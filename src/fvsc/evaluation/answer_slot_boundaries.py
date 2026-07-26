"""Deterministic question-only answer-slot boundary compilation."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


BoundaryKind = Literal[
    "attribute_coordination",
    "explicit_clause_coordination",
    "requested_role_pair",
    "temporal_pair",
]


@dataclass(frozen=True)
class AnswerSlot:
    slot_id: str
    role: str
    description: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"R[1-9][0-9]*", self.slot_id):
            raise ValueError("answer slot id must use R<number>")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.role):
            raise ValueError("answer slot role must be a stable snake-case label")
        description = self.description.strip()
        if not description:
            raise ValueError("answer slot description must not be empty")
        object.__setattr__(self, "description", description)


@dataclass(frozen=True)
class AnswerSlotBoundaryPlan:
    question: str
    boundary_kind: BoundaryKind
    slots: tuple[AnswerSlot, ...]

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("question must not be empty")
        if len(self.slots) < 2:
            raise ValueError("a boundary plan requires at least two answer slots")
        expected = tuple(f"R{index}" for index in range(1, len(self.slots) + 1))
        if tuple(slot.slot_id for slot in self.slots) != expected:
            raise ValueError("answer slots must be contiguous and ordered")


class AmbiguousAnswerSlotBoundary(ValueError):
    """Raised when the registered grammar cannot establish slot boundaries."""


_TEMPORAL = re.compile(r"^How did (?P<topic>.+?) change\?$", re.IGNORECASE)
_ORDERED_PAIR = re.compile(
    r"^What (?:two-step|two stage|two-stage) (?P<topic>.+?)"
    r"(?: did .+? request| was requested)?\?$",
    re.IGNORECASE,
)
_WHERE_REASON = re.compile(
    r"^Where (?:was|were|is|are) (?P<topic>.+?),? and why\?$",
    re.IGNORECASE,
)
_PRIMARY_RELATION = re.compile(
    r"^What (?:is|are) (?P<primary>.+?) and (?:its|their) "
    r"(?P<relation_phrase>(?:[a-z][a-z -]* )?"
    r"(?P<relation>condition|constraint|reason|rationale))\?$",
    re.IGNORECASE,
)
_WHAT_CLAUSES = re.compile(
    r"^What (?P<left>.+?), and what (?P<right>.+?)\?$",
    re.IGNORECASE,
)
_WHAT_ATTRIBUTES = re.compile(
    r"^What (?:are|is) (?:the )?(?P<topic>.+?)(?:'s|s') "
    r"(?P<left>[a-z][a-z -]*?) and (?P<right>[a-z][a-z -]*?)\?$",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" ,.?!")


def _slots(*items: tuple[str, str]) -> tuple[AnswerSlot, ...]:
    return tuple(
        AnswerSlot(f"R{index}", role, _clean(description))
        for index, (role, description) in enumerate(items, start=1)
    )


def compile_answer_slot_boundaries(question: str) -> AnswerSlotBoundaryPlan:
    """Compile only boundaries licensed by explicit registered question grammar."""

    normalized = _clean(question)
    normalized = normalized + "?"

    match = _TEMPORAL.fullmatch(normalized)
    if match:
        topic = _clean(match.group("topic"))
        return AnswerSlotBoundaryPlan(
            question,
            "temporal_pair",
            _slots(
                ("former_state", f"former state of {topic}"),
                ("current_state", f"current state of {topic}"),
            ),
        )

    match = _ORDERED_PAIR.fullmatch(normalized)
    if match:
        topic = _clean(match.group("topic"))
        return AnswerSlotBoundaryPlan(
            question,
            "requested_role_pair",
            _slots(
                ("step_1", f"first step of {topic}"),
                ("step_2", f"second step of {topic}"),
            ),
        )

    match = _WHERE_REASON.fullmatch(normalized)
    if match:
        topic = _clean(match.group("topic"))
        return AnswerSlotBoundaryPlan(
            question,
            "explicit_clause_coordination",
            _slots(
                ("destination", f"destination of {topic}"),
                ("reason", f"reason for moving {topic}"),
            ),
        )

    match = _PRIMARY_RELATION.fullmatch(normalized)
    if match:
        primary = _clean(match.group("primary"))
        relation = _clean(match.group("relation")).lower()
        relation_phrase = _clean(match.group("relation_phrase"))
        return AnswerSlotBoundaryPlan(
            question,
            "explicit_clause_coordination",
            _slots(
                ("primary", primary),
                (relation, f"{relation_phrase} for {primary}"),
            ),
        )

    match = _WHAT_CLAUSES.fullmatch(normalized)
    if match:
        left = _clean(match.group("left"))
        right = _clean(match.group("right"))
        return AnswerSlotBoundaryPlan(
            question,
            "explicit_clause_coordination",
            _slots(
                ("requested_clause_1", left),
                ("requested_clause_2", right),
            ),
        )

    match = _WHAT_ATTRIBUTES.fullmatch(normalized)
    if match:
        topic = _clean(match.group("topic"))
        left = _clean(match.group("left"))
        right = _clean(match.group("right"))
        return AnswerSlotBoundaryPlan(
            question,
            "attribute_coordination",
            _slots(
                ("attribute_1", f"{left} of {topic}"),
                ("attribute_2", f"{right} of {topic}"),
            ),
        )

    raise AmbiguousAnswerSlotBoundary(
        "question does not match a registered explicit multi-slot grammar"
    )


def to_frozen_question_plan(
    case_id: str,
    boundary_plan: AnswerSlotBoundaryPlan,
):
    """Adapt a validated boundary plan to the existing planned-slot contract."""

    from .planned_slot_synthesis import FrozenQuestionPlan, PlannedRequirement

    return FrozenQuestionPlan(
        case_id,
        tuple(
            PlannedRequirement(slot.slot_id, slot.description)
            for slot in boundary_plan.slots
        ),
    )


__all__ = [
    "AmbiguousAnswerSlotBoundary",
    "AnswerSlot",
    "AnswerSlotBoundaryPlan",
    "BoundaryKind",
    "compile_answer_slot_boundaries",
    "to_frozen_question_plan",
]
