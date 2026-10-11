"""Held-out public fixtures for the requirement-coverage synthesis gate."""

from __future__ import annotations

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


PUBLIC_REQUIREMENT_GATE_FIXTURES = (
    _positive(
        "requirement-heldout-001",
        "What is the greenhouse ventilation plan and its heat condition?",
        "The east vents carry the routine airflow.",
        "The roof vents join in only once the interior passes thirty degrees.",
        "east-routine",
        "roof-heat-conditional",
        "roof-always-open",
    ),
    _positive(
        "requirement-heldout-002",
        "Where was the audit log moved, and why?",
        "The secure server now houses the audit log.",
        "The relocation answers to an access breach on the former host.",
        "secure-server",
        "breach-reason",
        "capacity-reason",
    ),
    _positive(
        "requirement-heldout-003",
        "How did the laboratory booking rule change?",
        "The former rule allowed bookings without an end date.",
        "The current rule closes each booking after six hours.",
        "no-end-before",
        "six-hours-now",
        "no-end-now",
    ),
    _positive(
        "requirement-heldout-004",
        "What two-step response did the moderator request?",
        "Begin by recording the participant's objection in full.",
        "A ruling is to follow only after the participant confirms that record.",
        "record-objection",
        "delay-ruling",
        "rule-immediately",
    ),
    _positive(
        "requirement-heldout-005",
        "Which portions of the restoration did the inspector accept and decline?",
        "Acceptance covered the stonework.",
        "It stopped short of the replacement windows.",
        "stonework-accepted",
        "windows-declined",
        "whole-restoration-accepted",
    ),
    _positive(
        "requirement-heldout-006",
        "What transfer was made, and what constraint motivated it?",
        "Night deliveries now use the river entrance.",
        "The shift follows the residential noise limit at the courtyard gate.",
        "river-entrance",
        "noise-limit-reason",
        "distance-reason",
    ),
    _positive(
        "requirement-heldout-007",
        "What are the seminar's location and attendance format?",
        "The seminar is anchored in Studio Four.",
        "Attendance remains in person rather than remote.",
        "studio-four",
        "in-person",
        "remote",
    ),
    _positive(
        "requirement-heldout-008",
        "What is confirmed about the shipment, and what remains conditional?",
        "The first crate leaves on Wednesday.",
        "The second crate follows only upon customs clearance.",
        "first-wednesday",
        "second-customs-conditional",
        "second-confirmed",
    ),
    _negative(
        "requirement-heldout-009",
        "Which insulation material was selected?",
        "Cork achieved the best thermal score.",
        "Mineral wool achieved the best fire score; selection is next week.",
        "cork-selected",
        "wool-selected",
    ),
    _negative(
        "requirement-heldout-010",
        "What caused the library network interruption?",
        "A catalog import ended shortly before the interruption.",
        "A router inspection began after service returned; the cause is unresolved.",
        "import-cause",
        "router-cause",
    ),
    _negative(
        "requirement-heldout-011",
        "Which landscaping proposal was approved?",
        "The pond proposal passed drainage review.",
        "The meadow proposal costs less; the approval vote is Friday.",
        "pond-approved",
        "meadow-approved",
    ),
    _negative(
        "requirement-heldout-012",
        "Which migration task has been completed?",
        "The database migration has an allocated budget.",
        "Credentials for the file migration are ready; work starts tomorrow.",
        "database-completed",
        "files-completed",
    ),
)


__all__ = ["PUBLIC_REQUIREMENT_GATE_FIXTURES"]
