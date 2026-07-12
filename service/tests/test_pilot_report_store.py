from __future__ import annotations

from pathlib import Path

from service.pilot_report_store import (
    EVALUATION_REVIEW_PATH,
    load_evaluation_report,
    render_evaluation_markdown,
    save_evaluation_report,
)


def _report() -> dict:
    return {
        "generated_at": 1.0,
        "benchmark": "fvsc-chronological-heldout-v1",
        "verdict": "no_demonstrated_added_value",
        "train_documents": 8,
        "test_documents": 2,
        "evaluated_test_documents": 2,
        "known_positive_coverage": 0.75,
        "positive_pairs_known": 12,
        "positive_pairs_total": 16,
        "best_baseline": "direct_graph",
        "fvsc_auc_delta_vs_best_baseline": 0.01,
        "paired_bootstrap_ci95": [-0.02, 0.04],
        "models": {
            "fvsc_shape": {"auc": 0.65, "average_precision": 0.6, "pairwise_comparisons": 120},
            "direct_graph": {"auc": 0.64, "average_precision": 0.61, "pairwise_comparisons": 120},
            "trace_mass": {"auc": 0.55, "average_precision": 0.5, "pairwise_comparisons": 120},
            "random": {"auc": 0.5, "average_precision": 0.4, "pairwise_comparisons": 120},
        },
        "limitations": ["small pilot"],
    }


def test_evaluation_report_round_trip_and_markdown(tmp_path: Path) -> None:
    report = _report()
    json_path, markdown_path = save_evaluation_report(tmp_path, report)

    assert load_evaluation_report(tmp_path) == report
    assert json_path == tmp_path / ".fvsc" / "heldout-evaluation-latest.json"
    assert markdown_path == tmp_path / EVALUATION_REVIEW_PATH
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "no_demonstrated_added_value" in markdown
    assert "FVSC shape" in markdown
    assert "Direct graph" in markdown
    assert "0.0100" in markdown


def test_markdown_handles_incomplete_report() -> None:
    markdown = render_evaluation_markdown({"verdict": "insufficient_data"})

    assert "insufficient_data" in markdown
    assert "Пока недостаточно" in markdown
