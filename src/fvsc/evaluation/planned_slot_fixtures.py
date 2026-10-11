"""Frozen question-only plans for the held-out requirement fixtures."""

from __future__ import annotations

from .planned_slot_synthesis import FrozenQuestionPlan, PlannedRequirement


def _plan(case_id: str, *descriptions: str) -> FrozenQuestionPlan:
    return FrozenQuestionPlan(
        case_id,
        tuple(
            PlannedRequirement(f"R{index}", description)
            for index, description in enumerate(descriptions, start=1)
        ),
    )


PUBLIC_FROZEN_QUESTION_PLANS = (
    _plan("requirement-heldout-001", "routine ventilation plan", "heat condition"),
    _plan("requirement-heldout-002", "audit-log destination", "reason for relocation"),
    _plan("requirement-heldout-003", "former booking rule", "current booking rule"),
    _plan("requirement-heldout-004", "first response step", "second response step"),
    _plan("requirement-heldout-005", "accepted portion", "declined portion"),
    _plan("requirement-heldout-006", "transfer decision", "motivating constraint"),
    _plan("requirement-heldout-007", "seminar location", "attendance format"),
    _plan("requirement-heldout-008", "confirmed shipment fact", "conditional shipment fact"),
    _plan("requirement-heldout-009", "selected insulation material"),
    _plan("requirement-heldout-010", "cause of network interruption"),
    _plan("requirement-heldout-011", "approved landscaping proposal"),
    _plan("requirement-heldout-012", "completed migration task"),
)

QUESTION_PLAN_BY_CASE = {item.case_id: item for item in PUBLIC_FROZEN_QUESTION_PLANS}


__all__ = ["PUBLIC_FROZEN_QUESTION_PLANS", "QUESTION_PLAN_BY_CASE"]
