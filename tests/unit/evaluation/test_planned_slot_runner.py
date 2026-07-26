from __future__ import annotations

from fvsc.evaluation.planned_slot_runner import run_planned_slots
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
