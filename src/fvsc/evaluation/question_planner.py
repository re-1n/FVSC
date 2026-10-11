"""Question-only QDMR-like planning contracts for operation S5."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


QuestionOperation = Literal[
    "select",
    "project",
    "filter",
    "compare",
    "boolean",
]

QUESTION_PLANNER_PROMPT_VERSION = "public-question-planner-qdmr-v1"
QUESTION_PLANNER_INSTRUCTION = """Decompose only the supplied question into the
smallest ordered steps needed to answer it. Do not answer the question and do not
assume any source facts.

Use only these operations:
- select: introduce an entity, event, decision, or requested fact without a prior step;
- project: request a property, reason, state, part, or other relation of a prior step;
- filter: restrict a prior step by an explicit condition, time, polarity, or scope;
- compare: request a comparison or change between prior steps;
- boolean: ask whether a proposition represented by prior steps holds.

References are earlier step_ids used by the step. Set emits_requirement=true only when
the step directly corresponds to a part of the answer the user requested. Internal
setup steps must set it to false. Preserve contrasts, order, conditions, reasons,
polarity, and former/current distinctions in the description.

Return JSON only:
{"steps":[{"step_id":"S1","operation":"select","description":"...",
"references":[],"emits_requirement":false}]}"""


@dataclass(frozen=True)
class QuestionPlanStep:
    step_id: str
    operation: QuestionOperation
    description: str
    references: tuple[str, ...] = ()
    emits_requirement: bool = True

    def __post_init__(self) -> None:
        if not self.step_id.startswith("S") or not self.step_id[1:].isdigit():
            raise ValueError("question-plan step id must use S<number>")
        if self.operation not in {"select", "project", "filter", "compare", "boolean"}:
            raise ValueError(f"unknown question operation: {self.operation!r}")
        description = str(self.description).strip()
        if not description:
            raise ValueError("question-plan step description must not be empty")
        if len(self.references) != len(set(self.references)):
            raise ValueError("question-plan references must be unique")
        step_number = int(self.step_id[1:])
        for reference in self.references:
            if (
                not reference.startswith("S")
                or not reference[1:].isdigit()
                or int(reference[1:]) >= step_number
            ):
                raise ValueError("question-plan references must point to earlier steps")
        if self.operation == "select" and self.references:
            raise ValueError("select steps cannot reference earlier steps")
        if self.operation != "select" and not self.references:
            raise ValueError("non-select steps require an earlier-step reference")
        object.__setattr__(self, "description", description)


@dataclass(frozen=True)
class QuestionOnlyPlan:
    question: str
    steps: tuple[QuestionPlanStep, ...]

    def __post_init__(self) -> None:
        if not str(self.question).strip():
            raise ValueError("question must not be empty")
        if not self.steps:
            raise ValueError("question plan requires steps")
        expected = tuple(f"S{index}" for index in range(1, len(self.steps) + 1))
        actual = tuple(step.step_id for step in self.steps)
        if actual != expected:
            raise ValueError("question-plan steps must be contiguous and ordered")
        if not any(step.emits_requirement for step in self.steps):
            raise ValueError("question plan must emit at least one requirement")

    @property
    def requirements(self) -> tuple[QuestionPlanStep, ...]:
        return tuple(step for step in self.steps if step.emits_requirement)


__all__ = [
    "QUESTION_PLANNER_INSTRUCTION",
    "QUESTION_PLANNER_PROMPT_VERSION",
    "QuestionOnlyPlan",
    "QuestionOperation",
    "QuestionPlanStep",
]
