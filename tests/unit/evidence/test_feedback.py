from __future__ import annotations

import pytest

from fvsc.evidence import (
    EvidenceEvent,
    EvidenceLedger,
    FeedbackState,
    FVSC_OWNER_FEEDBACK_RELATION,
    create_owner_feedback,
)


def _target(object_: str = "ответственность") -> EvidenceEvent:
    return EvidenceEvent.assertion(
        source_id="note.md",
        source_revision="a" * 64,
        observed_at=1.0,
        recorded_at=1.0,
        subject="свобода",
        relation="требовать",
        object=object_,
        interpretation_layer=1,
        extractor="fvsc.ingest.judgment",
        extractor_version="1",
        context={
            "derivation": "linguistic-judgment",
            "source_kind": "owner_reflection",
            "judgment": {"confirmation_status": "unreviewed"},
        },
    )


def test_feedback_is_separate_append_only_evidence_and_latest_decision_wins() -> None:
    target = _target()
    ledger = EvidenceLedger([target])
    confirmed = create_owner_feedback(
        ledger,
        target_event_id=target.event_id,
        action="confirm",
        observed_at=2.0,
        recorded_at=2.0,
    )
    ledger.append(confirmed)
    rejected = create_owner_feedback(
        ledger,
        target_event_id=target.event_id,
        action="reject",
        observed_at=3.0,
        recorded_at=3.0,
    )
    ledger.append(rejected)

    state = FeedbackState.from_ledger(ledger)

    assert ledger.is_active(target.event_id)
    assert confirmed.relation == FVSC_OWNER_FEEDBACK_RELATION
    assert state.confirmation_status_for(target.event_id) == "rejected"
    assert state.decision_for(target.event_id).feedback_event_id == rejected.event_id


def test_contextualization_requires_tags_and_does_not_store_free_text() -> None:
    target = _target()
    ledger = EvidenceLedger([target])

    with pytest.raises(ValueError, match="requires"):
        create_owner_feedback(
            ledger,
            target_event_id=target.event_id,
            action="contextualize",
            observed_at=2.0,
        )

    event = create_owner_feedback(
        ledger,
        target_event_id=target.event_id,
        action="contextualize",
        observed_at=2.0,
        recorded_at=2.0,
        context_tags=["dream", "private", "dream"],
    )
    ledger.append(event)
    state = FeedbackState.from_ledger(ledger)

    assert state.confirmation_status_for(target.event_id) == "contextualized"
    assert state.context_tags_for(target.event_id) == ("dream", "private")


def test_feedback_rejects_unknown_targets_and_invalid_action() -> None:
    target = _target()
    ledger = EvidenceLedger([target])
    with pytest.raises(ValueError, match="does not exist"):
        create_owner_feedback(
            ledger,
            target_event_id="0" * 64,
            action="confirm",
            observed_at=2.0,
        )
    with pytest.raises(ValueError, match="unknown feedback action"):
        create_owner_feedback(
            ledger,
            target_event_id=target.event_id,
            action="erase",  # type: ignore[arg-type]
            observed_at=2.0,
        )
