from __future__ import annotations

from fvsc.evaluation.referent_slot_gate_fixtures import (
    PUBLIC_REFERENT_SLOT_GATE_FIXTURES,
    REFERENT_PLAN_BY_CASE,
)


def test_referent_gate_has_six_positive_and_two_negative_frozen_cases() -> None:
    assert len(PUBLIC_REFERENT_SLOT_GATE_FIXTURES) == 8
    assert sum(item.should_abstain for item in PUBLIC_REFERENT_SLOT_GATE_FIXTURES) == 2
    assert set(REFERENT_PLAN_BY_CASE) == {
        fixture.case_id for fixture in PUBLIC_REFERENT_SLOT_GATE_FIXTURES
    }
    assert all(
        len(plan.requirements) == 2 for plan in REFERENT_PLAN_BY_CASE.values()
    )
