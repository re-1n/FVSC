from __future__ import annotations

from fvsc.evaluation.coverage_atlas_v2 import (
    PUBLIC_COVERAGE_ATLAS_V2_EXTENSION,
    atlas_v2_extension_fixtures,
    summarize_coverage_extension,
)
from fvsc.evaluation.synthesis import SynthesisCaseScore


def _score(case_id: str, recall: float) -> SynthesisCaseScore:
    return SynthesisCaseScore(
        case_id, recall, 0.0, 1.0, 0, 0, True, None, None, None
    )


def test_v2_extension_is_balanced_across_the_three_tied_phenomena() -> None:
    assert len(PUBLIC_COVERAGE_ATLAS_V2_EXTENSION) == 6
    assert len(atlas_v2_extension_fixtures()) == 12
    counts = {}
    for pair in PUBLIC_COVERAGE_ATLAS_V2_EXTENSION:
        counts[pair.phenomenon] = counts.get(pair.phenomenon, 0) + 1
    assert set(counts.values()) == {2}


def test_v2_selection_rule_uses_drop_count_then_hard_recall() -> None:
    scores = {
        item.case_id: _score(item.case_id, 1.0)
        for item in atlas_v2_extension_fixtures()
    }
    temporal = [
        pair
        for pair in PUBLIC_COVERAGE_ATLAS_V2_EXTENSION
        if pair.phenomenon == "temporal_contrast"
    ]
    conditional = [
        pair
        for pair in PUBLIC_COVERAGE_ATLAS_V2_EXTENSION
        if pair.phenomenon == "conditional_scope"
    ]
    for pair in temporal:
        scores[pair.hard.case_id] = _score(pair.hard.case_id, 0.0)
    for pair in conditional:
        scores[pair.hard.case_id] = _score(pair.hard.case_id, 0.5)
    summary = summarize_coverage_extension(scores)
    assert summary.selected_phenomenon == "temporal_contrast"
    assert "lowest hard mean recall" in summary.selection_reason


def test_v2_selection_rule_retains_no_target_on_full_tie() -> None:
    scores = {
        item.case_id: _score(item.case_id, 1.0)
        for item in atlas_v2_extension_fixtures()
    }
    for pair in PUBLIC_COVERAGE_ATLAS_V2_EXTENSION:
        scores[pair.hard.case_id] = _score(pair.hard.case_id, 0.0)
    summary = summarize_coverage_extension(scores)
    assert summary.selected_phenomenon is None
    assert "remains tied" in summary.selection_reason
