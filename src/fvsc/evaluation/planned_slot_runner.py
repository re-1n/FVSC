"""Runner for the controlled frozen-question-plan synthesis ablation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence

from ..integrations.ollama import OllamaGenerationTelemetry
from .claim_first_runner import _claims
from .planned_slot_fixtures import QUESTION_PLAN_BY_CASE
from .planned_slot_synthesis import (
    PLANNED_SLOT_INSTRUCTION,
    PLANNED_SLOT_PROMPT_VERSION,
    FilledRequirementSlot,
    FrozenQuestionPlan,
    PlannedSlotOutput,
    normalize_empty_claim_sentinel,
    render_planned_slot_answer,
)
from .synthesis import SynthesisFixture


class PlannedSlotBackend(Protocol):
    last_generation_telemetry: OllamaGenerationTelemetry | None

    def generate_json_object(
        self, payload: dict[str, Any], *, source_count: int
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class PlannedSlotGeneration:
    case_id: str
    status: str
    answer: str
    slots: tuple[dict[str, Any], ...]
    telemetry: dict[str, Any] | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "case_id": self.case_id,
            "error": self.error,
            "slots": list(self.slots),
            "status": self.status,
            "telemetry": self.telemetry,
        }


def guard_planned_slot_generation(
    generation: PlannedSlotGeneration,
    plan: FrozenQuestionPlan,
    eligible_labels_by_requirement: Mapping[str, tuple[str, ...]],
) -> PlannedSlotGeneration:
    """Fail closed on generated citations lacking a typed relation cue."""

    if generation.error is not None:
        return generation
    slots = []
    stored = []
    for item in generation.slots:
        requirement_id = str(item.get("requirement_id", ""))
        status = item.get("status", "")
        claim_value = item.get("claim")
        claim = None if claim_value is None else _claims([claim_value])[0]
        if (
            claim is not None
            and not set(claim.source_labels)
            <= set(eligible_labels_by_requirement.get(requirement_id, ()))
        ):
            status = "unsupported"
            claim = None
        slot = FilledRequirementSlot(requirement_id, status, claim)
        slots.append(slot)
        stored.append(
            {
                "claim": (
                    None
                    if claim is None
                    else {
                        "citations": list(claim.source_labels),
                        "support_level": claim.support_level,
                        "text": claim.text,
                    }
                ),
                "requirement_id": requirement_id,
                "status": status,
            }
        )
    output = PlannedSlotOutput(plan, tuple(slots))
    return PlannedSlotGeneration(
        generation.case_id,
        output.status,
        render_planned_slot_answer(output),
        tuple(stored),
        generation.telemetry,
        generation.error,
    )


def run_planned_slots(
    fixtures: Sequence[SynthesisFixture],
    *,
    backend_factory: Callable[[str, str], PlannedSlotBackend],
    plans_by_case: Mapping[str, FrozenQuestionPlan] | None = None,
    instruction: str = PLANNED_SLOT_INSTRUCTION,
    prompt_version: str = PLANNED_SLOT_PROMPT_VERSION,
    eligible_labels_by_case: Mapping[str, Mapping[str, tuple[str, ...]]] | None = None,
) -> tuple[PlannedSlotGeneration, ...]:
    plans = QUESTION_PLAN_BY_CASE if plans_by_case is None else plans_by_case
    expected_ids = tuple(item.case_id for item in fixtures)
    if set(expected_ids) != set(plans):
        raise ValueError("planned-slot run requires the complete frozen fixture set")
    results: list[PlannedSlotGeneration] = []
    for fixture in fixtures:
        plan = plans[fixture.case_id]
        backend = backend_factory(instruction, prompt_version)
        raw = backend.generate_json_object(
            {
                "question": fixture.question,
                "requirements": [
                    {
                        "requirement_id": item.requirement_id,
                        "description": item.description,
                    }
                    for item in plan.requirements
                ],
                "sources": [
                    {"label": source.label, "text": source.text}
                    for source in fixture.sources
                ],
            },
            source_count=len(fixture.sources),
        )
        error = None
        raw_slots = raw.get("slots")
        try:
            if not isinstance(raw_slots, list):
                raise ValueError("planned slots must be a list")
            slots: list[FilledRequirementSlot] = []
            stored: list[dict[str, Any]] = []
            for item in raw_slots:
                if not isinstance(item, dict):
                    raise ValueError("planned slot must be an object")
                claim_value = normalize_empty_claim_sentinel(
                    item.get("status"),
                    item.get("claim"),
                )
                claim = (
                    None
                    if claim_value is None
                    else _claims([claim_value])[0]
                )
                requirement_id = str(item.get("requirement_id", ""))
                if (
                    claim is not None
                    and eligible_labels_by_case is not None
                    and not set(claim.source_labels)
                    <= set(
                        eligible_labels_by_case[fixture.case_id].get(
                            requirement_id, ()
                        )
                    )
                ):
                    claim = None
                    item = dict(item)
                    item["status"] = "unsupported"
                slot = FilledRequirementSlot(
                    requirement_id,
                    item.get("status", ""),
                    claim,
                )
                slots.append(slot)
                stored.append(
                    {
                        "claim": (
                            None
                            if claim is None
                            else {
                                "citations": list(claim.source_labels),
                                "support_level": claim.support_level,
                                "text": claim.text,
                            }
                        ),
                        "requirement_id": slot.requirement_id,
                        "status": slot.status,
                    }
                )
            output = PlannedSlotOutput(plan, tuple(slots))
            status = output.status
            answer = render_planned_slot_answer(output)
            stored_slots = tuple(stored)
        except (IndexError, ValueError):
            status = "schema_error"
            answer = "SCHEMA_ERROR"
            stored_slots = tuple(
                dict(item) for item in raw_slots if isinstance(item, dict)
            ) if isinstance(raw_slots, list) else ()
            error = "invalid_structured_output"
        telemetry = backend.last_generation_telemetry
        results.append(
            PlannedSlotGeneration(
                fixture.case_id,
                status,
                answer,
                stored_slots,
                None if telemetry is None else telemetry.to_dict(),
                error,
            )
        )
    return tuple(results)


__all__ = [
    "PlannedSlotGeneration",
    "PlannedSlotBackend",
    "guard_planned_slot_generation",
    "run_planned_slots",
]
