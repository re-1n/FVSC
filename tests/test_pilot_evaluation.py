from __future__ import annotations

from core.pilot_evaluation import (
    HeldoutDocument,
    chronological_split,
    run_heldout_evaluation,
)


def _document(index: int, parent: str, child: str, extra: str) -> HeldoutDocument:
    return HeldoutDocument(
        source_id=f"daily/{index:02d}.md",
        observed_at=float(index),
        source_revision=f"{index:064x}",
        semantic_input={
            parent: {"weight": 0.9, "contains": {child: 0.8, extra: 0.5}},
            child: {"weight": 0.8, "contains": {}},
            extra: {"weight": 0.7, "contains": {}},
        },
    )


def _corpus() -> list[HeldoutDocument]:
    documents = []
    for index in range(1, 13):
        documents.append(
            _document(
                index,
                "свобода" if index % 2 else "доверие",
                "выбор" if index % 2 else "отношения",
                "ответственность" if index % 3 else "честность",
            )
        )
    return documents


def test_chronological_split_never_uses_future_documents_for_training() -> None:
    train, test = chronological_split(list(reversed(_corpus())), train_fraction=0.75)

    assert len(train) == 9
    assert len(test) == 3
    assert max(document.observed_at for document in train) < min(
        document.observed_at for document in test
    )


def test_heldout_report_is_deterministic_and_bounded() -> None:
    report_a = run_heldout_evaluation(
        _corpus(), train_fraction=0.67, bootstrap_samples=100, seed=7
    )
    report_b = run_heldout_evaluation(
        list(reversed(_corpus())), train_fraction=0.67, bootstrap_samples=100, seed=7
    )

    assert report_a == report_b
    assert report_a["benchmark"] == "fvsc-chronological-heldout-v1"
    assert report_a["train_documents"] == 8
    assert report_a["test_documents"] == 4
    assert 0.0 <= report_a["known_positive_coverage"] <= 1.0
    assert report_a["best_baseline"] in {"direct_graph", "trace_mass", "random"}
    assert report_a["verdict"] in {
        "insufficient_data",
        "promising_added_value",
        "not_predictive",
        "no_demonstrated_added_value",
    }

    for model in report_a["models"].values():
        assert 0.0 <= model["auc"] <= 1.0
        assert 0.0 <= model["average_precision"] <= 1.0
        assert model["pairwise_comparisons"] >= 0

    low, high = report_a["paired_bootstrap_ci95"]
    assert -1.0 <= low <= high <= 1.0


def test_small_corpus_is_reported_as_insufficient_not_overclaimed() -> None:
    report = run_heldout_evaluation(
        _corpus()[:3], train_fraction=0.67, bootstrap_samples=100
    )

    assert report["verdict"] == "insufficient_data"
