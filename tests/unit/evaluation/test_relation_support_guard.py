from __future__ import annotations

from types import SimpleNamespace

import pytest

from fvsc.evaluation.planned_slot_synthesis import (
    FrozenQuestionPlan,
    PlannedRequirement,
)
from fvsc.evaluation.relation_support_guard import (
    PUBLIC_RELATION_SUPPORT_GUARD,
    RELATION_SUPPORT_GUARD_OPERATION_ID,
    RelationSupportGuardOperation,
    compile_relation_support_candidates,
    relation_for_requirement,
    source_affirms_relation,
)
from fvsc.evaluation.synthesis import SyntheticSource
from fvsc.ingest import ExpressionSpan, source_attribution


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


def test_guard_is_explicitly_registered_as_s6() -> None:
    assert PUBLIC_RELATION_SUPPORT_GUARD.operation_id == "S6"
    assert RELATION_SUPPORT_GUARD_OPERATION_ID == "S6"
    with pytest.raises(ValueError, match="remain S6"):
        RelationSupportGuardOperation(operation_id="S7")


@pytest.mark.parametrize(
    ("text", "relation", "expected"),
    (
        ("The room is confirmed.", "confirmed", True),
        ("The room is not confirmed.", "confirmed", False),
        ("The room may be confirmed.", "confirmed", False),
        ("It opens only if approved.", "conditional", True),
        ("It may become subject to approval.", "conditional", False),
        ("The receipt was retained.", "retained", True),
        ("The receipt was not retained.", "retained", False),
        ("A kiosk replaced the desk.", "replaced", True),
        ("A kiosk has not replaced the desk.", "replaced", False),
    ),
)
def test_relation_cues_obey_local_polarity_and_modality(
    text: str,
    relation,
    expected: bool,
) -> None:
    assert source_affirms_relation(text, relation) is expected


def test_owner_commentary_span_preserves_direct_relation_cue() -> None:
    text = "The owner commentary says the panel accepted the arch."
    start = text.index("the panel accepted")
    span = ExpressionSpan.from_text(
        text,
        start=start,
        end=len(text),
        kind="owner_commentary",
        origin_status="owner",
        owner_relation="authored",
    )
    assert source_affirms_relation(
        text,
        "accepted",
        expression_spans=(span,),
    )


def test_registered_operation_consumes_existing_f1_attribution_envelope() -> None:
    text = 'The message quotes: "The panel accepted the arch."'
    quoted = "The panel accepted the arch."
    start = text.index(quoted)
    span = ExpressionSpan.from_text(
        text,
        start=start,
        end=start + len(quoted),
        kind="quotation",
        origin_status="external",
    )
    source = SimpleNamespace(
        label="S1",
        text=text,
        attribution=source_attribution(
            transport_author_role="owner",
            owner_adopted_expression=False,
            expression_spans=(span,),
        ),
    )
    plan = FrozenQuestionPlan(
        "case",
        (PlannedRequirement("R1", "what was accepted"),),
    )
    candidate = PUBLIC_RELATION_SUPPORT_GUARD.compile(plan, (source,))[0]
    assert candidate.eligible_source_labels == ()
