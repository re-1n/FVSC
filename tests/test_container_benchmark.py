from __future__ import annotations

from core.container_benchmark import (
    BENCHMARK_VERSION,
    ContainerRepresentationSuite,
    run_container_bakeoff,
)
from core.pilot_evaluation import HeldoutDocument
from core.pilot_runtime import source_revision


def _document(index: int, edges: dict[str, dict[str, float]]) -> HeldoutDocument:
    semantic_input = {
        parent: {"weight": 1.0, "contains": dict(children)}
        for parent, children in edges.items()
    }
    text = repr((index, semantic_input))
    return HeldoutDocument(
        source_id=f"container-fixture:{index}",
        observed_at=float(index),
        semantic_input=semantic_input,
        source_revision=source_revision(text),
    )


def test_container_suite_exposes_required_ablations() -> None:
    documents = [
        _document(
            index,
            {
                "system": {"architecture": 1.0, "evidence": 0.8},
                "architecture": {"provenance": 0.9},
                "evidence": {"source": 0.7},
            },
        )
        for index in range(1, 5)
    ]
    suite = ContainerRepresentationSuite.fit(documents)
    scores = suite.scores("system", "architecture")

    assert tuple(scores) == suite.MODEL_NAMES
    assert set(scores) == {
        "direct_graph",
        "conditional_graph",
        "ppmi_graph",
        "fvsc_density_shape",
        "container_structure",
        "container_density",
        "container_hybrid",
        "random",
    }
    assert scores["container_structure"] > 0.0
    assert 0.0 <= scores["container_density"] <= 1.0
    assert 0.0 <= scores["container_hybrid"] <= 1.0


def test_container_bakeoff_is_deterministic_and_reports_decision_scope() -> None:
    documents = []
    for index in range(14):
        if index < 10:
            edges = {
                "project": {"architecture": 1.0, "evidence": 0.9},
                "architecture": {"provenance": 0.8, "runtime": 0.6},
                "evidence": {"source": 0.7},
                "runtime": {"feedback": 0.5},
            }
        else:
            edges = {
                "project": {"architecture": 1.0, "provenance": 0.8},
                "architecture": {"runtime": 0.7},
                "evidence": {"feedback": 0.6},
                "runtime": {"source": 0.5},
            }
        documents.append(_document(index + 1, edges))

    first = run_container_bakeoff(
        documents,
        train_fraction=0.75,
        bootstrap_samples=100,
        max_negatives_per_document=30,
    )
    second = run_container_bakeoff(
        documents,
        train_fraction=0.75,
        bootstrap_samples=100,
        max_negatives_per_document=30,
    )

    assert first == second
    assert first["benchmark"] == BENCHMARK_VERSION
    assert first["train_documents"] == 10
    assert first["test_documents"] == 4
    assert set(first["models"]) == set(ContainerRepresentationSuite.MODEL_NAMES)
    assert first["best_container_backend"] in {
        "container_structure",
        "container_density",
        "container_hybrid",
    }
    assert first["best_non_container_backend"] in {
        "direct_graph",
        "conditional_graph",
        "ppmi_graph",
        "fvsc_density_shape",
        "random",
    }
    assert 0.0 <= first["asymmetric_positive_pair_rate"] <= 1.0
    assert first["container_snapshot"]["containers"] > 0
    assert first["container_snapshot"]["embeddings"] > 0
    assert first["decision_scope"]["container_structure"].startswith("explicit")
    assert first["verdict"] in {
        "insufficient_data",
        "container_model_leads",
        "simpler_backend_preferred",
        "container_model_competitive",
        "inconclusive",
    }
