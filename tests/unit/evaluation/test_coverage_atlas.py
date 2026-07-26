from __future__ import annotations

from fvsc.evaluation.coverage_atlas import (
    PUBLIC_COVERAGE_ATLAS,
    atlas_fixtures,
    summarize_coverage_atlas,
)
from fvsc.evaluation.synthesis import SynthesisCaseScore


def _score(case_id: str, recall: float) -> SynthesisCaseScore:
    return SynthesisCaseScore(
        case_id=case_id,
        required_recall=recall,
        unsupported_facet_rate=0.0,
        citation_correctness=1.0,
        prohibited_violations=0,
        role_violations=0,
        abstention_correct=True,
        prompt_tokens=None,
        output_tokens=None,
        latency_seconds=None,
    )


def test_atlas_selects_only_a_unique_hard_variant_completion_gap() -> None:
    scores = {item.case_id: _score(item.case_id, 1.0) for item in atlas_fixtures()}
    target = PUBLIC_COVERAGE_ATLAS[2]
    scores[target.hard.case_id] = _score(target.hard.case_id, 0.5)

    summary = summarize_coverage_atlas(scores)
    assert summary.selected_phenomenon == target.phenomenon
    selected = next(
        item for item in summary.phenomena if item.phenomenon == target.phenomenon
    )
    assert selected.completion_gap == 1


def test_atlas_tie_does_not_select_a_post_hoc_target() -> None:
    scores = {item.case_id: _score(item.case_id, 1.0) for item in atlas_fixtures()}
    for pair in PUBLIC_COVERAGE_ATLAS[:2]:
        scores[pair.hard.case_id] = _score(pair.hard.case_id, 0.5)
    summary = summarize_coverage_atlas(scores)
    assert summary.selected_phenomenon is None
    assert "tie" in summary.selection_reason


def test_atlas_rejects_incomplete_score_maps() -> None:
    scores = {item.case_id: _score(item.case_id, 1.0) for item in atlas_fixtures()}
    scores.pop(next(iter(scores)))
    try:
        summarize_coverage_atlas(scores)
    except ValueError as error:
        assert "every frozen case" in str(error)
    else:
        raise AssertionError("incomplete atlas score map was accepted")
