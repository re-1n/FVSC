from __future__ import annotations

from fvsc.semantic.containers import materialize_container_ledger
from fvsc.semantic.containers import BoundedContainerTraversal
from fvsc.evidence import EvidenceEvent
from fvsc.evidence import EvidenceLedger


def _assertion(index: int, subject: str, object_: str, *, weight: float) -> EvidenceEvent:
    return EvidenceEvent.assertion(
        source_id=f"source-{index}",
        source_revision=f"revision-{index}",
        observed_at=float(index),
        recorded_at=float(index),
        extractor="container-traversal-test",
        extractor_version="1",
        subject=subject,
        relation="contains",
        object=object_,
        intensity=weight,
        context={"fixture": "aggregation"},
        provenance={"record": index},
    )


def test_traversal_aggregates_repeated_embeddings_and_preserves_provenance() -> None:
    first = _assertion(1, "system", "evidence", weight=0.5)
    second = _assertion(2, "system", "evidence", weight=0.6)
    third = _assertion(3, "evidence", "source", weight=0.7)
    snapshot = materialize_container_ledger(EvidenceLedger([first, second, third]))
    traversal = BoundedContainerTraversal(snapshot)

    outgoing = traversal.outgoing("system")
    assert len(snapshot.direct_embeddings("system", "evidence")) == 2
    assert len(outgoing) == 1
    assert outgoing[0].embedding_ids == tuple(sorted((
        snapshot.direct_embeddings("system", "evidence")[0].embedding_id,
        snapshot.direct_embeddings("system", "evidence")[1].embedding_id,
    )))
    assert set(outgoing[0].evidence_ids) == {first.event_id, second.event_id}
    assert outgoing[0].strength > max(0.5, 0.6)
    assert traversal.structure_score("system", "source", max_depth=2) > 0.0


def test_traversal_branch_limit_is_deterministic() -> None:
    events = [
        _assertion(index, "root", f"child-{index}", weight=index / 20.0)
        for index in range(1, 16)
    ]
    snapshot = materialize_container_ledger(EvidenceLedger(events))
    first = BoundedContainerTraversal(snapshot, branch_limit=5)
    second = BoundedContainerTraversal(snapshot, branch_limit=5)

    assert len(first.outgoing("root")) == 5
    assert [edge.edge_id for edge in first.outgoing("root")] == [
        edge.edge_id for edge in second.outgoing("root")
    ]
    strengths = [edge.strength for edge in first.outgoing("root")]
    assert strengths == sorted(strengths, reverse=True)
