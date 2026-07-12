from __future__ import annotations

from core.container_benchmark_cached import (
    BENCHMARK_VERSION,
    CachedContainerSuite,
    run_cached_container_bakeoff,
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
        source_id=f"cached-container-fixture:{index}",
        observed_at=float(index),
        semantic_input=semantic_input,
        source_revision=source_revision(text),
    )


def _documents() -> list[HeldoutDocument]:
    documents: list[HeldoutDocument] = []
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
    return documents


def test_cached_suite_exposes_container_paths_and_all_ablations() -> None:
    suite = CachedContainerSuite.fit(_documents()[:10])
    scores = suite.scores("project", "architecture")

    assert tuple(scores) == suite.MODEL_NAMES
    assert scores["container_structure"] > 0.0
    assert 0.0 <= scores["container_density"] <= 1.0
    assert 0.0 <= scores["container_hybrid"] <= 1.0
    paths = suite.query.explain("project", "provenance", max_depth=2)
    assert paths
    assert paths[0].container_ids == ("project", "architecture", "provenance")
    assert paths[0].evidence_ids


def test_cached_bakeoff_is_deterministic_without_runtime_field() -> None:
    first = run_cached_container_bakeoff(
        _documents(),
        train_fraction=0.75,
        bootstrap_samples=100,
        max_positives_per_document=20,
        max_negatives_per_document=20,
    )
    second = run_cached_container_bakeoff(
        _documents(),
        train_fraction=0.75,
        bootstrap_samples=100,
        max_positives_per_document=20,
        max_negatives_per_document=20,
    )

    assert first == second
    assert first["benchmark"] == BENCHMARK_VERSION
    assert first["train_documents"] == 10
    assert first["test_documents"] == 4
    assert "runtime_seconds" not in first
    assert set(first["models"]) == set(CachedContainerSuite.MODEL_NAMES)
    assert first["container_snapshot"]["query_edges"] > 0
    assert first["resource_bounds"]["max_positives_per_document"] == 20
    assert first["resource_bounds"]["max_negatives_per_document"] == 20
    assert first["verdict"] in {
        "insufficient_data",
        "container_model_leads",
        "simpler_backend_preferred",
        "container_model_competitive",
        "inconclusive",
    }
