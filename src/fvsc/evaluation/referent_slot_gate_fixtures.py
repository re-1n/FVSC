"""Frozen public fixtures for implicit-referent support inside fixed slots."""

from __future__ import annotations

from .answer_slot_boundaries import (
    compile_answer_slot_boundaries,
    to_frozen_question_plan,
)
from .synthesis import GoldFacet, SynthesisFixture, SyntheticSource


def _fixture(
    case_id: str,
    question: str,
    source_1: str,
    source_2: str,
    facet_1: str,
    facet_2: str,
    prohibited: str,
) -> SynthesisFixture:
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
    question: str,
    source_1: str,
    source_2: str,
    prohibited_1: str,
    prohibited_2: str,
) -> SynthesisFixture:
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


PUBLIC_REFERENT_SLOT_GATE_FIXTURES = (
    _fixture(
        "referent-heldout-001",
        "What is confirmed about the venue, and what remains conditional?",
        "The main hall is confirmed for the conference.",
        "The courtyard joins the venue plan only if the rain forecast clears.",
        "hall-confirmed",
        "courtyard-conditional",
        "courtyard-confirmed",
    ),
    _fixture(
        "referent-heldout-002",
        "What was retained from the release plan, and what was replaced?",
        "The Tuesday release date remains in the plan.",
        "A staged rollout replaced the single global launch.",
        "tuesday-retained",
        "global-launch-replaced",
        "whole-plan-retained",
    ),
    _fixture(
        "referent-heldout-003",
        "What was accepted in the garden design, and what was declined?",
        "The review accepted the native hedge.",
        "It declined the proposed fountain.",
        "hedge-accepted",
        "fountain-declined",
        "whole-design-accepted",
    ),
    _fixture(
        "referent-heldout-004",
        "What is confirmed about the maintenance window, and what remains conditional?",
        "Sunday morning is confirmed for database maintenance.",
        "The cache restart occurs only if stale entries remain after migration.",
        "sunday-confirmed",
        "restart-conditional",
        "restart-confirmed",
    ),
    _fixture(
        "referent-heldout-005",
        "What was retained from the training format, and what was replaced?",
        "The opening demonstration remains part of training.",
        "Individual exercises replaced the former group exercise.",
        "demo-retained",
        "group-exercise-replaced",
        "whole-format-retained",
    ),
    _fixture(
        "referent-heldout-006",
        "What was accepted in the signage proposal, and what was declined?",
        "Reviewers accepted the larger platform numbers.",
        "Reviewers rejected animated arrows.",
        "numbers-accepted",
        "arrows-declined",
        "whole-signage-accepted",
    ),
    _negative(
        "referent-heldout-007",
        "What is confirmed about the catering, and what remains conditional?",
        "Two caterers submitted menus.",
        "A tasting is scheduled before any catering decision.",
        "caterer-confirmed",
        "menu-conditional",
    ),
    _negative(
        "referent-heldout-008",
        "What was accepted in the mural proposal, and what was declined?",
        "The blue sketch passed a colour-fastness test.",
        "The red sketch is cheaper; the selection meeting is next month.",
        "blue-accepted",
        "red-declined",
    ),
)


REFERENT_PLAN_BY_CASE = {
    fixture.case_id: to_frozen_question_plan(
        fixture.case_id,
        compile_answer_slot_boundaries(fixture.question),
    )
    for fixture in PUBLIC_REFERENT_SLOT_GATE_FIXTURES
}


__all__ = ["PUBLIC_REFERENT_SLOT_GATE_FIXTURES", "REFERENT_PLAN_BY_CASE"]
