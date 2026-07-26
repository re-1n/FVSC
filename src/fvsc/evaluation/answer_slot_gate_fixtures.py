"""Frozen public held-out questions for deterministic answer-slot boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from .answer_slot_boundaries import BoundaryKind


@dataclass(frozen=True)
class AnswerSlotGateFixture:
    case_id: str
    question: str
    boundary_kind: BoundaryKind
    expected_roles: tuple[str, ...]


PUBLIC_ANSWER_SLOT_GATE_FIXTURES = (
    AnswerSlotGateFixture(
        "slot-heldout-001",
        "How did the workshop access policy change?",
        "temporal_pair",
        ("former_state", "current_state"),
    ),
    AnswerSlotGateFixture(
        "slot-heldout-002",
        "How did the archive retention period change?",
        "temporal_pair",
        ("former_state", "current_state"),
    ),
    AnswerSlotGateFixture(
        "slot-heldout-003",
        "How did the ferry reservation rule change?",
        "temporal_pair",
        ("former_state", "current_state"),
    ),
    AnswerSlotGateFixture(
        "slot-heldout-004",
        "Where was the emergency stock moved, and why?",
        "explicit_clause_coordination",
        ("destination", "reason"),
    ),
    AnswerSlotGateFixture(
        "slot-heldout-005",
        "What is the lighting plan and its heat condition?",
        "explicit_clause_coordination",
        ("primary", "condition"),
    ),
    AnswerSlotGateFixture(
        "slot-heldout-006",
        "What is the routing decision and its rationale?",
        "explicit_clause_coordination",
        ("primary", "rationale"),
    ),
    AnswerSlotGateFixture(
        "slot-heldout-007",
        "What is confirmed about the first delivery, and what remains conditional?",
        "explicit_clause_coordination",
        ("requested_clause_1", "requested_clause_2"),
    ),
    AnswerSlotGateFixture(
        "slot-heldout-008",
        "What was accepted in the exterior proposal, and what was declined?",
        "explicit_clause_coordination",
        ("requested_clause_1", "requested_clause_2"),
    ),
    AnswerSlotGateFixture(
        "slot-heldout-009",
        "What was retained from the old schedule, and what was replaced?",
        "explicit_clause_coordination",
        ("requested_clause_1", "requested_clause_2"),
    ),
    AnswerSlotGateFixture(
        "slot-heldout-010",
        "What two-step recovery procedure did the operator request?",
        "requested_role_pair",
        ("step_1", "step_2"),
    ),
    AnswerSlotGateFixture(
        "slot-heldout-011",
        "What two-stage review process was requested?",
        "requested_role_pair",
        ("step_1", "step_2"),
    ),
    AnswerSlotGateFixture(
        "slot-heldout-012",
        "What two-step notification sequence did the coordinator request?",
        "requested_role_pair",
        ("step_1", "step_2"),
    ),
)


__all__ = ["AnswerSlotGateFixture", "PUBLIC_ANSWER_SLOT_GATE_FIXTURES"]
