from __future__ import annotations

import numpy as np

from core.container_core import materialize_container_ledger
from core.container_query import ContainerQueryIndex
from core.evidence import EvidenceEvent
from core.evidence_ledger import EvidenceLedger


def _assertion(
    index: int,
    subject: str,
    relation: str,
    object_: str,
    *,
    weight: float = 0.8,
    context: str = "general",
) -> EvidenceEvent:
    return EvidenceEvent.assertion(
        source_id=f"source-{index}",
        source_revision=f"revision-{index}",
        observed_at=float(index),
        recorded_at=float(index),
        extractor="container-query-test",
        extractor_version="1",
        subject=subject,
        relation=relation,
        object=object_,
        intensity=weight,
        confidence=1.0,
        context={"domain": context},
        provenance={"fixture": index, "context": context},
    )


def test_query_index_preserves_context_specific_parallel_embeddings() -> None:
    finance = _assertion(1, "bank", "contains", "asset", context="finance")
    river = _assertion(2, "bank", "contains", "asset", context="river")
    snapshot = materialize_container_ledger(EvidenceLedger([finance, river]))
    index = ContainerQueryIndex(snapshot)

    assert len(snapshot.direct_embeddings("bank", "asset")) == 2
    assert len(index.outgoing("bank")) == 2

    finance_paths = index.explain("bank", "asset", context=("finance",))
    river_paths = index.explain("bank", "asset", context=("river",))

    assert finance_paths[0].evidence_ids == (finance.event_id,)
    assert river_paths[0].evidence_ids == (river.event_id,)
    assert finance_paths[0].strength > finance_paths[1].strength
    assert river_paths[0].strength > river_paths[1].strength
    assert not np.allclose(finance_paths[0].operator, river_paths[0].operator)


def test_explanation_reports_indirect_asymmetric_path_and_provenance() -> None:
    first = _assertion(1, "project", "contains", "architecture", context="design")
    second = _assertion(2, "architecture", "contains", "provenance", context="design")
    snapshot = materialize_container_ledger(EvidenceLedger([first, second]))
    index = ContainerQueryIndex(snapshot)

    paths = index.explain(
        "project",
        "provenance",
        context=("design",),
        max_depth=3,
    )

    assert len(paths) == 1
    assert paths[0].container_ids == ("project", "architecture", "provenance")
    assert len(paths[0].edge_ids) == 2
    assert set(paths[0].evidence_ids) == {first.event_id, second.event_id}
    assert paths[0].strength > 0.0
    assert index.explain("provenance", "project", max_depth=3) == ()

    projection = index.project("project", "provenance", context=("design",), max_depth=3)
    assert projection.path == paths[0]
    assert projection.path_count == 1
    assert not projection.state.is_empty
    assert set(paths[0].evidence_ids).issubset(projection.evidence_ids)


def test_cached_activation_is_cycle_safe_and_counts_each_container_once() -> None:
    events = [
        _assertion(1, "trust", "contains", "dialogue", context="communication"),
        _assertion(2, "dialogue", "contains", "attention", context="communication"),
        _assertion(3, "attention", "contains", "trust", context="reflection"),
    ]
    snapshot = materialize_container_ledger(EvidenceLedger(events))
    index = ContainerQueryIndex(snapshot, branch_limit=8, max_paths_per_target=4)

    first = index.activate("trust", context=("communication",), max_depth=8)
    second = index.activate("trust", context=("communication",), max_depth=8)

    assert first is second
    assert len(first.container_ids) == len(set(first.container_ids))
    assert set(first.container_ids) == {"trust", "dialogue", "attention"}
    assert first.path_count <= index.edge_count
    assert len(first.contribution_ids) == len(set(first.contribution_ids))
    assert not first.state.is_empty


def test_matching_context_changes_structure_and_density_scores() -> None:
    finance = _assertion(1, "bank", "contains", "asset", context="finance")
    river = _assertion(2, "bank", "contains", "shore", context="river")
    snapshot = materialize_container_ledger(EvidenceLedger([finance, river]))
    index = ContainerQueryIndex(snapshot)

    matching = index.structure_score("bank", "asset", context=("finance",))
    mismatching = index.structure_score("bank", "asset", context=("river",))
    assert matching > mismatching

    finance_activation = index.activate("bank", context=("finance",))
    river_activation = index.activate("bank", context=("river",))
    assert not np.allclose(finance_activation.state.shape, river_activation.state.shape)
    assert index.density_score("bank", "asset", context=("finance",)) > 0.0
