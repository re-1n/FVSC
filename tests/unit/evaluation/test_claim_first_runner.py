from __future__ import annotations

from fvsc.evaluation.claim_first_runner import run_claim_first_pair
from fvsc.evaluation.synthesis_consistency_fixtures import (
    PUBLIC_CONSISTENCY_FIXTURES,
)


def test_claim_first_runner_renders_only_claims_and_alternates_order() -> None:
    calls = []

    class Backend:
        last_generation_telemetry = None

        def __init__(self, arm):
            self.arm = arm

        def generate_json_object(self, payload, *, source_count):
            calls.append((self.arm, payload, source_count))
            if self.arm == "claim_first":
                return {"status": "insufficient", "claims": []}
            return {
                "answer": "Independent answer.",
                "claims": [
                    {
                        "text": "Cited claim.",
                        "citations": ["S1"],
                        "support_level": "evidence_bound",
                    }
                ],
            }

    results = run_claim_first_pair(
        PUBLIC_CONSISTENCY_FIXTURES[:2],
        backend_factory=lambda arm, prompt, version: Backend(arm),
    )
    assert [item.arm for item in results] == [
        "baseline",
        "claim_first",
        "claim_first",
        "baseline",
    ]
    assert results[1].answer == "INSUFFICIENT_CONTEXT"
    assert results[1].claims == ()
    assert calls[0][1] == calls[1][1]


def test_claim_first_runner_answer_is_exact_claim_rendering() -> None:
    class Backend:
        last_generation_telemetry = None

        def __init__(self, arm):
            self.arm = arm

        def generate_json_object(self, payload, *, source_count):
            if self.arm == "baseline":
                return {
                    "answer": "Baseline.",
                    "claims": [
                        {
                            "text": "Baseline claim.",
                            "citations": ["S1"],
                            "support_level": "evidence_bound",
                        }
                    ],
                }
            return {
                "status": "answered",
                "claims": [
                    {
                        "text": "Ceramic was selected.",
                        "citations": ["S1"],
                        "support_level": "evidence_bound",
                    },
                    {
                        "text": "Application begins on 14 September.",
                        "citations": ["S2"],
                        "support_level": "evidence_bound",
                    },
                ],
            }

    results = run_claim_first_pair(
        PUBLIC_CONSISTENCY_FIXTURES[:1],
        backend_factory=lambda arm, prompt, version: Backend(arm),
    )
    claim_first = results[1]
    assert claim_first.answer == (
        "Ceramic was selected. Application begins on 14 September."
    )


def test_schema_invalid_generation_is_recorded_without_normalization() -> None:
    class Backend:
        last_generation_telemetry = None

        def generate_json_object(self, payload, *, source_count):
            return {
                "answer": "Maybe selected.",
                "claims": [
                    {
                        "text": "Maybe selected.",
                        "citations": ["S1"],
                        "support_level": "free_generation",
                    }
                ],
            }

    results = run_claim_first_pair(
        PUBLIC_CONSISTENCY_FIXTURES[:1],
        backend_factory=lambda arm, prompt, version: Backend(),
    )
    assert all(item.status == "schema_error" for item in results)
    assert all(item.error == "invalid_structured_output" for item in results)
    assert results[0].claims[0]["support_level"] == "free_generation"
