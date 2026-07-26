from __future__ import annotations

from fvsc.evaluation.boundary_slot_gate_fixtures import (
    BOUNDARY_PLAN_BY_CASE,
    PUBLIC_BOUNDARY_SLOT_GATE_FIXTURES,
)


def test_boundary_slot_gate_is_new_complete_and_plan_bound() -> None:
    assert len(PUBLIC_BOUNDARY_SLOT_GATE_FIXTURES) == 12
    assert len(BOUNDARY_PLAN_BY_CASE) == 12
    assert sum(item.should_abstain for item in PUBLIC_BOUNDARY_SLOT_GATE_FIXTURES) == 2
    assert set(BOUNDARY_PLAN_BY_CASE) == {
        item.case_id for item in PUBLIC_BOUNDARY_SLOT_GATE_FIXTURES
    }
    assert all(
        tuple(requirement.requirement_id for requirement in plan.requirements)
        == ("R1", "R2")
        for plan in BOUNDARY_PLAN_BY_CASE.values()
    )
