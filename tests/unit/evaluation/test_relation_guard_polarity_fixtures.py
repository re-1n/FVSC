from __future__ import annotations

from collections import Counter

from fvsc.evaluation.relation_guard_polarity_fixtures import (
    PUBLIC_RELATION_GUARD_POLARITY_FIXTURES,
)
from fvsc.evaluation.planned_slot_synthesis import (
    FrozenQuestionPlan,
    PlannedRequirement,
)
from fvsc.evaluation.relation_support_guard import PUBLIC_RELATION_SUPPORT_GUARD
from fvsc.evaluation.synthesis import SyntheticSource


def test_polarity_audit_has_one_positive_and_two_controls_per_relation() -> None:
    fixtures = PUBLIC_RELATION_GUARD_POLARITY_FIXTURES
    assert len(fixtures) == 18
    assert len({item.case_id for item in fixtures}) == 18
    assert Counter(item.relation for item in fixtures) == {
        "accepted": 3,
        "conditional": 3,
        "confirmed": 3,
        "declined": 3,
        "replaced": 3,
        "retained": 3,
    }
    assert Counter(item.contrast for item in fixtures) == {
        "affirmed": 6,
        "modal": 6,
        "negated": 6,
    }
    assert sum(item.should_be_eligible for item in fixtures) == 6


def test_polarity_audit_passes_after_frozen_scope_intervention() -> None:
    for fixture in PUBLIC_RELATION_GUARD_POLARITY_FIXTURES:
        candidates = PUBLIC_RELATION_SUPPORT_GUARD.compile(
            FrozenQuestionPlan(
                fixture.case_id,
                (PlannedRequirement("R1", fixture.requirement),),
            ),
            (SyntheticSource("S1", fixture.source_text),),
        )
        assert (candidates[0].eligible_source_labels == ("S1",)) is (
            fixture.should_be_eligible
        )
