from __future__ import annotations

import hashlib
import json

import pytest

from fvsc.ingest import SourceDocument, SourceSpan, judgment_to_evidence_event
from fvsc.semantic import Judgment, judgment_from_event


def _document(text: str = "Свобода не требует подчинения.") -> SourceDocument:
    return SourceDocument.create(
        source_id="telegram/messages/message-10.json",
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=100.0,
        text=text,
        adapter="telegram-json",
        source_kind="owner_reflection",
    )


def test_judgment_event_preserves_exact_relation_and_private_source_reference() -> None:
    document = _document()
    span = SourceSpan.from_document(document, start=0, end=len(document.text))
    judgment = Judgment(
        subject="свобода",
        verb="требовать",
        object="подчинение",
        quality="NEGATIVE",
        negation_scope=True,
        modality_type="FACTUAL",
        interpretation_layer=1,
        defeasible=True,
        inference_chain=["morphology", "shallow-syntax"],
        extraction_confidence=0.75,
    )

    first = judgment_to_evidence_event(judgment, document=document, source_span=span)
    replay = judgment_to_evidence_event(judgment, document=document, source_span=span)

    assert first.event_id == replay.event_id
    assert (first.subject, first.relation, first.object) == (
        "свобода",
        "требовать",
        "подчинение",
    )
    assert first.polarity == -1.0
    assert first.context["source_span"] == span.to_dict()
    assert first.context["source_kind"] == "owner_reflection"
    assert first.provenance["source_assertion_key"] == replay.provenance[
        "source_assertion_key"
    ]
    serialized = json.dumps(first.to_dict(), ensure_ascii=False)
    assert document.text not in serialized
    assert judgment_from_event(first).negation_scope is True


def test_source_span_fails_closed_for_wrong_document_or_offsets() -> None:
    document = _document()
    span = SourceSpan.from_document(document, start=0, end=7)
    changed = _document("Свободы не существует.")

    with pytest.raises(ValueError, match="does not match"):
        span.verify(changed)
    with pytest.raises(ValueError, match="beyond"):
        SourceSpan.from_document(document, start=0, end=len(document.text) + 1)
    with pytest.raises(ValueError, match="empty"):
        SourceSpan.from_document(document, start=1, end=1)
