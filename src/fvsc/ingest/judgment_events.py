"""Map portable judgments to canonical evidence without persisting source text."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from ..evidence import EvidenceEvent
from ..semantic import Judgment
from .vault_ingest import SourceDocument


JUDGMENT_DERIVATION = "linguistic-judgment"
JUDGMENT_EVENT_EXTRACTOR = "fvsc.ingest.judgment"
JUDGMENT_EVENT_EXTRACTOR_VERSION = "1"
_DEFAULT_MANAGER = "fvsc-document-ingest-v1"


@dataclass(frozen=True)
class SourceSpan:
    """Content-addressed half-open character span inside one source revision."""

    start: int
    end: int
    text_sha256: str

    def __post_init__(self) -> None:
        if isinstance(self.start, bool) or isinstance(self.end, bool):
            raise ValueError("source span offsets must be integers")
        if not isinstance(self.start, int) or not isinstance(self.end, int):
            raise ValueError("source span offsets must be integers")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("source span must be non-empty and half-open")
        digest = str(self.text_sha256).strip()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("source span digest must be lowercase SHA-256")
        object.__setattr__(self, "text_sha256", digest)

    @classmethod
    def from_document(cls, document: SourceDocument, *, start: int, end: int) -> "SourceSpan":
        if end > len(document.text):
            raise ValueError("source span extends beyond the document")
        text = document.text[start:end]
        if not text:
            raise ValueError("source span must not be empty")
        return cls(
            start=start,
            end=end,
            text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )

    def verify(self, document: SourceDocument) -> None:
        if self.end > len(document.text):
            raise ValueError("source span extends beyond the document")
        digest = hashlib.sha256(document.text[self.start : self.end].encode("utf-8")).hexdigest()
        if digest != self.text_sha256:
            raise ValueError("source span does not match the document revision")

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "text_sha256": self.text_sha256,
        }


def _source_assertion_key(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def judgment_to_evidence_event(
    judgment: Judgment,
    *,
    document: SourceDocument,
    source_span: SourceSpan,
    extractor: str = JUDGMENT_EVENT_EXTRACTOR,
    extractor_version: str = JUDGMENT_EVENT_EXTRACTOR_VERSION,
    managed_by: str = _DEFAULT_MANAGER,
    provenance: Mapping[str, Any] | None = None,
) -> EvidenceEvent:
    """Create a deterministic assertion for one extracted judgment.

    The persisted event contains a source id, revision, offsets, and span digest.
    It deliberately does not contain the private sentence body; callers resolve it
    from the original source when producing citations.
    """
    source_span.verify(document)
    context = {
        "derivation": JUDGMENT_DERIVATION,
        "judgment": judgment.to_evidence_context(),
        "source_kind": document.source_kind,
        "source_span": source_span.to_dict(),
    }
    key_payload = {
        "context": context,
        "extractor": extractor,
        "extractor_version": extractor_version,
        "object": judgment.object,
        "polarity": judgment.polarity,
        "relation": judgment.verb,
        "source_adapter": document.adapter,
        "source_id": document.source_id,
        "source_revision": document.source_revision,
        "subject": judgment.subject,
        "modality": judgment.modality,
        "intensity": judgment.intensity,
        "confidence": judgment.extraction_confidence,
        "interpretation_layer": judgment.interpretation_layer,
    }
    assertion_key = _source_assertion_key(key_payload)
    event_provenance = {
        "managed_by": managed_by,
        "source_adapter": document.adapter,
        "source_assertion_key": assertion_key,
        "source_id": document.source_id,
        "source_revision": document.source_revision,
        **dict(provenance or {}),
    }
    # Required manager fields cannot be shadowed by extractor-specific metadata.
    event_provenance.update(
        {
            "managed_by": managed_by,
            "source_adapter": document.adapter,
            "source_assertion_key": assertion_key,
            "source_id": document.source_id,
            "source_revision": document.source_revision,
        }
    )
    return EvidenceEvent.assertion(
        source_id=document.source_id,
        source_revision=document.source_revision,
        observed_at=document.observed_at,
        recorded_at=document.observed_at,
        subject=judgment.subject,
        relation=judgment.verb,
        object=judgment.object,
        polarity=judgment.polarity,
        modality=judgment.modality,
        intensity=judgment.intensity,
        confidence=judgment.extraction_confidence,
        interpretation_layer=judgment.interpretation_layer,
        extractor=extractor,
        extractor_version=extractor_version,
        context=context,
        provenance=event_provenance,
    )


__all__ = [
    "JUDGMENT_DERIVATION",
    "JUDGMENT_EVENT_EXTRACTOR",
    "JUDGMENT_EVENT_EXTRACTOR_VERSION",
    "SourceSpan",
    "judgment_to_evidence_event",
]
