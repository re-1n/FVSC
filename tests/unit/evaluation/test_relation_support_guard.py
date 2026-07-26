from __future__ import annotations

import pytest

from fvsc.evaluation.planned_slot_synthesis import (
    FrozenQuestionPlan,
    PlannedRequirement,
)
from fvsc.evaluation.relation_support_guard import (
    compile_relation_support_candidates,
    relation_for_requirement,
)
from fvsc.evaluation.synthesis import SyntheticSource


def test_relation_guard_accepts_explicit_cues_and_rejects_proxy_evidence() -> None:
    plan = FrozenQuestionPlan(
        "case",
        (
            PlannedRequirement("R1", "what was accepted in the proposal"),
            PlannedRequirement("R2", "what was declined"),
        ),
    )
    candidates = compile_relation_support_candidates(
        plan,
        (
            SyntheticSource("S1", "The panel accepted the stone arch."),
            SyntheticSource("S2", "The timber arch passed a strength test."),
            SyntheticSource("S3", "The panel rejected the glass arch."),
            SyntheticSource("S4", "The steel arch costs less."),
        ),
    )
    assert candidates[0].eligible_source_labels == ("S1",)
    assert candidates[1].eligible_source_labels == ("S3",)


def test_conditional_guard_does_not_treat_chronology_as_condition() -> None:
    plan = FrozenQuestionPlan(
        "case",
        (PlannedRequirement("R1", "what remains conditional"),),
    )
    candidates = compile_relation_support_candidates(
        plan,
        (
            SyntheticSource("S1", "A tasting occurs before the decision."),
            SyntheticSource("S2", "The terrace opens only if the forecast clears."),
        ),
    )
    assert candidates[0].eligible_source_labels == ("S2",)


def test_unknown_or_ambiguous_relation_fails_closed() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        relation_for_requirement("general plan")
    with pytest.raises(ValueError, match="exactly one"):
        relation_for_requirement("what was accepted and declined")
