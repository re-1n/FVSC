from __future__ import annotations

from fvsc.evaluation.planned_slot_runner import (
    guard_planned_slot_generation,
    run_planned_slots,
)
from fvsc.evaluation.planned_slot_synthesis import (
    FrozenQuestionPlan,
    PlannedRequirement,
)
from fvsc.evaluation.requirement_gate_fixtures import PUBLIC_REQUIREMENT_GATE_FIXTURES


def test_planned_slot_runner_fills_exact_input_slots() -> None:
    class Backend:
        last_generation_telemetry = None

        def generate_json_object(self, payload, *, source_count):
            return {
                "slots": [
                    {
                        "requirement_id": item["requirement_id"],
                        "status": "supported",
                        "claim": {
                            "text": item["description"] + ".",
                            "citations": ["S1"],
                            "support_level": "evidence_bound",
                        },
                    }
                    for item in payload["requirements"]
                ]
            }

    results = run_planned_slots(
        PUBLIC_REQUIREMENT_GATE_FIXTURES,
        backend_factory=lambda prompt, version: Backend(),
    )
    assert len(results) == 12
    assert all(item.status == "answered" for item in results)


def test_planned_slot_runner_fails_closed_on_missing_slots() -> None:
    class Backend:
        last_generation_telemetry = None

        def generate_json_object(self, payload, *, source_count):
            return {"slots": []}

    results = run_planned_slots(
        PUBLIC_REQUIREMENT_GATE_FIXTURES,
        backend_factory=lambda prompt, version: Backend(),
    )
    assert all(item.status == "schema_error" for item in results)


def test_planned_slot_runner_accepts_an_explicit_new_plan_set() -> None:
    fixture = PUBLIC_REQUIREMENT_GATE_FIXTURES[0]
    plans = {
        fixture.case_id: FrozenQuestionPlan(
            fixture.case_id,
            (
                PlannedRequirement("R1", "primary plan"),
                PlannedRequirement("R2", "heat condition"),
            ),
        )
    }

    class Backend:
        last_generation_telemetry = None

        def generate_json_object(self, payload, *, source_count):
            return {
                "slots": [
                    {
                        "requirement_id": item["requirement_id"],
                        "status": "unsupported",
                        "claim": None,
                    }
                    for item in payload["requirements"]
                ]
            }

    result = run_planned_slots(
        (fixture,),
        backend_factory=lambda prompt, version: Backend(),
        plans_by_case=plans,
    )
    assert result[0].status == "insufficient"


def test_planned_slot_runner_demotes_claim_outside_relation_eligible_sources() -> None:
    fixture = PUBLIC_REQUIREMENT_GATE_FIXTURES[0]
    plans = {
        fixture.case_id: FrozenQuestionPlan(
            fixture.case_id,
            (
                PlannedRequirement("R1", "primary plan"),
                PlannedRequirement("R2", "heat condition"),
            ),
        )
    }

    class Backend:
        last_generation_telemetry = None

        def generate_json_object(self, payload, *, source_count):
            return {
                "slots": [
                    {
                        "requirement_id": "R1",
                        "status": "supported",
                        "claim": {
                            "text": "Routine plan.",
                            "citations": ["S1"],
                            "support_level": "evidence_bound",
                        },
                    },
                    {
                        "requirement_id": "R2",
                        "status": "supported",
                        "claim": {
                            "text": "Heat condition.",
                            "citations": ["S1"],
                            "support_level": "evidence_bound",
                        },
                    },
                ]
            }

    result = run_planned_slots(
        (fixture,),
        backend_factory=lambda prompt, version: Backend(),
        plans_by_case=plans,
        eligible_labels_by_case={
            fixture.case_id: {"R1": ("S1",), "R2": ("S2",)}
        },
    )
    assert result[0].status == "partial"
    assert result[0].slots[1]["status"] == "unsupported"
    assert result[0].slots[1]["claim"] is None

    raw = run_planned_slots(
        (fixture,),
        backend_factory=lambda prompt, version: Backend(),
        plans_by_case=plans,
    )[0]
    guarded = guard_planned_slot_generation(
        raw,
        plans[fixture.case_id],
        {"R1": ("S1",), "R2": ("S2",)},
    )
    assert guarded.status == "partial"
    assert guarded.slots == result[0].slots
