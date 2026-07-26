from __future__ import annotations

import pytest

from fvsc.evaluation.synthesis import (
    COVERAGE_INSTRUCTION,
    FacetObservation,
    GoldFacet,
    SynthesisFixture,
    SyntheticSource,
    evaluate_synthesis_gate,
    instruction_for_arm,
    score_synthesis_case,
    summarize_synthesis_arm,
)
from fvsc.evaluation.synthesis_fixtures import PUBLIC_SYNTHESIS_FIXTURES
from fvsc.evaluation.synthesis_consistency_fixtures import (
    PUBLIC_CONSISTENCY_FIXTURES,
)
from fvsc.evaluation.coverage_atlas import PUBLIC_COVERAGE_ATLAS, atlas_fixtures


def _fixture() -> SynthesisFixture:
    return SynthesisFixture(
        case_id="C01",
        question="What changed and what remained constrained?",
        sources=(
            SyntheticSource("S1", "The window was extended to Friday."),
            SyntheticSource("S2", "The budget remained fixed."),
            SyntheticSource("S3", "If legal approves, Saturday is another option."),
        ),
        facets=(
            GoldFacet("deadline", "required", ("S1",)),
            GoldFacet("budget", "required", ("S2",)),
            GoldFacet("saturday", "alternative", ("S3",), "schedule"),
            GoldFacet("unlimited-budget", "prohibited"),
        ),
    )


def test_coverage_scoring_does_not_require_optional_or_alternative_facets() -> None:
    score = score_synthesis_case(
        _fixture(),
        FacetObservation(
            expressed_facet_ids=("deadline", "budget"),
            citations_by_facet={"deadline": ("S1",), "budget": ("S2",)},
            prompt_tokens=120,
            output_tokens=24,
            latency_seconds=0.5,
        ),
    )

    assert score.required_recall == 1.0
    assert score.citation_correctness == 1.0
    assert score.unsupported_facet_rate == 0.0
    assert score.role_violations == 0
    assert score.abstention_correct


def test_promoted_alternative_and_prohibited_claim_are_visible() -> None:
    score = score_synthesis_case(
        _fixture(),
        FacetObservation(
            expressed_facet_ids=("deadline", "saturday", "unlimited-budget"),
            citations_by_facet={"deadline": ("S1",), "saturday": ("S3",)},
            promoted_role_facet_ids=("saturday",),
        ),
    )

    assert score.required_recall == 0.5
    assert score.prohibited_violations == 1
    assert score.role_violations == 1
    assert score.unsupported_facet_rate == pytest.approx(1 / 3)


def test_wrong_or_missing_citations_reduce_correctness() -> None:
    score = score_synthesis_case(
        _fixture(),
        FacetObservation(
            expressed_facet_ids=("deadline", "budget"),
            citations_by_facet={"deadline": ("S2",)},
        ),
    )
    assert score.citation_correctness == 0.0


def test_positive_fixture_requires_multiple_independent_required_facets() -> None:
    with pytest.raises(ValueError, match="at least two"):
        SynthesisFixture(
            case_id="bad",
            question="q",
            sources=(SyntheticSource("S1", "text"),),
            facets=(GoldFacet("only", "required", ("S1",)),),
        )


def test_gold_roles_are_not_rendered_into_coverage_instruction() -> None:
    assert instruction_for_arm("coverage") == COVERAGE_INSTRUCTION
    for hidden_label in ("required", "optional", "prohibited"):
        assert hidden_label not in COVERAGE_INSTRUCTION
    with pytest.raises(ValueError, match="unknown synthesis arm"):
        instruction_for_arm("experimental")  # type: ignore[arg-type]


def test_public_fixture_set_covers_registered_roles_and_is_wholly_distinct() -> None:
    assert len(PUBLIC_SYNTHESIS_FIXTURES) == 6
    assert len({item.case_id for item in PUBLIC_SYNTHESIS_FIXTURES}) == 6
    roles = {
        facet.role
        for fixture in PUBLIC_SYNTHESIS_FIXTURES
        for facet in fixture.facets
    }
    assert roles == {"required", "optional", "alternative", "guard", "prohibited"}
    assert sum(item.should_abstain for item in PUBLIC_SYNTHESIS_FIXTURES) == 1


def test_registered_gate_requires_recall_gain_without_safety_regression() -> None:
    baseline_scores = (
        score_synthesis_case(
            _fixture(),
            FacetObservation(
                expressed_facet_ids=("deadline",),
                citations_by_facet={"deadline": ("S1",)},
                prompt_tokens=100,
                output_tokens=10,
            ),
        ),
    )
    coverage_scores = (
        score_synthesis_case(
            _fixture(),
            FacetObservation(
                expressed_facet_ids=("deadline", "budget"),
                citations_by_facet={"deadline": ("S1",), "budget": ("S2",)},
                prompt_tokens=120,
                output_tokens=18,
            ),
        ),
    )
    baseline = summarize_synthesis_arm("baseline", baseline_scores)
    coverage = summarize_synthesis_arm("coverage", coverage_scores)

    decision = evaluate_synthesis_gate(baseline, coverage)
    assert decision.passed
    assert decision.reasons == ()
    assert baseline.prompt_tokens == 100
    assert coverage.output_tokens == 18


def test_registered_gate_reports_role_promotion() -> None:
    baseline = summarize_synthesis_arm(
        "baseline",
        (
            score_synthesis_case(
                _fixture(),
                FacetObservation(
                    expressed_facet_ids=("deadline",),
                    citations_by_facet={"deadline": ("S1",)},
                ),
            ),
        ),
    )
    coverage = summarize_synthesis_arm(
        "coverage",
        (
            score_synthesis_case(
                _fixture(),
                FacetObservation(
                    expressed_facet_ids=("deadline", "budget", "saturday"),
                    citations_by_facet={
                        "deadline": ("S1",),
                        "budget": ("S2",),
                        "saturday": ("S3",),
                    },
                    promoted_role_facet_ids=("saturday",),
                ),
            ),
        ),
    )
    decision = evaluate_synthesis_gate(baseline, coverage)
    assert not decision.passed
    assert "coverage arm promoted guards or alternatives" in decision.reasons


def test_consistency_fixture_family_has_matched_positive_and_abstention_cases() -> None:
    assert len(PUBLIC_CONSISTENCY_FIXTURES) == 8
    assert sum(item.should_abstain for item in PUBLIC_CONSISTENCY_FIXTURES) == 4
    assert len({item.case_id for item in PUBLIC_CONSISTENCY_FIXTURES}) == 8
    for fixture in PUBLIC_CONSISTENCY_FIXTURES:
        required = [facet for facet in fixture.facets if facet.role == "required"]
        prohibited = [facet for facet in fixture.facets if facet.role == "prohibited"]
        if fixture.should_abstain:
            assert not required
            assert prohibited
        else:
            assert len(required) >= 2
            assert prohibited


def test_public_coverage_atlas_freezes_six_balanced_minimal_pairs() -> None:
    assert len(PUBLIC_COVERAGE_ATLAS) == 6
    assert len(atlas_fixtures()) == 12
    assert len({pair.phenomenon for pair in PUBLIC_COVERAGE_ATLAS}) == 6
    assert len({fixture.case_id for fixture in atlas_fixtures()}) == 12
    for pair in PUBLIC_COVERAGE_ATLAS:
        easy_required = {
            facet.facet_id for facet in pair.easy.facets if facet.role == "required"
        }
        hard_required = {
            facet.facet_id for facet in pair.hard.facets if facet.role == "required"
        }
        assert easy_required == hard_required
        assert len(easy_required) == 2
