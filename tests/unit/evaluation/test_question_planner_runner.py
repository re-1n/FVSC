from __future__ import annotations

from fvsc.evaluation.question_planner_runner import run_question_planner
from fvsc.evaluation.requirement_gate_fixtures import PUBLIC_REQUIREMENT_GATE_FIXTURES


def test_question_planner_receives_no_sources() -> None:
    payloads = []

    class Backend:
        last_generation_telemetry = None

        def generate_json_object(self, payload, *, source_count):
            payloads.append((payload, source_count))
            return {
                "steps": [
                    {
                        "step_id": "S1",
                        "operation": "select",
                        "description": "requested information",
                        "references": [],
                        "emits_requirement": True,
                    }
                ]
            }

    results = run_question_planner(
        PUBLIC_REQUIREMENT_GATE_FIXTURES,
        backend_factory=lambda prompt, version: Backend(),
    )
    assert all(item.status == "planned" for item in results)
    assert all(set(payload) == {"question"} and count == 0 for payload, count in payloads)


def test_question_planner_fails_closed_on_invalid_dependencies() -> None:
    class Backend:
        last_generation_telemetry = None

        def generate_json_object(self, payload, *, source_count):
            return {
                "steps": [
                    {
                        "step_id": "S1",
                        "operation": "project",
                        "description": "unsupported dependency",
                        "references": ["S2"],
                    }
                ]
            }

    results = run_question_planner(
        PUBLIC_REQUIREMENT_GATE_FIXTURES[:1],
        backend_factory=lambda prompt, version: Backend(),
    )
    assert results[0].status == "schema_error"
