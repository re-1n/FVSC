from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from core.evidence import EvidenceEvent


ASSERTION_ARGS = {
    "source_id": "notes/values.md",
    "source_revision": "sha256:revision-1",
    "observed_at": 1710000000.0,
    "subject": "свобода",
    "relation": "требует",
    "object": "ответственность",
    "extractor": "fvsc-parser",
    "extractor_version": "1.0.0",
    "polarity": 1.0,
    "modality": 0.9,
    "intensity": 0.8,
    "confidence": 0.85,
    "interpretation_layer": 0,
    "context": {"register": "reflective", "topics": ["ethics", "agency"]},
    "provenance": {"chunk_id": "notes/values.md:3", "span": [10, 42]},
}


def test_assertion_id_is_deterministic_and_ignores_recording_time() -> None:
    first = EvidenceEvent.assertion(recorded_at=1710000010.0, **ASSERTION_ARGS)
    replay = EvidenceEvent.assertion(recorded_at=1810000010.0, **ASSERTION_ARGS)

    assert first.event_id == replay.event_id
    assert first.recorded_at != replay.recorded_at
    assert len(first.event_id) == 64
    assert first.context == ASSERTION_ARGS["context"]
    assert first.provenance == ASSERTION_ARGS["provenance"]


def test_assertion_round_trips_through_json_compatible_dict() -> None:
    event = EvidenceEvent.assertion(recorded_at=1710000010.0, **ASSERTION_ARGS)

    restored = EvidenceEvent.from_dict(event.to_dict())

    assert restored == event
    assert restored.to_dict() == event.to_dict()


def test_context_access_returns_a_copy() -> None:
    event = EvidenceEvent.assertion(recorded_at=1710000010.0, **ASSERTION_ARGS)

    context = event.context
    context["register"] = "mutated"

    assert event.context["register"] == "reflective"


def test_events_are_frozen() -> None:
    event = EvidenceEvent.assertion(recorded_at=1710000010.0, **ASSERTION_ARGS)

    with pytest.raises(FrozenInstanceError):
        event.subject = "другое"  # type: ignore[misc]


def test_retraction_targets_an_existing_event_without_replacement_payload() -> None:
    assertion = EvidenceEvent.assertion(recorded_at=1710000010.0, **ASSERTION_ARGS)
    retraction = EvidenceEvent.retraction(
        source_id="notes/values.md",
        source_revision="sha256:revision-2",
        observed_at=1710001000.0,
        recorded_at=1710001010.0,
        target_event_id=assertion.event_id,
        extractor="user-action",
        extractor_version="1.0.0",
        provenance={"reason": "source paragraph deleted"},
    )

    assert retraction.event_kind == "retraction"
    assert retraction.target_event_id == assertion.event_id
    assert retraction.subject is None
    assert retraction.relation is None
    assert retraction.object is None


def test_supersession_contains_replacement_statement() -> None:
    assertion = EvidenceEvent.assertion(recorded_at=1710000010.0, **ASSERTION_ARGS)
    supersession = EvidenceEvent.supersession(
        source_id="notes/values.md",
        source_revision="sha256:revision-2",
        observed_at=1710001000.0,
        recorded_at=1710001010.0,
        target_event_id=assertion.event_id,
        subject="свобода",
        relation="включает",
        object="ответственность",
        extractor="user-action",
        extractor_version="1.0.0",
    )

    assert supersession.event_kind == "supersession"
    assert supersession.target_event_id == assertion.event_id
    assert supersession.relation == "включает"


def test_tampered_payload_is_rejected() -> None:
    event = EvidenceEvent.assertion(recorded_at=1710000010.0, **ASSERTION_ARGS)
    tampered = event.to_dict()
    tampered["object"] = "подчинение"

    with pytest.raises(ValueError, match="event_id"):
        EvidenceEvent.from_dict(tampered)


def test_event_kind_payload_rules_are_enforced() -> None:
    with pytest.raises(ValueError, match="require subject"):
        EvidenceEvent.assertion(
            source_id="source",
            observed_at=1.0,
            extractor="parser",
            extractor_version="1",
        )

    with pytest.raises(ValueError, match="target_event_id"):
        EvidenceEvent.retraction(
            source_id="source",
            observed_at=1.0,
            extractor="parser",
            extractor_version="1",
        )


def test_numeric_and_json_metadata_are_validated() -> None:
    with pytest.raises(ValueError, match="confidence"):
        EvidenceEvent.assertion(
            **{**ASSERTION_ARGS, "confidence": 1.5},
        )
    with pytest.raises(ValueError, match="interpretation_layer"):
        EvidenceEvent.assertion(
            **{**ASSERTION_ARGS, "interpretation_layer": 1.5},
        )
    with pytest.raises(ValueError, match="JSON"):
        EvidenceEvent.assertion(
            **{**ASSERTION_ARGS, "context": {"bad": object()}},
        )
