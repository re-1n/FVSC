"""Immutable contracts for the controlled Stage 4h attribution test.

The committed contracts contain identifiers, revisions, configuration and
owner-review mechanics.  Raw source bodies and generated prose remain local
runtime data.  Content-addressed manifests make candidate or threshold drift
visible instead of silently changing the experiment after review begins.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Literal, Mapping, Sequence


Stage4hArm = Literal["A0", "A1", "A2", "A3", "A4"]
CandidateRole = Literal["ranked", "context", "oracle"]
ClaimReviewVerdict = Literal[
    "accepted",
    "partially_accepted",
    "rejected",
    "needs_revision",
]
CitationReviewVerdict = Literal["supports", "partial", "unsupported"]

_STAGE4H_ARMS = frozenset({"A0", "A1", "A2", "A3", "A4"})
STAGE4H_REQUIRED_ARMS = frozenset({"A0", "A1", "A2", "A4"})
_CANDIDATE_ROLES = frozenset({"ranked", "context", "oracle"})
_CLAIM_REVIEW_VERDICTS = frozenset(
    {"accepted", "partially_accepted", "rejected", "needs_revision"}
)
_CITATION_REVIEW_VERDICTS = frozenset({"supports", "partial", "unsupported"})
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")
MAX_STAGE4H_CONTRACT_BYTES = 8 * 1024 * 1024


def _nonempty(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must not be empty")
    return result


def _optional_nonempty(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    return _nonempty(value, field=field)


def _digest(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if _DIGEST_RE.fullmatch(result) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return result


def _finite(
    value: Any,
    *,
    field: str,
    lower: float | None = None,
    upper: float | None = None,
) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    if lower is not None and result < lower:
        raise ValueError(f"{field} must be >= {lower:g}")
    if upper is not None and result > upper:
        raise ValueError(f"{field} must be <= {upper:g}")
    return result


def _integer(
    value: Any,
    *,
    field: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f"[{minimum}, {maximum}]" if maximum is not None else f">= {minimum}"
        raise ValueError(f"{field} must be {bounds}")
    return value


def _unique_strings(values: Sequence[Any], *, field: str) -> tuple[str, ...]:
    result = tuple(_nonempty(value, field=field) for value in values)
    if len(result) != len(set(result)):
        raise ValueError(f"{field} values must be unique")
    return result


def canonical_json(value: Any) -> str:
    """Return the one JSON encoding used for every Stage 4h content id."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Stage 4h contract must contain JSON values") from exc


