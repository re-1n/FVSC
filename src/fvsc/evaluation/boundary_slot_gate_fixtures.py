"""Held-out sources for the boundary-compiled planned-slot synthesis gate."""

from __future__ import annotations

from .answer_slot_boundaries import (
    compile_answer_slot_boundaries,
    to_frozen_question_plan,
)
from .answer_slot_gate_fixtures import PUBLIC_ANSWER_SLOT_GATE_FIXTURES
from .synthesis import GoldFacet, SynthesisFixture, SyntheticSource


def _positive(
    case_id: str,
    source_1: str,
    source_2: str,
    facet_1: str,
    facet_2: str,
    prohibited: str,
) -> SynthesisFixture:
    question = next(
        fixture.question
        for fixture in PUBLIC_ANSWER_SLOT_GATE_FIXTURES
        if fixture.case_id == case_id
    )
    return SynthesisFixture(
        case_id,
        question,
        (SyntheticSource("S1", source_1), SyntheticSource("S2", source_2)),
        (
            GoldFacet(facet_1, "required", ("S1",)),
            GoldFacet(facet_2, "required", ("S2",)),
            GoldFacet(prohibited, "prohibited"),
        ),
    )


def _negative(
    case_id: str,
    source_1: str,
    source_2: str,
    prohibited_1: str,
    prohibited_2: str,
) -> SynthesisFixture:
    question = next(
        fixture.question
        for fixture in PUBLIC_ANSWER_SLOT_GATE_FIXTURES
        if fixture.case_id == case_id
    )
    return SynthesisFixture(
        case_id,
        question,
        (SyntheticSource("S1", source_1), SyntheticSource("S2", source_2)),
        (
            GoldFacet(prohibited_1, "prohibited"),
            GoldFacet(prohibited_2, "prohibited"),
        ),
        should_abstain=True,
    )


PUBLIC_BOUNDARY_SLOT_GATE_FIXTURES = (
    _positive(
        "slot-heldout-001",
        "Previously, workshop access remained open until midnight.",
        "The current policy closes workshop access at nine in the evening.",
        "midnight-before",
        "nine-now",
        "midnight-now",
    ),
    _positive(
        "slot-heldout-002",
        "The former archive rule retained records for three years.",
        "The present retention period is seven years.",
        "three-years-before",
        "seven-years-now",
        "three-years-now",
    ),
    _positive(
        "slot-heldout-003",
        "Under the earlier rule, ferry places could be reserved without payment.",
        "Now a reservation becomes valid only after a deposit.",
        "no-deposit-before",
        "deposit-now",
        "no-deposit-now",
    ),
    _positive(
        "slot-heldout-004",
        "The emergency stock was transferred to the north depot.",
        "The transfer followed repeated flooding in the former storeroom.",
        "north-depot",
        "flooding-reason",
        "capacity-reason",
    ),
    _positive(
        "slot-heldout-005",
        "The west lamps provide the routine lighting.",
        "Ceiling lamps join only when the room exceeds twenty-eight degrees.",
        "west-routine",
        "ceiling-heat-condition",
        "ceiling-always",
    ),
    _positive(
        "slot-heldout-006",
        "Deliveries were routed through the rear entrance.",
        "The choice avoids the pedestrian-only frontage.",
        "rear-entrance",
        "pedestrian-rationale",
        "shorter-route",
    ),
    _positive(
        "slot-heldout-007",
        "The first delivery is confirmed for Thursday.",
        "A second delivery proceeds only if the loading permit arrives.",
        "first-thursday",
        "second-permit-conditional",
        "second-confirmed",
    ),
    _positive(
        "slot-heldout-008",
        "The inspector accepted the exterior brickwork.",
        "The inspector declined the proposed balcony railings.",
        "brickwork-accepted",
        "railings-declined",
        "whole-exterior-accepted",
    ),
    _positive(
        "slot-heldout-009",
        "The morning departure was retained from the old schedule.",
        "The evening departure was replaced by an afternoon service.",
        "morning-retained",
        "evening-replaced",
        "whole-schedule-retained",
    ),
    _positive(
        "slot-heldout-010",
        "First isolate the failed pump from the water line.",
        "Then restart the controller after pressure reaches zero.",
        "isolate-pump",
        "restart-after-zero",
        "restart-immediately",
    ),
    _negative(
        "slot-heldout-011",
        "A single technical review is scheduled for Tuesday.",
        "A later publication meeting has not yet been approved.",
        "technical-first-stage",
        "publication-second-stage",
    ),
    _negative(
        "slot-heldout-012",
        "Email and radio alerts were discussed as alternatives.",
        "The coordinator will choose a notification process next week.",
        "email-first-step",
        "radio-second-step",
    ),
)


BOUNDARY_PLAN_BY_CASE = {
    fixture.case_id: to_frozen_question_plan(
        fixture.case_id,
        compile_answer_slot_boundaries(fixture.question),
    )
    for fixture in PUBLIC_BOUNDARY_SLOT_GATE_FIXTURES
}


__all__ = ["BOUNDARY_PLAN_BY_CASE", "PUBLIC_BOUNDARY_SLOT_GATE_FIXTURES"]
