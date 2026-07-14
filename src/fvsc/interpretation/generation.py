"""Backend-neutral orchestration for source-cited interpretation generation."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Protocol

from ..ingest.vault_ingest import SourceDocument, SourceKind
from .proposals import (
    InterpretationClaim,
    InterpretationLayer,
    InterpretationProposal,
    SourceCitation,
    SupportLevel,
)


_SOURCE_LABEL_RE = re.compile(r"S[1-9]\d*")
_SUPPORT_LEVELS = frozenset(
    {"evidence_bound", "partially_supported", "free_generation"}
)


def _nonempty(value: str, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must not be empty")
    return result


@dataclass(frozen=True)
class PromptSource:
    """Transient source text exposed to one interpretation backend call."""

    label: str
    source_id: str
    source_revision: str
    observed_at: float
    source_kind: SourceKind
    text: str
    citation: SourceCitation

    def __post_init__(self) -> None:
        label = str(self.label).strip()
        if _SOURCE_LABEL_RE.fullmatch(label) is None:
            raise ValueError("prompt source label must use S<number> format")
        if not self.text:
            raise ValueError("prompt source text must not be empty")
        observed_at = float(self.observed_at)
        if not math.isfinite(observed_at):
            raise ValueError("prompt source observed_at must be finite")
        if self.citation.source_id != self.source_id:
            raise ValueError("prompt source citation id does not match")
        if self.citation.source_revision != self.source_revision:
            raise ValueError("prompt source citation revision does not match")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "observed_at", observed_at)

    @classmethod
    def from_document(
        cls,
        document: SourceDocument,
        *,
        label: str,
        evidence_event_ids: tuple[str, ...] = (),
    ) -> "PromptSource":
        citation = SourceCitation.from_document(
            document,
            evidence_event_ids=evidence_event_ids,
        )
        return cls(
            label=label,
            source_id=document.source_id,
            source_revision=document.source_revision,
            observed_at=document.observed_at,
            source_kind=document.source_kind,
            text=document.text,
            citation=citation,
        )


@dataclass(frozen=True)
class GeneratedClaim:
    text: str
    source_labels: tuple[str, ...]
    support_level: SupportLevel = "evidence_bound"

    def __post_init__(self) -> None:
        text = _nonempty(self.text, field="generated claim text")
        if self.support_level not in _SUPPORT_LEVELS:
            raise ValueError(f"unknown support level: {self.support_level!r}")
        labels = tuple(str(value).strip() for value in self.source_labels)
        if any(_SOURCE_LABEL_RE.fullmatch(value) is None for value in labels):
            raise ValueError("generated claim source labels must use S<number> format")
        if len(labels) != len(set(labels)):
            raise ValueError("generated claim source labels must be unique")
        if self.support_level == "free_generation" and labels:
            raise ValueError("free-generation claims cannot carry source citations")
        if self.support_level != "free_generation" and not labels:
            raise ValueError("supported generated claims require source citations")
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "source_labels", labels)


@dataclass(frozen=True)
class GeneratedInterpretation:
    answer: str
    claims: tuple[GeneratedClaim, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "answer",
            _nonempty(self.answer, field="generated interpretation answer"),
        )
        if not self.claims:
            raise ValueError("generated interpretation must contain claims")


class InterpretationBackend(Protocol):
    backend_id: str
    model: str | None
    prompt_version: str
    interpretation_layer: InterpretationLayer

    def generate(
        self,
        question: str,
        sources: tuple[PromptSource, ...],
    ) -> GeneratedInterpretation: ...


def generate_interpretation_proposal(
    *,
    question: str,
    documents: tuple[SourceDocument, ...],
    backend: InterpretationBackend,
    generated_at: float,
    retrieval_method: str = "lexical-char-ngram-v1",
    evidence_event_ids_by_source: dict[str, tuple[str, ...]] | None = None,
) -> InterpretationProposal:
    """Generate an isolated proposal and resolve backend labels to citations."""
    question_value = _nonempty(question, field="interpretation question")
    nonempty_documents = tuple(document for document in documents if document.text)
    source_ids = tuple(document.source_id for document in nonempty_documents)
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("interpretation source documents must have unique ids")
    if not nonempty_documents:
        raise ValueError("interpretation requires at least one non-empty source")
    event_ids = evidence_event_ids_by_source or {}
    prompt_sources = tuple(
        PromptSource.from_document(
            document,
            label=f"S{index}",
            evidence_event_ids=event_ids.get(document.source_id, ()),
        )
        for index, document in enumerate(nonempty_documents, start=1)
    )
    generated = backend.generate(question_value, prompt_sources)
    source_by_label = {item.label: item for item in prompt_sources}
    claims: list[InterpretationClaim] = []
    used_labels: set[str] = set()
    for candidate in generated.claims:
        unknown = set(candidate.source_labels) - set(source_by_label)
        if unknown:
            raise ValueError(
                f"interpretation backend cited unknown source labels: {sorted(unknown)}"
            )
        used_labels.update(candidate.source_labels)
        claims.append(
            InterpretationClaim.create(
                text=candidate.text,
                citation_ids=tuple(
                    source_by_label[label].citation.citation_id
                    for label in candidate.source_labels
                ),
                support_level=candidate.support_level,
            )
        )
    citations = tuple(
        item.citation for item in prompt_sources if item.label in used_labels
    )
    return InterpretationProposal.create(
        question=question_value,
        answer=generated.answer,
        claims=tuple(claims),
        citations=citations,
        interpretation_layer=backend.interpretation_layer,
        producer=backend.backend_id,
        model=backend.model,
        prompt_version=backend.prompt_version,
        generated_at=generated_at,
        retrieval_method=retrieval_method,
        metadata={
            "candidate_source_count": len(prompt_sources),
            "cited_source_count": len(citations),
        },
    )


__all__ = [
    "GeneratedClaim",
    "GeneratedInterpretation",
    "InterpretationBackend",
    "PromptSource",
    "generate_interpretation_proposal",
]
