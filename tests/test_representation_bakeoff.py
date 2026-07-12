from __future__ import annotations

from core.pilot_evaluation import HeldoutDocument
from core.pilot_runtime import source_revision
from core.representation_bakeoff import (
    BENCHMARK_VERSION,
    RepresentationSuite,
    SparseGraphState,
    run_representation_bakeoff,
)


def _document(index: int, edges: dict[str, dict[str, float]]) -> HeldoutDocument:
    semantic_input = {
        parent: {
            "weight": 1.0,
            "contains": dict(children),
        }
        for parent, children in edges.items()
    }
    text = repr((index, semantic_input))
    return HeldoutDocument(
        source_id=f"fixture:{index}",
        observed_at=float(index),
        semantic_input=semantic_input,
        source_revision=source_revision(text),
    )


def test_sparse_graph_scores_are_bounded_and_directional() -> None:
    documents = [
        _document(
            1,
            {
                "system": {"evidence": 3.0, "context": 1.0},
                "evidence": {"source": 2.0, "context": 1.0},
                "context": {"source": 1.0},
            },
        ),
        _document(
            2,
            {
                "system": {"evidence": 2.0, "context": 2.0},
                "evidence": {"source": 2.0},
                "context": {"source": 1.0},
            },
        ),
    ]
    graph = SparseGraphState.fit(documents)

    assert graph.direct("system", "evidence") == 5.0
    assert 0.0 < graph.conditional("system", "evidence") < 1.0
    assert graph.conditional("system", "evidence") != graph.conditional(
        "evidence", "system"
    )
    assert graph.ppmi("system", "evidence") > 0.0
    assert graph.ppmi("source", "system") == 0.0
    assert 0.0 <= graph.context_inclusion("system", "evidence") <= 1.0


def test_representation_suite_returns_all_registered_scores() -> None:
    train = [
        _document(
            index,
            {
                "reflection": {"attention": 1.0, "memory": 0.8},
                "attention": {"memory": 0.7, "choice": 0.6},
                "memory": {"choice": 0.5},
                "choice": {"responsibility": 0.9},
            },
        )
        for index in range(1, 5)
    ]
    suite = RepresentationSuite.fit(train)
    scores = suite.scores("reflection", "attention")

    assert tuple(scores) == suite.MODEL_NAMES
    assert all(isinstance(value, float) for value in scores.values())
    assert 0.0 <= scores["sparse_context_inclusion"] <= 1.0
    assert 0.0 <= scores["fvsc_density_shape"] <= 1.0


def test_bakeoff_is_deterministic_and_reports_scope() -> None:
    documents = []
    for index in range(12):
        if index < 8:
            edges = {
                "dialogue": {"trust": 1.0, "attention": 0.8},
                "trust": {"attention": 0.7, "cooperation": 0.6},
                "attention": {"cooperation": 0.5},
                "cooperation": {"dialogue": 0.4},
            }
        else:
            edges = {
                "dialogue": {"trust": 1.0, "cooperation": 0.8},
                "trust": {"attention": 0.9},
                "attention": {"dialogue": 0.6},
                "cooperation": {"attention": 0.5},
            }
        documents.append(_document(index + 1, edges))

    first = run_representation_bakeoff(
        documents,
        train_fraction=0.75,
        bootstrap_samples=100,
        max_negatives_per_document=20,
    )
    second = run_representation_bakeoff(
        documents,
        train_fraction=0.75,
        bootstrap_samples=100,
        max_negatives_per_document=20,
    )

    assert first == second
    assert first["benchmark"] == BENCHMARK_VERSION
    assert first["train_documents"] == 9
    assert first["test_documents"] == 3
    assert set(first["models"]) == set(RepresentationSuite.MODEL_NAMES)
    assert first["best_non_density_backend"] in RepresentationSuite.MODEL_NAMES
    assert first["verdict"] in {
        "insufficient_data",
        "density_shape_leads",
        "simpler_backend_preferred",
        "density_shape_competitive",
        "inconclusive",
    }
    assert "canonical_store" in first["decision_scope"]
