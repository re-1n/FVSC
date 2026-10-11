from __future__ import annotations

import pytest

from fvsc.evaluation.answer_slot_boundaries import (
    AmbiguousAnswerSlotBoundary,
    compile_answer_slot_boundaries,
    to_frozen_question_plan,
)
from fvsc.evaluation.answer_slot_gate_fixtures import (
    PUBLIC_ANSWER_SLOT_GATE_FIXTURES,
)


@pytest.mark.parametrize("fixture", PUBLIC_ANSWER_SLOT_GATE_FIXTURES)
def test_heldout_answer_slot_boundaries_are_exact(fixture) -> None:
    plan = compile_answer_slot_boundaries(fixture.question)
    assert plan.boundary_kind == fixture.boundary_kind
    assert tuple(slot.role for slot in plan.slots) == fixture.expected_roles
    assert tuple(slot.slot_id for slot in plan.slots) == ("R1", "R2")


@pytest.mark.parametrize(
    "question",
    (
        "Which insulation material was selected?",
        "What caused the network interruption?",
        "Summarize the plan.",
        "What changed?",
    ),
)
def test_unregistered_or_single_slot_questions_fail_closed(question: str) -> None:
    with pytest.raises(AmbiguousAnswerSlotBoundary, match="registered"):
        compile_answer_slot_boundaries(question)


def test_question_normalization_does_not_change_slot_boundaries() -> None:
    plan = compile_answer_slot_boundaries(
        "  Where   was the emergency stock moved, and why?  "
    )
    assert tuple(slot.role for slot in plan.slots) == ("destination", "reason")


def test_boundary_plan_adapts_to_existing_planned_slot_contract() -> None:
    boundary = compile_answer_slot_boundaries(
        "How did the workshop access policy change?"
    )
    frozen = to_frozen_question_plan("public-case", boundary)
    assert frozen.case_id == "public-case"
    assert tuple(item.requirement_id for item in frozen.requirements) == ("R1", "R2")
    assert "former state" in frozen.requirements[0].description
