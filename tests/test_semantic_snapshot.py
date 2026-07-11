from __future__ import annotations

import numpy as np
import pytest

from core.evidence import EvidenceEvent
from core.evidence_ledger import EvidenceLedger
from core.materializer import DeterministicEvidenceEncoder, materialize_ledger
from core.semantic_snapshot import (
    ConceptChange,
    SemanticSnapshot,
    SnapshotConcept,
    StateDelta,
    apply_delta,
)
from core.semantic_state import SemanticState


def _base_snapshot() -> SemanticSnapshot:
    event = EvidenceEvent.assertion(
        source_id="a.md",
        observed_at=100.0,
        recorded_at=101.0,
        subject="свобода",
        relation="требует",
        object="ответственность",
        extractor="test",
        extractor_version="1",
        intensity=1.0,
    )
    materialized = materialize_ledger(
        EvidenceLedger([event]),
        encoder=DeterministicEvidenceEncoder(dim=8),
    )
    return SemanticSnapshot.from_materialized(materialized)


def _state(diagonal: list[float], *, mass: float = 1.0) -> SemanticState:
    shape = np.diag(diagonal).astype(float)
    shape /= np.trace(shape)
    return SemanticState(mass=mass, shape=shape, evidence_count=1)


def test_materialized_snapshot_conversion_is_deterministic() -> None:
    first = _base_snapshot()
    second = _base_snapshot()

    assert first.snapshot_id == second.snapshot_id
    assert first.origin.startswith("materializer:")
    assert first.metadata["ledger_digest"]
    assert [concept.term for concept in first.concepts] == sorted(
        concept.term for concept in first.concepts
    )


def test_apply_delta_returns_new_snapshot_without_mutating_base() -> None:
    base = _base_snapshot()
    freedom_before = base.get("свобода")
    assert freedom_before is not None
    before_operator = freedom_before.state.to_operator()

    proposed = _state([0.9, 0.1], mass=3.0)
    delta = StateDelta.create(
        base_snapshot_id=base.snapshot_id,
        operator_id="context-activation",
        operator_version="1",
        changes=[
            ConceptChange(
                term="свобода",
                proposed_state=proposed,
                evidence_ids=("a" * 64,),
                reason="activate work context",
            ),
            ConceptChange(
                term="новый-концепт",
                proposed_state=_state([0.5, 0.5], mass=0.5),
                reason="scenario hypothesis",
            ),
        ],
        confidence=0.7,
        speculative=True,
    )

    result = apply_delta(base, delta)

    assert result.parent_snapshot_id == base.snapshot_id
    assert result.snapshot_id != base.snapshot_id
    assert result.get("новый-концепт") is not None
    changed = result.get("свобода")
    assert changed is not None
    assert changed.state.mass == pytest.approx(3.0)
    assert np.allclose(changed.state.shape, proposed.shape)
    assert np.allclose(freedom_before.state.to_operator(), before_operator)
    assert base.get("новый-концепт") is None
    assert result.metadata["speculative"] is True
    assert result.metadata["delta_id"] == delta.delta_id


def test_delta_can_delete_concept_only_in_new_snapshot() -> None:
    base = _base_snapshot()
    assert base.get("требует") is not None
    delta = StateDelta.create(
        base_snapshot_id=base.snapshot_id,
        operator_id="policy-filter",
        operator_version="1",
        changes=[ConceptChange(term="требует", proposed_state=None, reason="hidden in branch")],
        confidence=1.0,
        speculative=False,
    )

    result = apply_delta(base, delta)

    assert result.get("требует") is None
    assert base.get("требует") is not None


def test_delta_id_is_deterministic_for_same_proposal() -> None:
    base = _base_snapshot()
    kwargs = {
        "base_snapshot_id": base.snapshot_id,
        "operator_id": "test-operator",
        "operator_version": "1",
        "changes": [ConceptChange(term="x", proposed_state=_state([1.0, 0.0]))],
        "confidence": 0.5,
        "speculative": True,
        "metadata": {"seed": 7},
    }

    assert StateDelta.create(**kwargs).delta_id == StateDelta.create(**kwargs).delta_id


def test_apply_rejects_delta_for_other_snapshot() -> None:
    base = _base_snapshot()
    delta = StateDelta.create(
        base_snapshot_id="0" * 64,
        operator_id="test",
        operator_version="1",
        changes=[],
        confidence=1.0,
        speculative=False,
    )

    with pytest.raises(ValueError, match="does not match"):
        apply_delta(base, delta)


def test_snapshots_and_deltas_reject_duplicate_terms() -> None:
    state = _state([0.5, 0.5])
    with pytest.raises(ValueError, match="unique terms"):
        SemanticSnapshot.create(
            concepts=[
                SnapshotConcept(term="x", state=state),
                SnapshotConcept(term="x", state=state),
            ],
            origin="test",
        )

    base = _base_snapshot()
    with pytest.raises(ValueError, match="same term twice"):
        StateDelta.create(
            base_snapshot_id=base.snapshot_id,
            operator_id="test",
            operator_version="1",
            changes=[
                ConceptChange(term="x", proposed_state=state),
                ConceptChange(term="x", proposed_state=None),
            ],
            confidence=1.0,
            speculative=False,
        )


def test_metadata_access_returns_copy() -> None:
    snapshot = SemanticSnapshot.create(
        concepts=[],
        origin="test",
        metadata={"nested": {"value": 1}},
    )

    metadata = snapshot.metadata
    metadata["nested"]["value"] = 2

    assert snapshot.metadata["nested"]["value"] == 1
