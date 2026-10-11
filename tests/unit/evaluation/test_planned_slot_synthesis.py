from __future__ import annotations

import pytest

from fvsc.evaluation.planned_slot_fixtures import PUBLIC_FROZEN_QUESTION_PLANS
from fvsc.evaluation.planned_slot_synthesis import (
    FilledRequirementSlot,
    FrozenQuestionPlan,
    PlannedRequirement,
    PlannedSlotOutput,
    normalize_empty_claim_sentinel,
    render_planned_slot_answer,
)
from fvsc.interpretation import GeneratedClaim


def test_planned_slots_render_only_supported_claims() -> None:
    plan = FrozenQuestionPlan(
        "case",
        (PlannedRequirement("R1", "decision"), PlannedRequirement("R2", "reason")),
    )
    output = PlannedSlotOutput(
        plan,
        (
            FilledRequirementSlot(
                "R1", "supported", GeneratedClaim("Moved.", ("S1",))
            ),
            FilledRequirementSlot("R2", "unsupported", None),
        ),
    )
    assert output.status == "partial"
    assert render_planned_slot_answer(output) == "PARTIAL_CONTEXT: Moved."


def test_planned_slots_must_exactly_match_input_plan() -> None:
    plan = FrozenQuestionPlan(
        "case",
        (PlannedRequirement("R1", "first"), PlannedRequirement("R2", "second")),
    )
    with pytest.raises(ValueError, match="exactly match"):
        PlannedSlotOutput(
            plan,
            (FilledRequirementSlot("R2", "unsupported", None),),
        )


def test_frozen_plans_cover_each_heldout_case_without_source_answers() -> None:
    assert len(PUBLIC_FROZEN_QUESTION_PLANS) == 12
    assert len({item.case_id for item in PUBLIC_FROZEN_QUESTION_PLANS}) == 12
    assert all(1 <= len(item.requirements) <= 2 for item in PUBLIC_FROZEN_QUESTION_PLANS)


def test_only_exact_proposition_free_unsupported_sentinel_normalizes_to_none() -> None:
    sentinel = {
        "text": None,
        "citations": [],
        "support_level": "evidence_bound",
    }
    assert normalize_empty_claim_sentinel("unsupported", sentinel) is None
    assert normalize_empty_claim_sentinel("supported", sentinel) == sentinel
    unsafe = sentinel | {"text": "Maybe selected."}
    assert normalize_empty_claim_sentinel("unsupported", unsafe) == unsafe
