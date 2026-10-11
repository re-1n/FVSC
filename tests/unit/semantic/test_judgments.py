from __future__ import annotations

from fvsc.evidence import EvidenceEvent
from fvsc.semantic import JUDGMENT_CONTEXT_SCHEMA, Judgment, judgment_from_event
from fvsc.semantic.density import Judgment as DensityJudgment


def test_density_backend_uses_portable_judgment_contract() -> None:
    assert DensityJudgment is Judgment


def test_judgment_context_is_portable_and_omits_raw_text_and_vectors() -> None:
    judgment = Judgment(
        subject="свобода",
        verb="требовать",
        object="ответственность",
        quality="NEGATIVE",
        negation_scope=True,
        modality=0.5,
        modality_type="EPISTEMIC",
        source_text="private diary sentence",
        condition_id="source:10:condition:1",
        condition_role="ANTECEDENT",
        interpretation_layer=1,
        defeasible=True,
        inference_chain=["morphology", "shallow-syntax"],
        clause_type="GENERIC",
        sense_vector=object(),
        perceptual_modalities={"visual", "kinesthetic"},
    )

    context = judgment.to_evidence_context()

    assert context["schema"] == JUDGMENT_CONTEXT_SCHEMA
    assert context["negation_scope"] is True
    assert context["modality_type"] == "EPISTEMIC"
    assert context["perceptual_modalities"] == ["kinesthetic", "visual"]
    assert "source_text" not in context
    assert "sense_vector" not in context
    assert judgment.polarity == -1.0


def test_event_round_trip_preserves_judgment_fields() -> None:
    original = Judgment(
        subject="внимание",
        verb="сканировать",
        object="реальность",
        modality=0.7,
        modality_type="DEONTIC",
        intensity=0.8,
        interpretation_layer=1,
        defeasible=True,
        extraction_confidence=0.75,
        semantic_roles={"AGENT": "внимание", "PATIENT": "реальность"},
        context_tags=["gold:011"],
    )
    event = EvidenceEvent.assertion(
        source_id="telegram/messages/message-11.json",
        source_revision="a" * 64,
        observed_at=100.0,
        recorded_at=100.0,
        subject=original.subject,
        relation=original.verb,
        object=original.object,
        polarity=original.polarity,
        modality=original.modality,
        intensity=original.intensity,
        confidence=original.extraction_confidence,
        interpretation_layer=original.interpretation_layer,
        extractor="test",
        extractor_version="1",
        context={"judgment": original.to_evidence_context()},
    )

    restored = judgment_from_event(event)

    assert (restored.subject, restored.verb, restored.object) == (
        "внимание",
        "сканировать",
        "реальность",
    )
    assert restored.modality_type == "DEONTIC"
    assert restored.defeasible is True
    assert restored.semantic_roles == original.semantic_roles
    assert restored.context_tags == ["gold:011"]
    assert restored.timestamp == 100.0
