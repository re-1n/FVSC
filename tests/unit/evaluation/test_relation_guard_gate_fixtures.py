from __future__ import annotations

from fvsc.evaluation.relation_guard_gate_fixtures import (
    PUBLIC_RELATION_GUARD_GATE_FIXTURES,
    RELATION_ELIGIBLE_LABELS_BY_CASE,
)


def test_relation_guard_gate_has_balanced_positive_and_negative_cases() -> None:
    fixtures = PUBLIC_RELATION_GUARD_GATE_FIXTURES
    assert len(fixtures) == 12
    assert sum(item.should_abstain for item in fixtures) == 6
    for fixture in fixtures:
        eligible = RELATION_ELIGIBLE_LABELS_BY_CASE[fixture.case_id]
        expected = (
            {"R1": (), "R2": ()}
            if fixture.should_abstain
            else {"R1": ("S1",), "R2": ("S2",)}
        )
        assert eligible == expected
