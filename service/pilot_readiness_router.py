"""Evidence-based readiness assessment for the FVSC daily pilot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from .pilot_feedback import feedback_summary
from .pilot_report_store import load_evaluation_report
from .pilot_router import _ensure_loaded


router = APIRouter(prefix="/pilot", tags=["pilot-readiness"])
MIN_FEEDBACK = 30
MIN_USEFUL_RATE = 0.65
MIN_MEAN_RATING = 3.5
MIN_PAIRWISE_COMPARISONS = 100
MIN_KNOWN_POSITIVE_COVERAGE = 0.5


def _feedback_metrics(feedback: list[dict[str, Any]]) -> dict[str, Any]:
    summary = feedback_summary(feedback)
    return {
        "count": summary["count"],
        "history_count": summary["history_count"],
        "mean_rating": summary["mean_rating"],
        "useful_rate": summary["useful_rate"],
    }


def _load_latest_evaluation(vault: Path) -> dict[str, Any] | None:
    return load_evaluation_report(vault)


def assess_readiness(
    *,
    concept_count: int,
    active_event_count: int,
    feedback: list[dict[str, Any]],
    evaluation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Classify pilot state without claiming validity before thresholds are met."""
    feedback_metrics = _feedback_metrics(feedback)
    fvsc_model = (evaluation or {}).get("models", {}).get("fvsc_shape", {})
    comparisons = int(fvsc_model.get("pairwise_comparisons", 0) or 0)
    coverage = float((evaluation or {}).get("known_positive_coverage", 0.0) or 0.0)
    evaluation_verdict = (evaluation or {}).get("verdict")

    gates = {
        "map_available": concept_count > 0 and active_event_count > 0,
        "enough_human_feedback": feedback_metrics["count"] >= MIN_FEEDBACK,
        "human_usefulness": (
            feedback_metrics["count"] >= MIN_FEEDBACK
            and feedback_metrics["useful_rate"] is not None
            and feedback_metrics["useful_rate"] >= MIN_USEFUL_RATE
            and feedback_metrics["mean_rating"] is not None
            and feedback_metrics["mean_rating"] >= MIN_MEAN_RATING
        ),
        "enough_heldout_data": (
            evaluation is not None
            and comparisons >= MIN_PAIRWISE_COMPARISONS
            and coverage >= MIN_KNOWN_POSITIVE_COVERAGE
            and evaluation_verdict != "insufficient_data"
        ),
        "predictive_added_value": evaluation_verdict == "promising_added_value",
    }

    actions: list[str] = []
    if not gates["map_available"]:
        status = "setup_required"
        actions.append("rebuild the pilot ledger from the vault")
    elif not gates["enough_human_feedback"]:
        status = "collecting_human_feedback"
        actions.append(
            f"rate at least {MIN_FEEDBACK - feedback_metrics['count']} more daily-review concepts"
        )
        if evaluation is None:
            actions.append("run the chronological held-out evaluation")
    elif not gates["human_usefulness"]:
        status = "not_practically_useful_yet"
        actions.append("inspect low-rated outputs and revise parser/encoder before expanding features")
    elif not gates["enough_heldout_data"]:
        status = "useful_but_predictive_test_inconclusive"
        actions.append("collect more dated notes and rerun the held-out evaluation")
    elif gates["predictive_added_value"]:
        status = "promising_for_extended_pilot"
        actions.append("freeze the current model and begin a longer blinded comparison")
    else:
        status = "practically_useful_without_unique_model_value"
        actions.append("compare improved contextual encoders against the current simple baselines")

    return {
        "status": status,
        "gates": gates,
        "feedback": feedback_metrics,
        "evaluation": {
            "available": evaluation is not None,
            "verdict": evaluation_verdict,
            "fvsc_auc": fvsc_model.get("auc"),
            "pairwise_comparisons": comparisons,
            "known_positive_coverage": coverage,
            "best_baseline": (evaluation or {}).get("best_baseline"),
            "auc_delta_vs_best_baseline": (evaluation or {}).get(
                "fvsc_auc_delta_vs_best_baseline"
            ),
            "paired_bootstrap_ci95": (evaluation or {}).get("paired_bootstrap_ci95"),
        },
        "thresholds": {
            "minimum_feedback": MIN_FEEDBACK,
            "minimum_useful_rate": MIN_USEFUL_RATE,
            "minimum_mean_rating": MIN_MEAN_RATING,
            "minimum_pairwise_comparisons": MIN_PAIRWISE_COMPARISONS,
            "minimum_known_positive_coverage": MIN_KNOWN_POSITIVE_COVERAGE,
        },
        "next_actions": actions,
    }


@router.get("/readiness")
async def pilot_readiness():
    runtime, feedback, vault = _ensure_loaded()
    result = assess_readiness(
        concept_count=runtime.snapshot.concept_count,
        active_event_count=runtime.ledger.active_count,
        feedback=feedback,
        evaluation=_load_latest_evaluation(vault),
    )
    return {
        "snapshot_id": runtime.snapshot.snapshot_id,
        "concept_count": runtime.snapshot.concept_count,
        "active_event_count": runtime.ledger.active_count,
        **result,
    }
