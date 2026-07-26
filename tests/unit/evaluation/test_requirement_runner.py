from __future__ import annotations

from fvsc.evaluation.requirement_gate_fixtures import PUBLIC_REQUIREMENT_GATE_FIXTURES
from fvsc.evaluation.requirement_runner import run_requirement_pair


def test_requirement_runner_renders_claims_and_preserves_requirement_map() -> None:
    class Backend:
        last_generation_telemetry = None

        def __init__(self, arm):
            self.arm = arm

        def generate_json_object(self, payload, *, source_count):
            claims = [
                {
                    "text": "First.",
                    "citations": ["S1"],
                    "support_level": "evidence_bound",
                },
                {
                    "text": "Second.",
                    "citations": ["S2"],
                    "support_level": "evidence_bound",
                },
            ]
            if self.arm == "baseline":
                return {"answer": "Independent.", "claims": claims}
            return {
                "status": "answered",
                "requirements": [
                    {
                        "requirement_id": "R1",
                        "description": "first",
                        "status": "supported",
                        "claim_indices": [0],
                    },
                    {
                        "requirement_id": "R2",
                        "description": "second",
                        "status": "supported",
                        "claim_indices": [1],
                    },
                ],
                "claims": claims,
            }

    results = run_requirement_pair(
        PUBLIC_REQUIREMENT_GATE_FIXTURES[:1],
        backend_factory=lambda arm, prompt, version: Backend(arm),
    )
    requirement = results[1]
    assert requirement.arm == "requirement_coverage"
    assert requirement.answer == "First. Second."
    assert len(requirement.requirements) == 2


def test_requirement_runner_records_inconsistent_status_as_schema_error() -> None:
    class Backend:
        last_generation_telemetry = None

        def generate_json_object(self, payload, *, source_count):
            return {
                "status": "answered",
                "requirements": [
                    {
                        "requirement_id": "R1",
                        "description": "missing",
                        "status": "unsupported",
                        "claim_indices": [],
                    }
                ],
                "claims": [],
            }

    results = run_requirement_pair(
        PUBLIC_REQUIREMENT_GATE_FIXTURES[:1],
        backend_factory=lambda arm, prompt, version: Backend(),
    )
    assert all(item.status == "schema_error" for item in results)
