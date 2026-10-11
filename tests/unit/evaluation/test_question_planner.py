from __future__ import annotations

import pytest

from fvsc.evaluation.question_planner import QuestionOnlyPlan, QuestionPlanStep


def test_question_plan_preserves_dependencies_and_emitted_requirements() -> None:
    plan = QuestionOnlyPlan(
        "Where was the log moved, and why?",
        (
            QuestionPlanStep("S1", "select", "the log", emits_requirement=False),
            QuestionPlanStep("S2", "project", "destination of #1", ("S1",)),
            QuestionPlanStep("S3", "project", "reason for #2", ("S2",)),
        ),
    )
    assert tuple(step.step_id for step in plan.requirements) == ("S2", "S3")


def test_question_plan_rejects_forward_references() -> None:
    with pytest.raises(ValueError, match="earlier"):
        QuestionPlanStep("S1", "project", "reason", ("S2",))


def test_question_plan_requires_contiguous_order() -> None:
    with pytest.raises(ValueError, match="contiguous"):
        QuestionOnlyPlan(
            "Question?",
            (QuestionPlanStep("S2", "select", "requested fact"),),
        )
