from __future__ import annotations

from collections import Counter

from fvsc.evaluation.relation_guard_polarity_fixtures import (
    PUBLIC_RELATION_GUARD_POLARITY_FIXTURES,
)


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
