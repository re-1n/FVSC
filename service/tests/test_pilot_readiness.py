from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from service import pilot_router, viz_router
from service.pilot_app import app
from service.pilot_readiness_router import assess_readiness


def _feedback(count: int, *, rating: int = 5, useful: bool = True) -> list[dict]:
    return [
        {"rating": rating, "useful": useful, "query_id": f"q{index}"}
        for index in range(count)
    ]


def _evaluation(verdict: str, *, comparisons: int = 200, coverage: float = 0.8) -> dict:
    return {
        "verdict": verdict,
        "known_positive_coverage": coverage,
        "best_baseline": "direct_graph",
        "fvsc_auc_delta_vs_best_baseline": 0.03,
        "paired_bootstrap_ci95": [0.01, 0.05],
        "models": {
            "fvsc_shape": {
                "auc": 0.7,
                "pairwise_comparisons": comparisons,
            }
        },
    }


def test_readiness_refuses_to_overclaim_before_feedback() -> None:
    result = assess_readiness(
        concept_count=20,
        active_event_count=40,
        feedback=_feedback(5),
        evaluation=_evaluation("promising_added_value"),
    )

    assert result["status"] == "collecting_human_feedback"
    assert result["gates"]["predictive_added_value"] is True
    assert result["gates"]["enough_human_feedback"] is False


def test_readiness_separates_practical_usefulness_from_unique_model_value() -> None:
    result = assess_readiness(
        concept_count=20,
        active_event_count=40,
        feedback=_feedback(30),
        evaluation=_evaluation("no_demonstrated_added_value"),
    )

    assert result["status"] == "practically_useful_without_unique_model_value"
    assert result["gates"]["human_usefulness"] is True
    assert result["gates"]["predictive_added_value"] is False


def test_readiness_marks_promising_only_after_all_gates_pass() -> None:
    result = assess_readiness(
        concept_count=20,
        active_event_count=40,
        feedback=_feedback(30),
        evaluation=_evaluation("promising_added_value"),
    )

    assert result["status"] == "promising_for_extended_pilot"
    assert all(result["gates"].values())


def test_readiness_endpoint_reports_collecting_state(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text(
        "Свобода включает выбор и ответственность. Доверие укрепляет отношения.",
        encoding="utf-8",
    )
    viz_router.configure(vault_path=tmp_path)
    pilot_router._runtime = None
    pilot_router._feedback = []
    pilot_router._loaded_vault = None

    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.post("/pilot/rebuild").status_code == 200
        readiness = client.get("/pilot/readiness")

    assert readiness.status_code == 200
    payload = readiness.json()
    assert payload["status"] == "collecting_human_feedback"
    assert payload["concept_count"] > 0
    assert payload["thresholds"]["minimum_feedback"] == 30
