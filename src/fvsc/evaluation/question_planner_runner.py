"""Run a source-free QDMR-like question planner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol, Sequence

from ..integrations.ollama import OllamaGenerationTelemetry
from .question_planner import (
    QUESTION_PLANNER_INSTRUCTION,
    QUESTION_PLANNER_PROMPT_VERSION,
    QuestionOnlyPlan,
    QuestionPlanStep,
)
from .synthesis import SynthesisFixture


class QuestionPlannerBackend(Protocol):
    last_generation_telemetry: OllamaGenerationTelemetry | None

    def generate_json_object(
        self, payload: dict[str, Any], *, source_count: int
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class QuestionPlanGeneration:
    case_id: str
    status: str
    steps: tuple[dict[str, Any], ...]
    telemetry: dict[str, Any] | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "error": self.error,
            "status": self.status,
            "steps": list(self.steps),
            "telemetry": self.telemetry,
        }


def run_question_planner(
    fixtures: Sequence[SynthesisFixture],
    *,
    backend_factory: Callable[[str, str], QuestionPlannerBackend],
) -> tuple[QuestionPlanGeneration, ...]:
    results: list[QuestionPlanGeneration] = []
    for fixture in fixtures:
        backend = backend_factory(
            QUESTION_PLANNER_INSTRUCTION, QUESTION_PLANNER_PROMPT_VERSION
        )
        raw = backend.generate_json_object(
            {"question": fixture.question},
            source_count=0,
        )
        raw_steps = raw.get("steps")
        try:
            if not isinstance(raw_steps, list):
                raise ValueError("question-plan steps must be a list")
            steps = tuple(
                QuestionPlanStep(
                    step_id=str(item.get("step_id", "")),
                    operation=item.get("operation", ""),
                    description=str(item.get("description", "")),
                    references=tuple(str(value) for value in item.get("references", ())),
                    emits_requirement=item.get("emits_requirement", True),
                )
                for item in raw_steps
                if isinstance(item, dict)
            )
            if len(steps) != len(raw_steps):
                raise ValueError("question-plan step must be an object")
            plan = QuestionOnlyPlan(fixture.question, steps)
            stored = tuple(
                {
                    "description": step.description,
                    "emits_requirement": step.emits_requirement,
                    "operation": step.operation,
                    "references": list(step.references),
                    "step_id": step.step_id,
                }
                for step in plan.steps
            )
            status = "planned"
            error = None
        except (TypeError, ValueError):
            stored = tuple(
                dict(item) for item in raw_steps if isinstance(item, dict)
            ) if isinstance(raw_steps, list) else ()
            status = "schema_error"
            error = "invalid_question_plan"
        telemetry = backend.last_generation_telemetry
        results.append(
            QuestionPlanGeneration(
                fixture.case_id,
                status,
                stored,
                None if telemetry is None else telemetry.to_dict(),
                error,
            )
        )
    return tuple(results)


__all__ = [
    "QuestionPlanGeneration",
    "QuestionPlannerBackend",
    "run_question_planner",
]
