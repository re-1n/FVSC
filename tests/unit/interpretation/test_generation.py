from __future__ import annotations

import hashlib
import json

import pytest

from fvsc.ingest import SourceDocument
from fvsc.interpretation import (
    GeneratedClaim,
    GeneratedInterpretation,
    PromptSource,
    generate_interpretation_proposal,
)


def _document(source_id: str, text: str) -> SourceDocument:
    return SourceDocument.create(
        source_id=source_id,
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=1.0,
        text=text,
        adapter="test",
        source_kind="owner_reflection",
        raw_chars=len(text),
    )


class _Backend:
    backend_id = "test.interpreter"
    model = "fake"
    prompt_version = "1"
    interpretation_layer = 3

    def __init__(self, labels: tuple[str, ...] = ("S1",)) -> None:
        self.labels = labels
        self.seen_sources: tuple[PromptSource, ...] = ()

    def generate(self, question, sources):
        self.seen_sources = sources
        return GeneratedInterpretation(
            answer="Паразит здесь описывает захват внимания.",
            claims=(
                GeneratedClaim(
                    text="Образ связан с захватом внимания.",
                    source_labels=self.labels,
                ),
            ),
        )


def test_generation_resolves_transient_labels_to_exact_source_citations() -> None:
    first = _document("message-334", "Паразиты превращают внимание в чужой ресурс.")
    second = _document("message-335", "Ресурс перенаправляется вовне.")
    backend = _Backend(("S1", "S2"))

    proposal = generate_interpretation_proposal(
        question="Какую роль играют паразиты?",
        documents=(first, second),
        backend=backend,
        generated_at=2.0,
    )

    assert tuple(item.label for item in backend.seen_sources) == ("S1", "S2")
    assert all(
        item.attribution.transport_author_role == "unknown"
        for item in backend.seen_sources
    )
    assert proposal.cited_source_ids == ("message-334", "message-335")
    assert proposal.interpretation_layer == 3
    assert proposal.defeasible is True
    for citation, document in zip(proposal.citations, (first, second), strict=True):
        citation.verify(document)

    serialized = json.dumps(proposal.to_dict(), ensure_ascii=False)
    assert first.text not in serialized
    assert second.text not in serialized


def test_backend_cannot_invent_source_identifiers() -> None:
    backend = _Backend(("S9",))

    with pytest.raises(ValueError, match="unknown source labels"):
        generate_interpretation_proposal(
            question="Question",
            documents=(_document("message-1", "Source text."),),
            backend=backend,
            generated_at=2.0,
        )


def test_free_generation_remains_visible_and_uncited() -> None:
    class FreeBackend(_Backend):
        def generate(self, question, sources):
            return GeneratedInterpretation(
                answer="Это лишь гипотеза.",
                claims=(
                    GeneratedClaim(
                        text="Это лишь гипотеза.",
                        source_labels=(),
                        support_level="free_generation",
                    ),
                ),
            )

    proposal = generate_interpretation_proposal(
        question="Question",
        documents=(_document("message-1", "Source text."),),
        backend=FreeBackend(),
        generated_at=2.0,
    )

    assert proposal.support_level == "free_generation"
    assert proposal.citations == ()


def test_generated_claim_support_labels_fail_closed() -> None:
    with pytest.raises(ValueError, match="require source citations"):
        GeneratedClaim(text="Claim", source_labels=())
    with pytest.raises(ValueError, match="cannot carry"):
        GeneratedClaim(
            text="Claim",
            source_labels=("S1",),
            support_level="free_generation",
        )
