"""Typed interpretation proposals with verifiable source citations.

Proposals are deliberately not ``EvidenceEvent`` objects.  They may compress,
connect, or interpret source material, but ADR-004 requires an explicit owner
confirmation flow before any resulting statement can enter the canonical
ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Literal, Mapping, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from ..ingest.vault_ingest import SourceDocument


AntourageOutputType = Literal[
    "evidence_reference",
    "deterministic_computation",
    "interpretation",
    "owner_simulation",
    "proposal",
    "counterfactual",
    "creative_artifact",
    "action_request",
]
SupportLevel = Literal["evidence_bound", "partially_supported", "free_generation"]
InterpretationLayer = Literal[2, 3]

_OUTPUT_TYPES = frozenset(
    {
        "evidence_reference",
        "deterministic_computation",
        "interpretation",
        "owner_simulation",
        "proposal",
        "counterfactual",
        "creative_artifact",
        "action_request",
    }
)
_SUPPORT_LEVELS = frozenset(
    {"evidence_bound", "partially_supported", "free_generation"}
)
_SHA256_HEX_LENGTH = 64


def _nonempty(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must not be empty")
    return result


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _validate_digest(value: Any, *, field: str) -> str:
    digest = str(value).strip()
    if len(digest) != _SHA256_HEX_LENGTH or any(
        char not in "0123456789abcdef" for char in digest
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return digest


def _canonical_json(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("proposal metadata must contain JSON values") from exc


def _content_id(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceCitation:
    """One exact, content-addressed span in a source revision."""

    citation_id: str
    source_id: str
    source_revision: str
    start: int
    end: int
    text_sha256: str
    evidence_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        source_id = _nonempty(self.source_id, field="source_id")
        revision = _validate_digest(self.source_revision, field="source_revision")
        if isinstance(self.start, bool) or isinstance(self.end, bool):
            raise ValueError("citation offsets must be integers")
        if not isinstance(self.start, int) or not isinstance(self.end, int):
            raise ValueError("citation offsets must be integers")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("citation span must be non-empty and half-open")
        text_digest = _validate_digest(self.text_sha256, field="text_sha256")
        event_ids = tuple(
            _validate_digest(value, field="evidence_event_id")
            for value in self.evidence_event_ids
        )
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("citation evidence event ids must be unique")
        payload = {
            "end": self.end,
            "evidence_event_ids": list(event_ids),
            "source_id": source_id,
            "source_revision": revision,
            "start": self.start,
            "text_sha256": text_digest,
        }
        expected_id = _content_id(payload)
        if self.citation_id != expected_id:
            raise ValueError("citation_id does not match the canonical citation payload")
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "source_revision", revision)
        object.__setattr__(self, "text_sha256", text_digest)
        object.__setattr__(self, "evidence_event_ids", event_ids)

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        source_revision: str,
        start: int,
        end: int,
        text_sha256: str,
        evidence_event_ids: tuple[str, ...] = (),
    ) -> "SourceCitation":
        payload = {
            "end": end,
            "evidence_event_ids": list(evidence_event_ids),
            "source_id": str(source_id).strip(),
            "source_revision": str(source_revision).strip(),
            "start": start,
            "text_sha256": str(text_sha256).strip(),
        }
        return cls(citation_id=_content_id(payload), **payload)

    @classmethod
    def from_document(
        cls,
        document: "SourceDocument",
        *,
        start: int = 0,
        end: int | None = None,
        evidence_event_ids: tuple[str, ...] = (),
    ) -> "SourceCitation":
        stop = len(document.text) if end is None else end
        if stop > len(document.text):
            raise ValueError("citation span extends beyond the source document")
        text = document.text[start:stop]
        if not text:
            raise ValueError("citation span must not be empty")
        return cls.create(
            source_id=document.source_id,
            source_revision=document.source_revision,
            start=start,
            end=stop,
            text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            evidence_event_ids=evidence_event_ids,
        )

    def verify(self, document: "SourceDocument") -> None:
        if document.source_id != self.source_id:
            raise ValueError("citation source id does not match the document")
        if document.source_revision != self.source_revision:
            raise ValueError("citation source revision does not match the document")
        if self.end > len(document.text):
            raise ValueError("citation span extends beyond the source document")
        digest = hashlib.sha256(
            document.text[self.start : self.end].encode("utf-8")
        ).hexdigest()
        if digest != self.text_sha256:
            raise ValueError("citation text does not match the source revision")

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "source_id": self.source_id,
            "source_revision": self.source_revision,
            "start": self.start,
            "end": self.end,
            "text_sha256": self.text_sha256,
            "evidence_event_ids": list(self.evidence_event_ids),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceCitation":
        raw_event_ids = value.get("evidence_event_ids", [])
        if not isinstance(raw_event_ids, list):
            raise ValueError("evidence_event_ids must be an array")
        return cls(
            citation_id=value.get("citation_id", ""),
            source_id=value.get("source_id", ""),
            source_revision=value.get("source_revision", ""),
            start=value.get("start", -1),
            end=value.get("end", -1),
            text_sha256=value.get("text_sha256", ""),
            evidence_event_ids=tuple(raw_event_ids),
        )


@dataclass(frozen=True)
class InterpretationClaim:
    """One independently citable assertion within a generated answer."""

    claim_id: str
    text: str
    citation_ids: tuple[str, ...]
    support_level: SupportLevel

    def __post_init__(self) -> None:
        text = _nonempty(self.text, field="claim text")
        if self.support_level not in _SUPPORT_LEVELS:
            raise ValueError(f"unknown support level: {self.support_level!r}")
        citation_ids = tuple(
            _validate_digest(value, field="citation_id") for value in self.citation_ids
        )
        if len(citation_ids) != len(set(citation_ids)):
            raise ValueError("claim citation ids must be unique")
        if self.support_level != "free_generation" and not citation_ids:
            raise ValueError("supported claims require at least one citation")
        payload = {
            "citation_ids": list(citation_ids),
            "support_level": self.support_level,
            "text": text,
        }
        if self.claim_id != _content_id(payload):
            raise ValueError("claim_id does not match the canonical claim payload")
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "citation_ids", citation_ids)

    @classmethod
    def create(
        cls,
        *,
        text: str,
        citation_ids: tuple[str, ...] = (),
        support_level: SupportLevel = "evidence_bound",
    ) -> "InterpretationClaim":
        payload = {
            "citation_ids": list(citation_ids),
            "support_level": support_level,
            "text": str(text).strip(),
        }
        return cls(claim_id=_content_id(payload), **payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "citation_ids": list(self.citation_ids),
            "support_level": self.support_level,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InterpretationClaim":
        raw_citation_ids = value.get("citation_ids", [])
        if not isinstance(raw_citation_ids, list):
            raise ValueError("citation_ids must be an array")
        return cls(
            claim_id=value.get("claim_id", ""),
            text=value.get("text", ""),
            citation_ids=tuple(raw_citation_ids),
            support_level=value.get("support_level", "evidence_bound"),
        )


def _combined_support(claims: tuple[InterpretationClaim, ...]) -> SupportLevel:
    levels = {claim.support_level for claim in claims}
    if "free_generation" in levels:
        return "free_generation"
    if "partially_supported" in levels:
        return "partially_supported"
    return "evidence_bound"


@dataclass(frozen=True)
class InterpretationProposal:
    """An immutable L2/L3 output that cannot silently become owner evidence."""

    proposal_id: str
    question: str
    answer: str
    claims: tuple[InterpretationClaim, ...]
    citations: tuple[SourceCitation, ...]
    output_type: AntourageOutputType
    support_level: SupportLevel
    interpretation_layer: InterpretationLayer
    producer: str
    model: str | None
    prompt_version: str
    generated_at: float
    retrieval_method: str
    metadata_json: str = "{}"
    defeasible: bool = True

    def __post_init__(self) -> None:
        question = _nonempty(self.question, field="proposal question")
        answer = _nonempty(self.answer, field="proposal answer")
        producer = _nonempty(self.producer, field="proposal producer")
        prompt_version = _nonempty(self.prompt_version, field="prompt_version")
        retrieval_method = _nonempty(self.retrieval_method, field="retrieval_method")
        model = _optional_text(self.model)
        if self.output_type not in _OUTPUT_TYPES:
            raise ValueError(f"unknown Antourage output type: {self.output_type!r}")
        if self.interpretation_layer not in {2, 3}:
            raise ValueError("interpretation proposals must use layer 2 or 3")
        if self.defeasible is not True:
            raise ValueError("interpretation proposals must remain defeasible")
        generated_at = float(self.generated_at)
        if not math.isfinite(generated_at):
            raise ValueError("generated_at must be finite")
        if not self.claims:
            raise ValueError("interpretation proposal must contain at least one claim")
        citation_ids = tuple(item.citation_id for item in self.citations)
        if len(citation_ids) != len(set(citation_ids)):
            raise ValueError("proposal citations must be unique")
        known_citations = set(citation_ids)
        for claim in self.claims:
            if not set(claim.citation_ids) <= known_citations:
                raise ValueError("claim references a citation outside the proposal")
        combined_support = _combined_support(self.claims)
        if self.support_level != combined_support:
            raise ValueError("proposal support level must match its weakest claim")
        if self.support_level == "evidence_bound":
            used = {item for claim in self.claims for item in claim.citation_ids}
            if used != known_citations:
                raise ValueError("evidence-bound proposals cannot carry unused citations")
        try:
            metadata = json.loads(self.metadata_json)
        except json.JSONDecodeError as exc:
            raise ValueError("metadata_json must contain a JSON object") from exc
        if not isinstance(metadata, dict):
            raise ValueError("metadata_json must contain a JSON object")
        metadata_json = _canonical_json(metadata)
        payload = {
            "answer": answer,
            "citations": [item.to_dict() for item in self.citations],
            "claims": [item.to_dict() for item in self.claims],
            "defeasible": True,
            "generated_at": generated_at,
            "interpretation_layer": self.interpretation_layer,
            "metadata": json.loads(metadata_json),
            "model": model,
            "output_type": self.output_type,
            "producer": producer,
            "prompt_version": prompt_version,
            "question": question,
            "retrieval_method": retrieval_method,
            "support_level": self.support_level,
        }
        if self.proposal_id != _content_id(payload):
            raise ValueError("proposal_id does not match the canonical proposal payload")
        object.__setattr__(self, "question", question)
        object.__setattr__(self, "answer", answer)
        object.__setattr__(self, "producer", producer)
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "prompt_version", prompt_version)
        object.__setattr__(self, "generated_at", generated_at)
        object.__setattr__(self, "retrieval_method", retrieval_method)
        object.__setattr__(self, "metadata_json", metadata_json)

    @classmethod
    def create(
        cls,
        *,
        question: str,
        answer: str,
        claims: tuple[InterpretationClaim, ...],
        citations: tuple[SourceCitation, ...],
        interpretation_layer: InterpretationLayer,
        producer: str,
        prompt_version: str,
        generated_at: float,
        retrieval_method: str,
        output_type: AntourageOutputType = "interpretation",
        model: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "InterpretationProposal":
        support_level = _combined_support(claims)
        metadata_json = _canonical_json(metadata or {})
        payload = {
            "answer": str(answer).strip(),
            "citations": [item.to_dict() for item in citations],
            "claims": [item.to_dict() for item in claims],
            "defeasible": True,
            "generated_at": float(generated_at),
            "interpretation_layer": interpretation_layer,
            "metadata": json.loads(metadata_json),
            "model": _optional_text(model),
            "output_type": output_type,
            "producer": str(producer).strip(),
            "prompt_version": str(prompt_version).strip(),
            "question": str(question).strip(),
            "retrieval_method": str(retrieval_method).strip(),
            "support_level": support_level,
        }
        return cls(
            proposal_id=_content_id(payload),
            question=payload["question"],
            answer=payload["answer"],
            claims=claims,
            citations=citations,
            output_type=cast(AntourageOutputType, output_type),
            support_level=support_level,
            interpretation_layer=interpretation_layer,
            producer=payload["producer"],
            model=payload["model"],
            prompt_version=payload["prompt_version"],
            generated_at=payload["generated_at"],
            retrieval_method=payload["retrieval_method"],
            metadata_json=metadata_json,
            defeasible=True,
        )

    @property
    def metadata(self) -> dict[str, Any]:
        return json.loads(self.metadata_json)

    @property
    def cited_source_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.source_id for item in self.citations))

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "question": self.question,
            "answer": self.answer,
            "claims": [item.to_dict() for item in self.claims],
            "citations": [item.to_dict() for item in self.citations],
            "output_type": self.output_type,
            "support_level": self.support_level,
            "interpretation_layer": self.interpretation_layer,
            "producer": self.producer,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "generated_at": self.generated_at,
            "retrieval_method": self.retrieval_method,
            "metadata": self.metadata,
            "defeasible": self.defeasible,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "InterpretationProposal":
        raw_claims = value.get("claims", [])
        raw_citations = value.get("citations", [])
        raw_metadata = value.get("metadata", {})
        if not isinstance(raw_claims, list) or not isinstance(raw_citations, list):
            raise ValueError("proposal claims and citations must be arrays")
        if not isinstance(raw_metadata, Mapping):
            raise ValueError("proposal metadata must be an object")
        return cls(
            proposal_id=value.get("proposal_id", ""),
            question=value.get("question", ""),
            answer=value.get("answer", ""),
            claims=tuple(InterpretationClaim.from_dict(item) for item in raw_claims),
            citations=tuple(SourceCitation.from_dict(item) for item in raw_citations),
            output_type=value.get("output_type", "interpretation"),
            support_level=value.get("support_level", "free_generation"),
            interpretation_layer=value.get("interpretation_layer", 3),
            producer=value.get("producer", ""),
            model=value.get("model"),
            prompt_version=value.get("prompt_version", ""),
            generated_at=value.get("generated_at", float("nan")),
            retrieval_method=value.get("retrieval_method", ""),
            metadata_json=_canonical_json(raw_metadata),
            defeasible=value.get("defeasible", True),
        )


__all__ = [
    "AntourageOutputType",
    "InterpretationClaim",
    "InterpretationLayer",
    "InterpretationProposal",
    "SourceCitation",
    "SupportLevel",
]
