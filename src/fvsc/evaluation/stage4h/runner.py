"""Paired local Stage 4h runner over immutable candidate sets."""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any, Callable, Iterable, Literal, Mapping

from ...ingest import SourceDocument
from ...interpretation import (
    InterpretationBackend,
    InterpretationProposal,
    generate_interpretation_proposal,
)
from ..gold import GoldCase
from .candidates import FrozenCandidateBundle
from .contracts import (
    FrozenCandidateSet,
    Stage4hArm,
    Stage4hRunSpec,
    content_digest,
)


ArmRunStatus = Literal["extractive", "generated", "no_candidates"]
_ARM_RUN_STATUSES = frozenset({"extractive", "generated", "no_candidates"})
_LOCAL_GENERATIVE_ARMS = frozenset({"A1", "A2", "A4"})


def _nonempty(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must not be empty")
    return result


def _finite(value: Any, *, field: str, lower: float = 0.0) -> float:
    result = float(value)
    if not math.isfinite(result) or result < lower:
        raise ValueError(f"{field} must be finite and >= {lower:g}")
    return result


def _counter(value: Any, *, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer or null")
    return value


@dataclass(frozen=True)
class Stage4hGenerationTelemetry:
    backend_id: str
    model: str
    model_digest: str
    prompt_version: str
    temperature: float
    seed: int
    num_ctx: int
    source_count: int
    prompt_chars: int
    wall_seconds: float
    total_duration_ns: int | None = None
    load_duration_ns: int | None = None
    prompt_eval_count: int | None = None
    prompt_eval_duration_ns: int | None = None
    eval_count: int | None = None
    eval_duration_ns: int | None = None
    done_reason: str | None = None

    def __post_init__(self) -> None:
        from .contracts import Stage4hModelConfig

        normalized = Stage4hModelConfig(
            backend_id=self.backend_id,
            model=self.model,
            model_digest=self.model_digest,
            prompt_version=self.prompt_version,
            temperature=self.temperature,
            seed=self.seed,
            num_ctx=self.num_ctx,
        )
        object.__setattr__(self, "backend_id", normalized.backend_id)
        object.__setattr__(self, "model", normalized.model)
        object.__setattr__(self, "model_digest", normalized.model_digest)
        object.__setattr__(self, "prompt_version", normalized.prompt_version)
        object.__setattr__(self, "temperature", normalized.temperature)
        object.__setattr__(self, "seed", normalized.seed)
        object.__setattr__(self, "num_ctx", normalized.num_ctx)
        for field in ("source_count", "prompt_chars"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field} must be a non-negative integer")
        object.__setattr__(
            self,
            "wall_seconds",
            _finite(self.wall_seconds, field="wall_seconds"),
        )
        for field in (
            "total_duration_ns",
            "load_duration_ns",
            "prompt_eval_count",
            "prompt_eval_duration_ns",
            "eval_count",
            "eval_duration_ns",
        ):
            object.__setattr__(self, field, _counter(getattr(self, field), field=field))
        if self.done_reason is not None:
            object.__setattr__(
                self,
                "done_reason",
                _nonempty(self.done_reason, field="done_reason"),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "done_reason": self.done_reason,
            "eval_count": self.eval_count,
            "eval_duration_ns": self.eval_duration_ns,
            "load_duration_ns": self.load_duration_ns,
            "model": self.model,
            "model_digest": self.model_digest,
            "num_ctx": self.num_ctx,
            "prompt_chars": self.prompt_chars,
            "prompt_eval_count": self.prompt_eval_count,
            "prompt_eval_duration_ns": self.prompt_eval_duration_ns,
            "prompt_version": self.prompt_version,
            "seed": self.seed,
            "source_count": self.source_count,
            "temperature": self.temperature,
            "total_duration_ns": self.total_duration_ns,
            "wall_seconds": self.wall_seconds,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hGenerationTelemetry":
        return cls(
            backend_id=value.get("backend_id", ""),
            model=value.get("model", ""),
            model_digest=value.get("model_digest", ""),
            prompt_version=value.get("prompt_version", ""),
            temperature=value.get("temperature", float("nan")),
            seed=value.get("seed", -1),
            num_ctx=value.get("num_ctx", 0),
            source_count=value.get("source_count", -1),
            prompt_chars=value.get("prompt_chars", -1),
            wall_seconds=value.get("wall_seconds", float("nan")),
            total_duration_ns=value.get("total_duration_ns"),
            load_duration_ns=value.get("load_duration_ns"),
            prompt_eval_count=value.get("prompt_eval_count"),
            prompt_eval_duration_ns=value.get("prompt_eval_duration_ns"),
            eval_count=value.get("eval_count"),
            eval_duration_ns=value.get("eval_duration_ns"),
            done_reason=value.get("done_reason"),
        )


@dataclass(frozen=True)
class Stage4hArmResult:
    result_id: str
    run_id: str
    candidate_set_id: str
    case_id: str
    arm: Stage4hArm
    status: ArmRunStatus
    generated_at: float
    extractive_source_ids: tuple[str, ...] = ()
    proposal: InterpretationProposal | None = None
    telemetry: Stage4hGenerationTelemetry | None = None

    def __post_init__(self) -> None:
        if self.status not in _ARM_RUN_STATUSES:
            raise ValueError(f"unknown Stage 4h result status: {self.status!r}")
        generated_at = _finite(self.generated_at, field="generated_at")
        source_ids = tuple(
            _nonempty(value, field="extractive_source_id")
            for value in self.extractive_source_ids
        )
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("extractive source ids must be unique")
        if self.status == "generated":
            if self.arm not in _LOCAL_GENERATIVE_ARMS:
                raise ValueError("only local generative arms can contain a proposal")
            if self.proposal is None or self.telemetry is None or source_ids:
                raise ValueError("generated result requires proposal and telemetry only")
        elif self.status == "extractive":
            if self.arm != "A0" or not source_ids:
                raise ValueError("extractive result requires non-empty A0 sources")
            if self.proposal is not None or self.telemetry is not None:
                raise ValueError("extractive result cannot contain generated output")
        else:
            if source_ids or self.proposal is not None or self.telemetry is not None:
                raise ValueError("no-candidate result cannot contain output")
        payload = {
            "arm": self.arm,
            "candidate_set_id": self.candidate_set_id,
            "case_id": self.case_id,
            "extractive_source_ids": list(source_ids),
            "generated_at": generated_at,
            "proposal": None if self.proposal is None else self.proposal.to_dict(),
            "run_id": self.run_id,
            "status": self.status,
            "telemetry": None if self.telemetry is None else self.telemetry.to_dict(),
        }
        if self.result_id != content_digest(payload):
            raise ValueError("result_id does not match the Stage 4h arm result")
        object.__setattr__(self, "generated_at", generated_at)
        object.__setattr__(self, "extractive_source_ids", source_ids)

    @classmethod
    def create(
        cls,
        *,
        candidate_set: FrozenCandidateSet,
        status: ArmRunStatus,
        generated_at: float,
        extractive_source_ids: tuple[str, ...] = (),
        proposal: InterpretationProposal | None = None,
        telemetry: Stage4hGenerationTelemetry | None = None,
    ) -> "Stage4hArmResult":
        payload = {
            "arm": candidate_set.arm,
            "candidate_set_id": candidate_set.candidate_set_id,
            "case_id": candidate_set.case_id,
            "extractive_source_ids": list(extractive_source_ids),
            "generated_at": float(generated_at),
            "proposal": None if proposal is None else proposal.to_dict(),
            "run_id": candidate_set.run_id,
            "status": status,
            "telemetry": None if telemetry is None else telemetry.to_dict(),
        }
        return cls(
            result_id=content_digest(payload),
            run_id=candidate_set.run_id,
            candidate_set_id=candidate_set.candidate_set_id,
            case_id=candidate_set.case_id,
            arm=candidate_set.arm,
            status=status,
            generated_at=generated_at,
            extractive_source_ids=extractive_source_ids,
            proposal=proposal,
            telemetry=telemetry,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "candidate_set_id": self.candidate_set_id,
            "case_id": self.case_id,
            "extractive_source_ids": list(self.extractive_source_ids),
            "generated_at": self.generated_at,
            "proposal": None if self.proposal is None else self.proposal.to_dict(),
            "result_id": self.result_id,
            "run_id": self.run_id,
            "status": self.status,
            "telemetry": None if self.telemetry is None else self.telemetry.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hArmResult":
        raw_sources = value.get("extractive_source_ids", [])
        raw_proposal = value.get("proposal")
        raw_telemetry = value.get("telemetry")
        if not isinstance(raw_sources, list):
            raise ValueError("extractive_source_ids must be an array")
        if raw_proposal is not None and not isinstance(raw_proposal, Mapping):
            raise ValueError("Stage 4h proposal must be an object or null")
        if raw_telemetry is not None and not isinstance(raw_telemetry, Mapping):
            raise ValueError("Stage 4h telemetry must be an object or null")
        return cls(
            result_id=value.get("result_id", ""),
            run_id=value.get("run_id", ""),
            candidate_set_id=value.get("candidate_set_id", ""),
            case_id=value.get("case_id", ""),
            arm=value.get("arm", ""),
            status=value.get("status", ""),
            generated_at=value.get("generated_at", float("nan")),
            extractive_source_ids=tuple(raw_sources),
            proposal=(
                None
                if raw_proposal is None
                else InterpretationProposal.from_dict(raw_proposal)
            ),
            telemetry=(
                None
                if raw_telemetry is None
                else Stage4hGenerationTelemetry.from_dict(raw_telemetry)
            ),
        )


@dataclass(frozen=True)
class Stage4hRunResultBundle:
    bundle_id: str
    run_id: str
    candidate_bundle_id: str
    results: tuple[Stage4hArmResult, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported Stage 4h result bundle version")
        if any(item.run_id != self.run_id for item in self.results):
            raise ValueError("Stage 4h result bundle contains another run id")
        keys = tuple((item.case_id, item.arm) for item in self.results)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("Stage 4h results must be unique and sorted by case/arm")
        if self.bundle_id != content_digest(self._payload()):
            raise ValueError("bundle_id does not match the Stage 4h run results")

    def _payload(self) -> dict[str, Any]:
        return {
            "candidate_bundle_id": self.candidate_bundle_id,
            "results": [item.to_dict() for item in self.results],
            "run_id": self.run_id,
            "schema_version": self.schema_version,
        }

    @classmethod
    def create(
        cls,
        *,
        spec: Stage4hRunSpec,
        candidate_bundle: FrozenCandidateBundle,
        results: Iterable[Stage4hArmResult],
    ) -> "Stage4hRunResultBundle":
        ordered = tuple(sorted(results, key=lambda item: (item.case_id, item.arm)))
        expected = {(case_id, arm) for case_id in spec.case_ids for arm in spec.arms}
        actual = {(item.case_id, item.arm) for item in ordered}
        if actual != expected:
            raise ValueError("Stage 4h results do not cover every preregistered case/arm")
        candidate_ids = {
            item.candidate_set_id for item in candidate_bundle.candidate_sets
        }
        if any(item.candidate_set_id not in candidate_ids for item in ordered):
            raise ValueError("Stage 4h result references another candidate bundle")
        payload = {
            "candidate_bundle_id": candidate_bundle.bundle_id,
            "results": [item.to_dict() for item in ordered],
            "run_id": spec.run_id,
            "schema_version": 1,
        }
        return cls(
            bundle_id=content_digest(payload),
            run_id=spec.run_id,
            candidate_bundle_id=candidate_bundle.bundle_id,
            results=ordered,
        )

    def to_dict(self) -> dict[str, Any]:
        return {"bundle_id": self.bundle_id, **self._payload()}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hRunResultBundle":
        raw_results = value.get("results", [])
        if not isinstance(raw_results, list):
            raise ValueError("Stage 4h results must be an array")
        return cls(
            bundle_id=value.get("bundle_id", ""),
            run_id=value.get("run_id", ""),
            candidate_bundle_id=value.get("candidate_bundle_id", ""),
            results=tuple(Stage4hArmResult.from_dict(item) for item in raw_results),
            schema_version=value.get("schema_version", 0),
        )

    def for_case_arm(self, case_id: str, arm: str) -> Stage4hArmResult:
        for item in self.results:
            if item.case_id == case_id and item.arm == arm:
                return item
        raise KeyError((case_id, arm))


def validate_local_backend(spec: Stage4hRunSpec, backend: InterpretationBackend) -> None:
    expected = spec.model
    if expected.model_digest is None:
        raise ValueError("Stage 4h generation requires a preregistered model digest")
    fields = {
        "backend_id": getattr(backend, "backend_id", None),
        "model": getattr(backend, "model", None),
        "prompt_version": getattr(backend, "prompt_version", None),
        "temperature": getattr(backend, "temperature", None),
        "seed": getattr(backend, "seed", None),
        "num_ctx": getattr(backend, "num_ctx", None),
        "model_digest": getattr(backend, "model_digest", None),
    }
    for name, actual in fields.items():
        wanted = getattr(expected, name)
        if actual != wanted:
            raise ValueError(
                f"Stage 4h backend {name} does not match the preregistered model"
            )


def _telemetry(
    *,
    spec: Stage4hRunSpec,
    backend: InterpretationBackend,
    documents: tuple[SourceDocument, ...],
    question: str,
    wall_seconds: float,
) -> Stage4hGenerationTelemetry:
    provider = getattr(backend, "last_generation_telemetry", None)

    def value(name: str, default: Any = None) -> Any:
        return default if provider is None else getattr(provider, name, default)

    returned_model = value("model", spec.model.model)
    returned_digest = value("model_digest", spec.model.model_digest)
    if returned_model != spec.model.model or returned_digest != spec.model.model_digest:
        raise ValueError("generation telemetry does not match the preregistered model")
    source_count = value("source_count", len(documents))
    if source_count != len(documents):
        raise ValueError("generation telemetry source count does not match the prompt")
    return Stage4hGenerationTelemetry(
        backend_id=spec.model.backend_id,
        model=returned_model,
        model_digest=returned_digest,
        prompt_version=spec.model.prompt_version,
        temperature=spec.model.temperature,
        seed=spec.model.seed,
        num_ctx=spec.model.num_ctx,
        source_count=source_count,
        prompt_chars=value(
            "prompt_chars",
            len(question) + sum(len(document.text) for document in documents),
        ),
        wall_seconds=wall_seconds,
        total_duration_ns=value("total_duration_ns"),
        load_duration_ns=value("load_duration_ns"),
        prompt_eval_count=value("prompt_eval_count"),
        prompt_eval_duration_ns=value("prompt_eval_duration_ns"),
        eval_count=value("eval_count"),
        eval_duration_ns=value("eval_duration_ns"),
        done_reason=value("done_reason"),
    )


def _resolve_documents(
    candidate_set: FrozenCandidateSet,
    by_id: Mapping[str, SourceDocument],
) -> tuple[tuple[SourceDocument, ...], dict[str, tuple[str, ...]]]:
    documents: list[SourceDocument] = []
    event_ids: dict[str, tuple[str, ...]] = {}
    for candidate in candidate_set.candidates:
        document = by_id.get(candidate.source_id)
        if document is None:
            raise ValueError("frozen candidate source is absent at generation time")
        if document.source_revision != candidate.source_revision:
            raise ValueError("frozen candidate source revision changed before generation")
        if not document.text:
            raise ValueError("frozen candidate source body is empty at generation time")
        documents.append(document)
        event_ids[document.source_id] = candidate.evidence_event_ids
    return tuple(documents), event_ids


def _verify_proposal_sources(
    proposal: InterpretationProposal,
    candidate_set: FrozenCandidateSet,
) -> None:
    revisions = {
        item.source_id: item.source_revision for item in candidate_set.candidates
    }
    for citation in proposal.citations:
        if revisions.get(citation.source_id) != citation.source_revision:
            raise ValueError("generated proposal cites outside the frozen candidate set")


def run_local_stage4h(
    *,
    spec: Stage4hRunSpec,
    candidate_bundle: FrozenCandidateBundle,
    cases: Iterable[GoldCase],
    documents: Iterable[SourceDocument],
    backend: InterpretationBackend,
    clock: Callable[[], float] = time.time,
    timer: Callable[[], float] = time.perf_counter,
) -> Stage4hRunResultBundle:
    """Run A0/A1/A2/A4; A3 requires a separately authorized external runner."""
    if "A3" in spec.arms:
        raise ValueError("A3 is not permitted in the local Stage 4h runner")
    if candidate_bundle.run_id != spec.run_id:
        raise ValueError("candidate bundle does not match the Stage 4h manifest")
    validate_local_backend(spec, backend)

    case_values = tuple(cases)
    by_case = {case.case_id: case for case in case_values}
    if len(by_case) != len(case_values):
        raise ValueError("Stage 4h cases must have unique ids")
    document_values = tuple(documents)
    by_document = {item.source_id: item for item in document_values}
    if len(by_document) != len(document_values):
        raise ValueError("Stage 4h source documents must have unique ids")

    results: list[Stage4hArmResult] = []
    for case_id in spec.case_ids:
        case = by_case.get(case_id)
        if case is None:
            raise ValueError(f"Stage 4h case is missing at run time: {case_id}")
        a0 = candidate_bundle.for_case_arm(case_id, "A0")
        a1 = candidate_bundle.for_case_arm(case_id, "A1")
        if [item.to_dict() for item in a0.candidates] != [
            item.to_dict() for item in a1.candidates
        ]:
            raise ValueError("A0 and A1 must use identical frozen lexical candidates")
        for arm in spec.arms:
            candidate_set = candidate_bundle.for_case_arm(case_id, arm)
            generated_at = clock()
            if not candidate_set.candidates:
                results.append(
                    Stage4hArmResult.create(
                        candidate_set=candidate_set,
                        status="no_candidates",
                        generated_at=generated_at,
                    )
                )
                continue
            if arm == "A0":
                results.append(
                    Stage4hArmResult.create(
                        candidate_set=candidate_set,
                        status="extractive",
                        generated_at=generated_at,
                        extractive_source_ids=tuple(
                            item.source_id for item in candidate_set.candidates
                        ),
                    )
                )
                continue
            documents_for_prompt, event_ids = _resolve_documents(
                candidate_set,
                by_document,
            )
            started = timer()
            proposal = generate_interpretation_proposal(
                question=case.question,
                documents=documents_for_prompt,
                backend=backend,
                generated_at=generated_at,
                retrieval_method=candidate_set.retrieval_method,
                evidence_event_ids_by_source=event_ids,
            )
            elapsed = timer() - started
            if elapsed < 0.0:
                raise ValueError("Stage 4h monotonic timer moved backwards")
            _verify_proposal_sources(proposal, candidate_set)
            results.append(
                Stage4hArmResult.create(
                    candidate_set=candidate_set,
                    status="generated",
                    generated_at=generated_at,
                    proposal=proposal,
                    telemetry=_telemetry(
                        spec=spec,
                        backend=backend,
                        documents=documents_for_prompt,
                        question=case.question,
                        wall_seconds=elapsed,
                    ),
                )
            )
    return Stage4hRunResultBundle.create(
        spec=spec,
        candidate_bundle=candidate_bundle,
        results=results,
    )


__all__ = [
    "ArmRunStatus",
    "Stage4hArmResult",
    "Stage4hGenerationTelemetry",
    "Stage4hRunResultBundle",
    "run_local_stage4h",
    "validate_local_backend",
]
