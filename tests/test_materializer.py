from __future__ import annotations

import numpy as np
import pytest

from core.evidence import EvidenceEvent
from core.evidence_ledger import EvidenceLedger
from core.materializer import DeterministicEvidenceEncoder, materialize_ledger


def _assertion(
    *,
    source_id: str,
    subject: str = "свобода",
    relation: str = "требует",
    object_: str = "ответственность",
    observed_at: float = 100.0,
) -> EvidenceEvent:
    return EvidenceEvent.assertion(
        source_id=source_id,
        observed_at=observed_at,
        recorded_at=observed_at + 1.0,
        subject=subject,
        relation=relation,
        object=object_,
        extractor="test",
        extractor_version="1",
        modality=1.0,
        intensity=1.0,
        confidence=1.0,
    )


def test_materializer_separates_expected_mass_from_normalized_shape() -> None:
    event = _assertion(source_id="a.md")
    snapshot = materialize_ledger(
        EvidenceLedger([event]),
        encoder=DeterministicEvidenceEncoder(dim=8),
    )

    subject = snapshot.get("свобода")
    object_state = snapshot.get("ответственность")
    relation = snapshot.get("требует")

    assert subject is not None and object_state is not None and relation is not None
    assert subject.state.mass == pytest.approx(1.0)
    assert object_state.state.mass == pytest.approx(0.5)
    assert relation.state.mass == pytest.approx(0.2)
    assert np.trace(subject.state.shape) == pytest.approx(1.0)
    assert subject.evidence_ids == (event.event_id,)
    assert subject.state.evidence_count == 1


def test_materialization_is_deterministic_on_replay() -> None:
    events = [
        _assertion(source_id="a.md"),
        _assertion(
            source_id="b.md",
            subject="доверие",
            relation="укрепляет",
            object_="отношения",
            observed_at=200.0,
        ),
    ]
    ledger = EvidenceLedger(events)
    replayed = EvidenceLedger.from_records(ledger.to_records())
    encoder = DeterministicEvidenceEncoder(dim=16)

    first = materialize_ledger(ledger, encoder=encoder)
    second = materialize_ledger(replayed, encoder=encoder)

    assert first.ledger_digest == second.ledger_digest
    assert first.state_digest == second.state_digest
    assert first.snapshot_id == second.snapshot_id
    assert first.concept_count == second.concept_count
    for concept in first.concepts:
        other = second.get(concept.term)
        assert other is not None
        assert concept.state.mass == pytest.approx(other.state.mass)
        assert np.array_equal(concept.state.shape, other.state.shape)
        assert concept.evidence_ids == other.evidence_ids


def test_retraction_removes_event_from_materialized_state_not_history() -> None:
    assertion = _assertion(source_id="a.md")
    retraction = EvidenceEvent.retraction(
        source_id="a.md",
        observed_at=300.0,
        recorded_at=301.0,
        target_event_id=assertion.event_id,
        extractor="user-action",
        extractor_version="1",
    )
    ledger = EvidenceLedger([assertion, retraction])

    snapshot = materialize_ledger(ledger, encoder=DeterministicEvidenceEncoder(dim=8))

    assert ledger.event_count == 2
    assert ledger.active_count == 0
    assert snapshot.concept_count == 0


def test_supersession_materializes_only_replacement_statement() -> None:
    original = _assertion(source_id="a.md")
    replacement = EvidenceEvent.supersession(
        source_id="a.md",
        observed_at=300.0,
        recorded_at=301.0,
        target_event_id=original.event_id,
        subject="свобода",
        relation="включает",
        object="ответственность",
        extractor="user-action",
        extractor_version="1",
        intensity=1.0,
    )
    ledger = EvidenceLedger([original, replacement])

    snapshot = materialize_ledger(ledger, encoder=DeterministicEvidenceEncoder(dim=8))

    assert snapshot.get("требует") is None
    assert snapshot.get("включает") is not None
    freedom = snapshot.get("свобода")
    assert freedom is not None
    assert freedom.evidence_ids == (replacement.event_id,)


def test_state_digest_is_independent_of_append_order_but_snapshot_tracks_history() -> None:
    first = _assertion(source_id="a.md", observed_at=100.0)
    second = _assertion(
        source_id="b.md",
        subject="доверие",
        relation="укрепляет",
        object_="отношения",
        observed_at=200.0,
    )
    encoder = DeterministicEvidenceEncoder(dim=8)

    ordered = materialize_ledger(EvidenceLedger([first, second]), encoder=encoder)
    reversed_order = materialize_ledger(EvidenceLedger([second, first]), encoder=encoder)

    assert ordered.state_digest == reversed_order.state_digest
    assert ordered.ledger_digest != reversed_order.ledger_digest
    assert ordered.snapshot_id != reversed_order.snapshot_id


def test_encoder_can_exclude_policy_terms_without_affecting_other_concepts() -> None:
    event = _assertion(source_id="a.md")
    encoder = DeterministicEvidenceEncoder(dim=8, excluded_terms=frozenset({"требует"}))

    snapshot = materialize_ledger(EvidenceLedger([event]), encoder=encoder)

    assert snapshot.get("требует") is None
    assert snapshot.get("свобода") is not None
    assert snapshot.get("ответственность") is not None
