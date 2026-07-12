from __future__ import annotations

import numpy as np

from core.container_core import CONTAINER_CORE_VERSION, materialize_container_ledger
from core.evidence import EvidenceEvent
from core.evidence_ledger import EvidenceLedger


def _assertion(
    index: int,
    subject: str,
    relation: str,
    object_: str,
    *,
    intensity: float = 1.0,
    polarity: float = 1.0,
    context: dict | None = None,
) -> EvidenceEvent:
    return EvidenceEvent.assertion(
        source_id=f"source-{index}",
        source_revision=f"revision-{index}",
        observed_at=float(index),
        recorded_at=float(index),
        extractor="container-test",
        extractor_version="1",
        subject=subject,
        relation=relation,
        object=object_,
        intensity=intensity,
        polarity=polarity,
        context=context or {},
        provenance={"fixture": index},
    )


def test_mutual_embeddings_remain_independent_and_asymmetric() -> None:
    forward = _assertion(
        1,
        "trust",
        "contains",
        "vulnerability",
        intensity=0.8,
        context={"domain": "intimacy"},
    )
    reverse = _assertion(
        2,
        "vulnerability",
        "enables",
        "trust",
        intensity=0.4,
        context={"domain": "risk"},
    )
    snapshot = materialize_container_ledger(EvidenceLedger([forward, reverse]))

    assert snapshot.version == CONTAINER_CORE_VERSION
    assert len(snapshot.direct_embeddings("trust", "vulnerability")) == 1
    assert len(snapshot.direct_embeddings("vulnerability", "trust")) == 1
    assert snapshot.structure_score("trust", "vulnerability") > snapshot.structure_score(
        "vulnerability", "trust"
    )
    first = snapshot.direct_embeddings("trust", "vulnerability")[0]
    second = snapshot.direct_embeddings("vulnerability", "trust")[0]
    assert first.role == "contains"
    assert second.role == "enables"
    assert not np.allclose(first.operator, second.operator.T)


def test_recursive_activation_is_context_sensitive_cycle_safe_and_deduplicated() -> None:
    events = [
        _assertion(
            1,
            "trust",
            "contains",
            "vulnerability",
            intensity=0.8,
            context={"domain": "intimacy"},
        ),
        _assertion(
            2,
            "trust",
            "contains",
            "dialogue",
            intensity=0.9,
            context={"domain": "communication"},
        ),
        _assertion(
            3,
            "dialogue",
            "supports",
            "attention",
            intensity=0.7,
            context={"domain": "communication"},
        ),
        _assertion(
            4,
            "attention",
            "supports",
            "trust",
            intensity=0.6,
            context={"domain": "reflection"},
        ),
    ]
    snapshot = materialize_container_ledger(EvidenceLedger(events))

    intimacy = snapshot.activate("trust", context=("intimacy",), max_depth=6)
    communication = snapshot.activate("trust", context=("communication",), max_depth=6)

    assert intimacy.path_count <= snapshot.embedding_count
    assert communication.path_count <= snapshot.embedding_count
    assert len(intimacy.contribution_ids) == len(set(intimacy.contribution_ids))
    assert len(communication.contribution_ids) == len(set(communication.contribution_ids))
    assert len(intimacy.activated_container_ids) <= snapshot.container_count
    assert not np.allclose(intimacy.state.shape, communication.state.shape)


def test_recursive_projection_finds_indirect_containment_without_inventing_reverse() -> None:
    events = [
        _assertion(1, "project", "contains", "architecture", intensity=0.9),
        _assertion(2, "architecture", "contains", "provenance", intensity=0.8),
    ]
    snapshot = materialize_container_ledger(EvidenceLedger(events))

    assert snapshot.direct_embeddings("project", "provenance") == ()
    assert snapshot.structure_score("project", "provenance", max_depth=3) > 0.0
    assert snapshot.structure_score("provenance", "project", max_depth=3) == 0.0
    projection = snapshot.project("project", "provenance", max_depth=3)
    assert projection.path_count == 1
    assert not projection.state.is_empty
    assert snapshot.density_score("project", "provenance", max_depth=3) > 0.0


def test_retracted_evidence_is_absent_from_container_snapshot() -> None:
    assertion = _assertion(1, "trust", "contains", "dialogue")
    retraction = EvidenceEvent.retraction(
        source_id="source-1",
        source_revision="revision-2",
        observed_at=2.0,
        recorded_at=2.0,
        extractor="container-test",
        extractor_version="1",
        target_event_id=assertion.event_id,
        context={"reason": "fixture"},
        provenance={"fixture": 2},
    )
    snapshot = materialize_container_ledger(EvidenceLedger([assertion, retraction]))

    assert snapshot.container_count == 0
    assert snapshot.embedding_count == 0


def test_negative_evidence_does_not_create_positive_containment_mass() -> None:
    event = _assertion(
        1,
        "trust",
        "excludes",
        "deception",
        intensity=0.9,
        polarity=-1.0,
    )
    snapshot = materialize_container_ledger(EvidenceLedger([event]))

    assert snapshot.embedding_count == 1
    assert snapshot.direct_embeddings("trust", "deception")[0].polarity == -1.0
    assert snapshot.structure_score("trust", "deception") == 0.0
    assert snapshot.density_score("trust", "deception") == 0.0


def test_materialization_is_semantically_order_independent_for_assertions() -> None:
    events = [
        _assertion(1, "system", "contains", "evidence", intensity=0.9),
        _assertion(2, "evidence", "contains", "source", intensity=0.8),
        _assertion(3, "system", "contains", "context", intensity=0.7),
    ]
    first = materialize_container_ledger(EvidenceLedger(events))
    second = materialize_container_ledger(EvidenceLedger(list(reversed(events))))

    assert [item.container_id for item in first.containers] == [
        item.container_id for item in second.containers
    ]
    assert [item.embedding_id for item in first.embeddings] == [
        item.embedding_id for item in second.embeddings
    ]
    for container in first.containers:
        other = second.get(container.container_id)
        assert other is not None
        assert np.allclose(container.local_state.shape, other.local_state.shape)
        assert container.local_state.mass == other.local_state.mass