def content_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    """Hash one regular file without following a symlink."""
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"refusing non-regular Stage 4h input: {source}")
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class Stage4hModelConfig:
    backend_id: str
    model: str
    prompt_version: str
    temperature: float = 0.0
    seed: int = 42
    num_ctx: int = 8_192
    model_digest: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend_id", _nonempty(self.backend_id, field="backend_id"))
        object.__setattr__(self, "model", _nonempty(self.model, field="model"))
        object.__setattr__(
            self,
            "prompt_version",
            _nonempty(self.prompt_version, field="prompt_version"),
        )
        object.__setattr__(
            self,
            "temperature",
            _finite(self.temperature, field="temperature", lower=0.0, upper=2.0),
        )
        object.__setattr__(
            self,
            "seed",
            _integer(self.seed, field="seed", maximum=2**31 - 1),
        )
        object.__setattr__(
            self,
            "num_ctx",
            _integer(self.num_ctx, field="num_ctx", minimum=256, maximum=1_048_576),
        )
        if self.model_digest is not None:
            object.__setattr__(
                self,
                "model_digest",
                _digest(self.model_digest, field="model_digest"),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "model": self.model,
            "model_digest": self.model_digest,
            "num_ctx": self.num_ctx,
            "prompt_version": self.prompt_version,
            "seed": self.seed,
            "temperature": self.temperature,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hModelConfig":
        return cls(
            backend_id=value.get("backend_id", ""),
            model=value.get("model", ""),
            model_digest=value.get("model_digest"),
            num_ctx=value.get("num_ctx", 8_192),
            prompt_version=value.get("prompt_version", ""),
            seed=value.get("seed", 42),
            temperature=value.get("temperature", 0.0),
        )


@dataclass(frozen=True)
class Stage4hThresholds:
    """Preregistered gates; severe errors are never averaged into prose quality."""

    oracle_min_accepted_or_partial_rate: float = 0.80
    min_citation_precision: float = 0.90
    min_median_meaning_fidelity: float = 3.0
    structural_min_mean_paired_fidelity_delta: float = 0.50
    max_citation_precision_drop: float = 0.05
    max_latency_multiplier: float = 2.0
    max_severe_errors: int = 0

    def __post_init__(self) -> None:
        for field in (
            "oracle_min_accepted_or_partial_rate",
            "min_citation_precision",
            "max_citation_precision_drop",
        ):
            object.__setattr__(
                self,
                field,
                _finite(getattr(self, field), field=field, lower=0.0, upper=1.0),
            )
        object.__setattr__(
            self,
            "min_median_meaning_fidelity",
            _finite(
                self.min_median_meaning_fidelity,
                field="min_median_meaning_fidelity",
                lower=0.0,
                upper=4.0,
            ),
        )
        object.__setattr__(
            self,
            "structural_min_mean_paired_fidelity_delta",
            _finite(
                self.structural_min_mean_paired_fidelity_delta,
                field="structural_min_mean_paired_fidelity_delta",
                lower=0.0,
                upper=4.0,
            ),
        )
        object.__setattr__(
            self,
            "max_latency_multiplier",
            _finite(
                self.max_latency_multiplier,
                field="max_latency_multiplier",
                lower=1.0,
            ),
        )
        object.__setattr__(
            self,
            "max_severe_errors",
            _integer(self.max_severe_errors, field="max_severe_errors"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_citation_precision_drop": self.max_citation_precision_drop,
            "max_latency_multiplier": self.max_latency_multiplier,
            "max_severe_errors": self.max_severe_errors,
            "min_citation_precision": self.min_citation_precision,
            "min_median_meaning_fidelity": self.min_median_meaning_fidelity,
            "oracle_min_accepted_or_partial_rate": self.oracle_min_accepted_or_partial_rate,
            "structural_min_mean_paired_fidelity_delta": (
                self.structural_min_mean_paired_fidelity_delta
            ),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hThresholds":
        return cls(
            oracle_min_accepted_or_partial_rate=value.get(
                "oracle_min_accepted_or_partial_rate", 0.80
            ),
            min_citation_precision=value.get("min_citation_precision", 0.90),
            min_median_meaning_fidelity=value.get(
                "min_median_meaning_fidelity", 3.0
            ),
            structural_min_mean_paired_fidelity_delta=value.get(
                "structural_min_mean_paired_fidelity_delta", 0.50
            ),
            max_citation_precision_drop=value.get(
                "max_citation_precision_drop", 0.05
            ),
            max_latency_multiplier=value.get("max_latency_multiplier", 2.0),
            max_severe_errors=value.get("max_severe_errors", 0),
        )


@dataclass(frozen=True)
class Stage4hRunSpec:
    gold_sha256: str
    challenge_sha256: str
    corpus_sha256: str
    case_ids: tuple[str, ...]
    arms: tuple[Stage4hArm, ...]
    model: Stage4hModelConfig
    created_at: float
    thresholds: Stage4hThresholds = Stage4hThresholds()
    top_k: int = 10
    prompt_source_cap: int = 12
    context_depth: int = 1
    external_reference_scope: str | None = None
    schema_version: int = 1
    protocol_version: str = "stage4h-v1"

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported Stage 4h run schema version")
        if self.protocol_version != "stage4h-v1":
            raise ValueError("unsupported Stage 4h protocol version")
        object.__setattr__(self, "gold_sha256", _digest(self.gold_sha256, field="gold_sha256"))
        object.__setattr__(
            self,
            "challenge_sha256",
            _digest(self.challenge_sha256, field="challenge_sha256"),
        )
        object.__setattr__(
            self,
            "corpus_sha256",
            _digest(self.corpus_sha256, field="corpus_sha256"),
        )
        object.__setattr__(self, "case_ids", _unique_strings(self.case_ids, field="case_id"))
        arms = tuple(str(value).strip() for value in self.arms)
        if len(arms) != len(set(arms)) or any(value not in _STAGE4H_ARMS for value in arms):
            raise ValueError("Stage 4h arms must be unique known arm ids")
        if not STAGE4H_REQUIRED_ARMS.issubset(arms):
            missing = sorted(STAGE4H_REQUIRED_ARMS - set(arms))
            raise ValueError(f"Stage 4h run is missing required arms: {missing}")
        object.__setattr__(self, "arms", arms)
        object.__setattr__(
            self,
            "created_at",
            _finite(self.created_at, field="created_at", lower=0.0),
        )
        object.__setattr__(self, "top_k", _integer(self.top_k, field="top_k", minimum=1))
        object.__setattr__(
            self,
            "prompt_source_cap",
            _integer(self.prompt_source_cap, field="prompt_source_cap", minimum=1),
        )
        if self.prompt_source_cap < self.top_k:
            raise ValueError("prompt_source_cap must be >= top_k")
        object.__setattr__(
            self,
            "context_depth",
            _integer(self.context_depth, field="context_depth"),
        )
        scope = _optional_nonempty(
            self.external_reference_scope,
            field="external_reference_scope",
        )
        if "A3" in arms and scope is None:
            raise ValueError("A3 requires an explicit external_reference_scope")
        if "A3" not in arms and scope is not None:
            raise ValueError("external_reference_scope is valid only when A3 is enabled")
        object.__setattr__(self, "external_reference_scope", scope)

    def _payload(self) -> dict[str, Any]:
        return {
            "arms": list(self.arms),
            "case_ids": list(self.case_ids),
            "challenge_sha256": self.challenge_sha256,
            "context_depth": self.context_depth,
            "corpus_sha256": self.corpus_sha256,
            "created_at": self.created_at,
            "external_reference_scope": self.external_reference_scope,
            "gold_sha256": self.gold_sha256,
            "model": self.model.to_dict(),
            "prompt_source_cap": self.prompt_source_cap,
            "protocol_version": self.protocol_version,
            "schema_version": self.schema_version,
            "thresholds": self.thresholds.to_dict(),
            "top_k": self.top_k,
        }

    @property
    def run_id(self) -> str:
        return content_digest(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, **self._payload()}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hRunSpec":
        raw_model = value.get("model")
        raw_thresholds = value.get("thresholds", {})
        raw_cases = value.get("case_ids", [])
        raw_arms = value.get("arms", [])
        if not isinstance(raw_model, Mapping):
            raise ValueError("Stage 4h model must be an object")
        if not isinstance(raw_thresholds, Mapping):
            raise ValueError("Stage 4h thresholds must be an object")
        if not isinstance(raw_cases, list) or not isinstance(raw_arms, list):
            raise ValueError("Stage 4h case_ids and arms must be arrays")
        result = cls(
            gold_sha256=value.get("gold_sha256", ""),
            challenge_sha256=value.get("challenge_sha256", ""),
            corpus_sha256=value.get("corpus_sha256", ""),
            case_ids=tuple(raw_cases),
            arms=tuple(raw_arms),
            model=Stage4hModelConfig.from_dict(raw_model),
            created_at=value.get("created_at", -1),
            thresholds=Stage4hThresholds.from_dict(raw_thresholds),
            top_k=value.get("top_k", 10),
            prompt_source_cap=value.get("prompt_source_cap", 12),
            context_depth=value.get("context_depth", 1),
            external_reference_scope=value.get("external_reference_scope"),
            schema_version=value.get("schema_version", 0),
            protocol_version=value.get("protocol_version", ""),
        )
        supplied = value.get("run_id")
        if supplied is not None and supplied != result.run_id:
            raise ValueError("run_id does not match the Stage 4h manifest")
        return result


@dataclass(frozen=True)
class FrozenCandidate:
    rank: int
    source_id: str
    source_revision: str
    role: CandidateRole
    score: float | None = None
    evidence_event_ids: tuple[str, ...] = ()
    expanded_from_source_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "rank", _integer(self.rank, field="rank", minimum=1))
        object.__setattr__(self, "source_id", _nonempty(self.source_id, field="source_id"))
        object.__setattr__(
            self,
            "source_revision",
            _digest(self.source_revision, field="source_revision"),
        )
        if self.role not in _CANDIDATE_ROLES:
            raise ValueError(f"unknown candidate role: {self.role!r}")
        if self.score is not None:
            object.__setattr__(
                self,
                "score",
                _finite(self.score, field="candidate score", lower=0.0),
            )
        event_ids = tuple(
            _digest(value, field="evidence_event_id") for value in self.evidence_event_ids
        )
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("candidate evidence_event_ids must be unique")
        object.__setattr__(self, "evidence_event_ids", event_ids)
        object.__setattr__(
            self,
            "expanded_from_source_id",
            _optional_nonempty(
                self.expanded_from_source_id,
                field="expanded_from_source_id",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_event_ids": list(self.evidence_event_ids),
            "expanded_from_source_id": self.expanded_from_source_id,
            "rank": self.rank,
            "role": self.role,
            "score": self.score,
            "source_id": self.source_id,
            "source_revision": self.source_revision,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FrozenCandidate":
        raw_event_ids = value.get("evidence_event_ids", [])
        if not isinstance(raw_event_ids, list):
            raise ValueError("candidate evidence_event_ids must be an array")
        return cls(
            rank=value.get("rank", 0),
            source_id=value.get("source_id", ""),
            source_revision=value.get("source_revision", ""),
            role=value.get("role", "ranked"),
            score=value.get("score"),
            evidence_event_ids=tuple(raw_event_ids),
            expanded_from_source_id=value.get("expanded_from_source_id"),
        )


@dataclass(frozen=True)
class FrozenCandidateSet:
    candidate_set_id: str
    run_id: str
    case_id: str
    arm: Stage4hArm
    retrieval_method: str
    candidates: tuple[FrozenCandidate, ...]

    def __post_init__(self) -> None:
        run_id = _digest(self.run_id, field="run_id")
        case_id = _nonempty(self.case_id, field="case_id")
        if self.arm not in _STAGE4H_ARMS:
            raise ValueError(f"unknown Stage 4h arm: {self.arm!r}")
        retrieval_method = _nonempty(self.retrieval_method, field="retrieval_method")
        ranks = tuple(item.rank for item in self.candidates)
        if ranks != tuple(range(1, len(self.candidates) + 1)):
            raise ValueError("candidate ranks must be contiguous and ordered from 1")
        source_ids = tuple(item.source_id for item in self.candidates)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("candidate source ids must be unique")
        known = set(source_ids)
        for item in self.candidates:
            parent = item.expanded_from_source_id
            if parent is not None and parent not in known:
                raise ValueError("expanded candidate parent must be in the candidate set")
        payload = {
            "arm": self.arm,
            "candidates": [item.to_dict() for item in self.candidates],
            "case_id": case_id,
            "retrieval_method": retrieval_method,
            "run_id": run_id,
        }
        if self.candidate_set_id != content_digest(payload):
            raise ValueError("candidate_set_id does not match the frozen candidates")
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "retrieval_method", retrieval_method)

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        case_id: str,
        arm: Stage4hArm,
        retrieval_method: str,
        candidates: tuple[FrozenCandidate, ...],
    ) -> "FrozenCandidateSet":
        normalized_run_id = str(run_id).strip()
        normalized_case_id = str(case_id).strip()
        normalized_method = str(retrieval_method).strip()
        payload = {
            "arm": arm,
            "candidates": [item.to_dict() for item in candidates],
            "case_id": normalized_case_id,
            "retrieval_method": normalized_method,
            "run_id": normalized_run_id,
        }
        return cls(
            candidate_set_id=content_digest(payload),
            run_id=normalized_run_id,
            case_id=normalized_case_id,
            arm=arm,
            retrieval_method=normalized_method,
            candidates=candidates,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "candidate_set_id": self.candidate_set_id,
            "candidates": [item.to_dict() for item in self.candidates],
            "case_id": self.case_id,
            "retrieval_method": self.retrieval_method,
            "run_id": self.run_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FrozenCandidateSet":
        raw_candidates = value.get("candidates", [])
        if not isinstance(raw_candidates, list):
            raise ValueError("frozen candidates must be an array")
        return cls(
            candidate_set_id=value.get("candidate_set_id", ""),
            run_id=value.get("run_id", ""),
            case_id=value.get("case_id", ""),
            arm=value.get("arm", ""),
            retrieval_method=value.get("retrieval_method", ""),
            candidates=tuple(FrozenCandidate.from_dict(item) for item in raw_candidates),
        )


@dataclass(frozen=True)
class Stage4hCitationReview:
    citation_id: str
    verdict: CitationReviewVerdict

    def __post_init__(self) -> None:
        object.__setattr__(self, "citation_id", _digest(self.citation_id, field="citation_id"))
        if self.verdict not in _CITATION_REVIEW_VERDICTS:
            raise ValueError(f"unknown citation review verdict: {self.verdict!r}")

    def to_dict(self) -> dict[str, str]:
        return {"citation_id": self.citation_id, "verdict": self.verdict}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hCitationReview":
        return cls(
            citation_id=value.get("citation_id", ""),
            verdict=value.get("verdict", ""),
        )


@dataclass(frozen=True)
class Stage4hClaimReview:
    claim_id: str
    verdict: ClaimReviewVerdict
    citations: tuple[Stage4hCitationReview, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _digest(self.claim_id, field="claim_id"))
        if self.verdict not in _CLAIM_REVIEW_VERDICTS:
            raise ValueError(f"unknown claim review verdict: {self.verdict!r}")
        citation_ids = tuple(item.citation_id for item in self.citations)
        if len(citation_ids) != len(set(citation_ids)):
            raise ValueError("claim review citation ids must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "citations": [item.to_dict() for item in self.citations],
            "claim_id": self.claim_id,
            "verdict": self.verdict,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hClaimReview":
        raw_citations = value.get("citations", [])
        if not isinstance(raw_citations, list):
            raise ValueError("claim review citations must be an array")
        return cls(
            claim_id=value.get("claim_id", ""),
            verdict=value.get("verdict", ""),
            citations=tuple(Stage4hCitationReview.from_dict(item) for item in raw_citations),
        )


@dataclass(frozen=True)
class Stage4hOwnerReview:
    review_id: str
    blind_item_id: str
    proposal_id: str
    claim_reviews: tuple[Stage4hClaimReview, ...]
    meaning_fidelity: int
    usefulness: int
    false_owner_attribution: bool = False
    unsupported_referent_assumption: bool = False
    forbidden_composite: bool = False
    missed_context: bool = False
    abstention_preferable: bool = False

    def __post_init__(self) -> None:
        blind_item_id = _digest(self.blind_item_id, field="blind_item_id")
        proposal_id = _digest(self.proposal_id, field="proposal_id")
        claim_ids = tuple(item.claim_id for item in self.claim_reviews)
        if not claim_ids:
            raise ValueError("owner review requires at least one claim review")
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("owner review claim ids must be unique")
        fidelity = _integer(
            self.meaning_fidelity,
            field="meaning_fidelity",
            maximum=4,
        )
        usefulness = _integer(self.usefulness, field="usefulness", maximum=4)
        for field in (
            "false_owner_attribution",
            "unsupported_referent_assumption",
            "forbidden_composite",
            "missed_context",
            "abstention_preferable",
        ):
            if not isinstance(getattr(self, field), bool):
                raise ValueError(f"{field} must be boolean")
        payload = {
            "abstention_preferable": self.abstention_preferable,
            "blind_item_id": blind_item_id,
            "claim_reviews": [item.to_dict() for item in self.claim_reviews],
            "false_owner_attribution": self.false_owner_attribution,
            "forbidden_composite": self.forbidden_composite,
            "meaning_fidelity": fidelity,
            "missed_context": self.missed_context,
            "proposal_id": proposal_id,
            "unsupported_referent_assumption": self.unsupported_referent_assumption,
            "usefulness": usefulness,
        }
        if self.review_id != content_digest(payload):
            raise ValueError("review_id does not match the owner review")
        object.__setattr__(self, "blind_item_id", blind_item_id)
        object.__setattr__(self, "proposal_id", proposal_id)
        object.__setattr__(self, "meaning_fidelity", fidelity)
        object.__setattr__(self, "usefulness", usefulness)

    @classmethod
    def create(
        cls,
        *,
        blind_item_id: str,
        proposal_id: str,
        claim_reviews: tuple[Stage4hClaimReview, ...],
        meaning_fidelity: int,
        usefulness: int,
        false_owner_attribution: bool = False,
        unsupported_referent_assumption: bool = False,
        forbidden_composite: bool = False,
        missed_context: bool = False,
        abstention_preferable: bool = False,
    ) -> "Stage4hOwnerReview":
        normalized_blind_item_id = str(blind_item_id).strip()
        normalized_proposal_id = str(proposal_id).strip()
        payload = {
            "abstention_preferable": abstention_preferable,
            "blind_item_id": normalized_blind_item_id,
            "claim_reviews": [item.to_dict() for item in claim_reviews],
            "false_owner_attribution": false_owner_attribution,
            "forbidden_composite": forbidden_composite,
            "meaning_fidelity": meaning_fidelity,
            "missed_context": missed_context,
            "proposal_id": normalized_proposal_id,
            "unsupported_referent_assumption": unsupported_referent_assumption,
            "usefulness": usefulness,
        }
        return cls(
            review_id=content_digest(payload),
            blind_item_id=normalized_blind_item_id,
            proposal_id=normalized_proposal_id,
            claim_reviews=claim_reviews,
            meaning_fidelity=meaning_fidelity,
            usefulness=usefulness,
            false_owner_attribution=false_owner_attribution,
            unsupported_referent_assumption=unsupported_referent_assumption,
            forbidden_composite=forbidden_composite,
            missed_context=missed_context,
            abstention_preferable=abstention_preferable,
        )

    @property
    def severe_error_count(self) -> int:
        return sum(
            (
                self.false_owner_attribution,
                self.unsupported_referent_assumption,
                self.forbidden_composite,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "abstention_preferable": self.abstention_preferable,
            "blind_item_id": self.blind_item_id,
            "claim_reviews": [item.to_dict() for item in self.claim_reviews],
            "false_owner_attribution": self.false_owner_attribution,
            "forbidden_composite": self.forbidden_composite,
            "meaning_fidelity": self.meaning_fidelity,
            "missed_context": self.missed_context,
            "proposal_id": self.proposal_id,
            "review_id": self.review_id,
            "unsupported_referent_assumption": self.unsupported_referent_assumption,
            "usefulness": self.usefulness,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hOwnerReview":
        raw_claims = value.get("claim_reviews", [])
        if not isinstance(raw_claims, list):
            raise ValueError("owner claim_reviews must be an array")
        return cls(
            review_id=value.get("review_id", ""),
            blind_item_id=value.get("blind_item_id", ""),
            proposal_id=value.get("proposal_id", ""),
            claim_reviews=tuple(Stage4hClaimReview.from_dict(item) for item in raw_claims),
            meaning_fidelity=value.get("meaning_fidelity", -1),
            usefulness=value.get("usefulness", -1),
            false_owner_attribution=value.get("false_owner_attribution", False),
            unsupported_referent_assumption=value.get(
                "unsupported_referent_assumption", False
            ),
            forbidden_composite=value.get("forbidden_composite", False),
            missed_context=value.get("missed_context", False),
            abstention_preferable=value.get("abstention_preferable", False),
        )


def load_run_spec(path: Path) -> Stage4hRunSpec:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"refusing non-regular Stage 4h manifest: {source}")
    if source.stat().st_size > MAX_STAGE4H_CONTRACT_BYTES:
        raise ValueError("Stage 4h manifest exceeds the size limit")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Stage 4h manifest is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("Stage 4h manifest must contain an object")
    return Stage4hRunSpec.from_dict(value)


__all__ = [
    "MAX_STAGE4H_CONTRACT_BYTES",
    "STAGE4H_REQUIRED_ARMS",
    "CandidateRole",
    "CitationReviewVerdict",
    "ClaimReviewVerdict",
    "FrozenCandidate",
    "FrozenCandidateSet",
    "Stage4hArm",
    "Stage4hCitationReview",
    "Stage4hClaimReview",
    "Stage4hModelConfig",
    "Stage4hOwnerReview",
    "Stage4hRunSpec",
    "Stage4hThresholds",
    "canonical_json",
    "content_digest",
    "file_sha256",
    "load_run_spec",
]
