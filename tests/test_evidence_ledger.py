from __future__ import annotations

import pytest

from core.evidence import EvidenceEvent
from core.evidence_ledger import EvidenceLedger


def _assertion(*, object_: str = "ответственность", revision: str = "r1") -> EvidenceEvent:
    return EvidenceEvent.assertion(
        source_id="notes/values.md",
        source_revision=revision,
        observed_at=100.0,
        recorded_at=110.0,
        subject="свобода",
        relation="требует",
        object=object_,
        extractor="test",
        extractor_version="1",
    )


def _retraction(target: EvidenceEvent) -> EvidenceEvent:
    return EvidenceEvent.retraction(
        source_id="notes/values.md",
        source_revision="r2",
        observed_at=200.0,
        recorded_at=210.0,
        target_event_id=target.event_id,
        extractor="user-action",
        extractor_version="1",
    )


def _supersession(target: EvidenceEvent) -> EvidenceEvent:
    return EvidenceEvent.supersession(
        source_id="notes/values.md",
        source_revision="r2",
        observed_at=200.0,
        recorded_at=210.0,
        target_event_id=target.event_id,
        subject="свобода",
        relation="включает",
        object="ответственность",
        extractor="user-action",
        extractor_version="1",
    )


def test_assertion_append_is_idempotent() -> None:
    event = _assertion()
    ledger = EvidenceLedger()

    assert ledger.append(event)
    assert not ledger.append(event)

    assert ledger.event_count == 1
    assert ledger.active_count == 1
    assert ledger.events == (event,)
    assert ledger.active_events == (event,)
    assert ledger.get(event.event_id) == event
    assert ledger.is_active(event.event_id)


def test_retraction_deactivates_without_deleting_history() -> None:
    assertion = _assertion()
    retraction = _retraction(assertion)
    ledger = EvidenceLedger([assertion, retraction])

    assert ledger.event_count == 2
    assert ledger.active_count == 0
    assert ledger.get(assertion.event_id) == assertion
    assert ledger.get(retraction.event_id) == retraction
    assert not ledger.is_active(assertion.event_id)


def test_supersession_replaces_active_statement() -> None:
    assertion = _assertion()
    replacement = _supersession(assertion)
    ledger = EvidenceLedger([assertion, replacement])

    assert not ledger.is_active(assertion.event_id)
    assert ledger.is_active(replacement.event_id)
    assert ledger.active_events == (replacement,)
    assert replacement.relation == "включает"


def test_lifecycle_events_require_existing_active_target() -> None:
    assertion = _assertion()
    retraction = _retraction(assertion)

    with pytest.raises(ValueError, match="does not exist"):
        EvidenceLedger().append(retraction)

    ledger = EvidenceLedger([assertion, retraction])
    second_retraction = EvidenceEvent.retraction(
        source_id="notes/values.md",
        source_revision="r3",
        observed_at=300.0,
        recorded_at=310.0,
        target_event_id=assertion.event_id,
        extractor="user-action",
        extractor_version="1",
    )
    with pytest.raises(ValueError, match="not active"):
        ledger.append(second_retraction)


def test_append_many_is_atomic() -> None:
    original = _assertion()
    valid_second = _assertion(object_="выбор", revision="r2")
    invalid_lifecycle = EvidenceEvent.retraction(
        source_id="missing.md",
        observed_at=400.0,
        recorded_at=410.0,
        target_event_id="0" * 64,
        extractor="user-action",
        extractor_version="1",
    )
    ledger = EvidenceLedger([original])
    digest_before = ledger.digest

    with pytest.raises(ValueError, match="does not exist"):
        ledger.append_many([valid_second, invalid_lifecycle])

    assert ledger.events == (original,)
    assert ledger.digest == digest_before


def test_records_round_trip_preserves_order_state_and_digest() -> None:
    first = _assertion()
    replacement = _supersession(first)
    second = _assertion(object_="выбор", revision="r3")
    ledger = EvidenceLedger([first, replacement, second])

    restored = EvidenceLedger.from_records(ledger.to_records())

    assert restored.events == ledger.events
    assert restored.active_events == ledger.active_events
    assert restored.digest == ledger.digest


def test_active_for_source_filters_materialized_view() -> None:
    first = _assertion()
    other = EvidenceEvent.assertion(
        source_id="notes/other.md",
        observed_at=120.0,
        recorded_at=130.0,
        subject="доверие",
        relation="поддерживает",
        object="отношения",
        extractor="test",
        extractor_version="1",
    )
    ledger = EvidenceLedger([first, other])

    assert ledger.active_for_source("notes/values.md") == (first,)
    assert ledger.active_for_source("notes/other.md") == (other,)
    assert ledger.active_for_source("missing") == ()
