from __future__ import annotations

import numpy as np

from core.container_materializer_fast import (
    FAST_CONTAINER_VERSION,
    materialize_fast_container_ledger,
    signed_permutation_operator,
)
from core.evidence import EvidenceEvent
from core.evidence_ledger import EvidenceLedger


def _event(index: int, subject: str, relation: str, object_: str, context: str) -> EvidenceEvent:
    return EvidenceEvent.assertion(
        source_id=f"source-{index}",
        source_revision=f"revision-{index}",
        observed_at=float(index),
        recorded_at=float(index),
        extractor="fast-container-test",
        extractor_version="1",
        subject=subject,
        relation=relation,
        object=object_,
        intensity=0.8,
        confidence=0.9,
        context={"domain": context},
        provenance={"fixture": index},
    )


def test_signed_permutation_operator_is_orthogonal_and_deterministic() -> None:
    first = signed_permutation_operator("a", "b", "contains", ("work",), 32)
    second = signed_permutation_operator("a", "b", "contains", ("work",), 32)
    reverse = signed_permutation_operator("b", "a", "contains", ("work",), 32)

    assert np.array_equal(first, second)
    assert np.allclose(first @ first.T, np.eye(32))
    assert not np.array_equal(first, reverse)
    assert not first.flags.writeable


def test_fast_materializer_preserves_explicit_container_contracts() -> None:
    forward = _event(1, "trust", "contains", "vulnerability", "intimacy")
    reverse = _event(2, "vulnerability", "enables", "trust", "risk")
    snapshot = materialize_fast_container_ledger(EvidenceLedger([forward, reverse]))

    assert snapshot.version == FAST_CONTAINER_VERSION
    assert snapshot.container_count >= 3
    assert snapshot.embedding_count == 2
    assert len(snapshot.direct_embeddings("trust", "vulnerability")) == 1
    assert len(snapshot.direct_embeddings("vulnerability", "trust")) == 1
    assert snapshot.structure_score("trust", "vulnerability") > 0.0
    assert snapshot.structure_score("trust", "missing") == 0.0
    assert snapshot.direct_embeddings("trust", "vulnerability")[0].evidence_ids == (
        forward.event_id,
    )


def test_fast_materialization_is_semantically_order_independent() -> None:
    events = [
        _event(1, "project", "contains", "architecture", "design"),
        _event(2, "architecture", "contains", "provenance", "design"),
        _event(3, "project", "contains", "evidence", "audit"),
    ]
    first = materialize_fast_container_ledger(EvidenceLedger(events))
    second = materialize_fast_container_ledger(EvidenceLedger(list(reversed(events))))

    # Append-only ledger identity is history-order sensitive, while the active semantic
    # projection is deterministic for the same assertion set.
    assert first.ledger_digest != second.ledger_digest
    assert first.snapshot_id != second.snapshot_id
    assert [item.embedding_id for item in first.embeddings] == [
        item.embedding_id for item in second.embeddings
    ]
    assert [item.container_id for item in first.containers] == [
        item.container_id for item in second.containers
    ]
    for container in first.containers:
        other = second.get(container.container_id)
        assert other is not None
        assert np.allclose(container.local_state.shape, other.local_state.shape)
        assert container.local_state.mass == other.local_state.mass
