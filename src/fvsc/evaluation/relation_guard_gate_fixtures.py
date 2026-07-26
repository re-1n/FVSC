"""Frozen public fixtures for the typed relation-support guard gate."""

from __future__ import annotations

from .answer_slot_boundaries import (
    compile_answer_slot_boundaries,
    to_frozen_question_plan,
)
from .relation_support_guard import compile_relation_support_candidates
from .synthesis import GoldFacet, SynthesisFixture, SyntheticSource


def _positive(case_id, question, source_1, source_2, facet_1, facet_2, prohibited):
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


def _negative(case_id, question, source_1, source_2, prohibited_1, prohibited_2):
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


PUBLIC_RELATION_GUARD_GATE_FIXTURES = (
    _positive(
        "relation-guard-001",
        "What is confirmed about the rehearsal, and what remains conditional?",
        "The orchestra rehearsal is confirmed for Monday.",
        "The choir rehearsal proceeds only if the conductor arrives by noon.",
        "orchestra-monday",
        "choir-conductor-condition",
        "choir-confirmed",
    ),
    _positive(
        "relation-guard-002",
        "What is confirmed about the exhibit, and what remains conditional?",
        "The map exhibit is confirmed for Gallery Two.",
        "The manuscript display opens only after humidity falls below fifty percent.",
        "map-gallery-two",
        "manuscript-humidity-condition",
        "manuscript-confirmed",
    ),
    _positive(
        "relation-guard-003",
        "What was accepted in the bridge proposal, and what was declined?",
        "The council accepted the wider footpath.",
        "The council rejected the illuminated handrail.",
        "footpath-accepted",
        "handrail-declined",
        "whole-bridge-accepted",
    ),
    _positive(
        "relation-guard-004",
        "What was accepted in the menu proposal, and what was declined?",
        "The kitchen adopted the seasonal soup.",
        "The kitchen declined the imported dessert.",
        "soup-accepted",
        "dessert-declined",
        "whole-menu-accepted",
    ),
    _positive(
        "relation-guard-005",
        "What was retained from the dispatch procedure, and what was replaced?",
        "The manual identity check was retained.",
        "Barcode scanning replaced the handwritten dispatch ledger.",
        "identity-check-retained",
        "ledger-replaced",
        "whole-procedure-retained",
    ),
    _positive(
        "relation-guard-006",
        "What was retained from the orientation, and what was replaced?",
        "The safety briefing remains part of orientation.",
        "A building walk replaced the slide tour.",
        "briefing-retained",
        "tour-replaced",
        "whole-orientation-retained",
    ),
    _negative(
        "relation-guard-007",
        "What was accepted in the roof proposal, and what was declined?",
        "The tile option passed the wind test.",
        "The metal option has a lower price; voting is pending.",
        "tile-accepted",
        "metal-declined",
    ),
    _negative(
        "relation-guard-008",
        "What is confirmed about the parade, and what remains conditional?",
        "The riverside route scored highest in the survey.",
        "A permit review occurs before the route decision.",
        "riverside-confirmed",
        "permit-conditional",
    ),
    _negative(
        "relation-guard-009",
        "What was retained from the packaging plan, and what was replaced?",
        "The paper sleeve is the cheapest tested option.",
        "A reusable box prototype will be tested next month.",
        "sleeve-retained",
        "box-replaced",
    ),
    _negative(
        "relation-guard-010",
        "What was accepted in the timetable proposal, and what was declined?",
        "The early train was discussed first.",
        "The late train requires less platform staffing; no vote has occurred.",
        "early-accepted",
        "late-declined",
    ),
    _negative(
        "relation-guard-011",
        "What is confirmed about the workshop, and what remains conditional?",
        "Room Six is available on Wednesday.",
        "Registration closes before the final room assignment.",
        "room-six-confirmed",
        "registration-conditional",
    ),
    _negative(
        "relation-guard-012",
        "What was retained from the migration plan, and what was replaced?",
        "The database task has completed a dry run.",
        "The file task has an approved budget; implementation starts later.",
        "database-retained",
        "files-replaced",
    ),
)


RELATION_GUARD_PLAN_BY_CASE = {
    fixture.case_id: to_frozen_question_plan(
        fixture.case_id,
        compile_answer_slot_boundaries(fixture.question),
    )
    for fixture in PUBLIC_RELATION_GUARD_GATE_FIXTURES
}

RELATION_ELIGIBLE_LABELS_BY_CASE = {
    fixture.case_id: {
        candidate.requirement_id: candidate.eligible_source_labels
        for candidate in compile_relation_support_candidates(
            RELATION_GUARD_PLAN_BY_CASE[fixture.case_id],
            fixture.sources,
        )
    }
    for fixture in PUBLIC_RELATION_GUARD_GATE_FIXTURES
}


__all__ = [
    "PUBLIC_RELATION_GUARD_GATE_FIXTURES",
    "RELATION_ELIGIBLE_LABELS_BY_CASE",
    "RELATION_GUARD_PLAN_BY_CASE",
]
