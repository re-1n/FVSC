from __future__ import annotations

from collections import Counter

from fvsc.evaluation.relation_guard_attribution_fixtures import (
    PUBLIC_RELATION_GUARD_ATTRIBUTION_FIXTURES,
)
from fvsc.evaluation.relation_support_guard import source_affirms_relation


def test_attribution_audit_pairs_direct_and_external_expression_cases() -> None:
    fixtures = PUBLIC_RELATION_GUARD_ATTRIBUTION_FIXTURES
    assert len(fixtures) == 12
    assert len({item.case_id for item in fixtures}) == 12
    assert Counter(item.relation for item in fixtures) == {
        "accepted": 2,
        "conditional": 2,
        "confirmed": 2,
        "declined": 2,
        "replaced": 2,
        "retained": 2,
    }
    assert sum(item.should_be_directly_eligible for item in fixtures) == 6
    for fixture in fixtures:
        for span in fixture.expression_spans:
            span.verify(fixture.text)
            assert span.origin_status == "external"


def test_external_expression_spans_block_only_direct_relation_eligibility() -> None:
    for fixture in PUBLIC_RELATION_GUARD_ATTRIBUTION_FIXTURES:
        assert source_affirms_relation(
            fixture.text,
            fixture.relation,
            expression_spans=fixture.expression_spans,
        ) is fixture.should_be_directly_eligible
