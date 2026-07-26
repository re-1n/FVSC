from __future__ import annotations

from types import SimpleNamespace

from fvsc.evaluation.synthesis import (
    GoldFacet,
    SynthesisFixture,
    SyntheticSource,
)
from fvsc.evaluation.synthesis_runner import (
    run_synthesis_pair,
    synthesis_system_prompt,
)
from fvsc.interpretation import GeneratedClaim, GeneratedInterpretation


def _fixtures() -> tuple[SynthesisFixture, ...]:
    return tuple(
        SynthesisFixture(
            case_id=f"C{index}",
            question="What are both facts?",
            sources=(
                SyntheticSource("S1", "First fact."),
                SyntheticSource("S2", "Second fact."),
            ),
            facets=(
                GoldFacet("first", "required", ("S1",)),
                GoldFacet("second", "required", ("S2",)),
            ),
        )
        for index in (1, 2)
    )


def test_runner_pairs_identical_sources_and_alternates_arm_order() -> None:
    calls = []

    class Backend:
        backend_id = "fake"
        model = "fake-model"
        interpretation_layer = 3

        def __init__(self, arm, system_prompt, prompt_version):
            self.arm = arm
            self.system_prompt = system_prompt
            self.prompt_version = prompt_version
            self.last_generation_telemetry = None

        def generate(self, question, sources):
            calls.append((self.arm, question, tuple((item.label, item.text) for item in sources)))
            return GeneratedInterpretation(
                answer=f"{self.arm} answer",
                claims=(
                    GeneratedClaim(
                        text="First.",
                        source_labels=("S1",),
                    ),
                ),
            )

    bundle = run_synthesis_pair(
        _fixtures(),
        backend_factory=lambda arm, prompt, version: Backend(arm, prompt, version),
    )

    assert [item[0] for item in calls] == [
        "baseline",
        "coverage",
        "coverage",
        "baseline",
    ]
    assert calls[0][2] == calls[1][2]
    assert len(bundle.generations) == 4
    assert len(bundle.to_dict()["review_template"]) == 4


def test_prompts_differ_only_in_registered_arm_instruction() -> None:
    baseline = synthesis_system_prompt("baseline")
    coverage = synthesis_system_prompt("coverage")
    assert baseline != coverage
    assert "required" not in coverage
    assert baseline.split("\n\n", 1)[1] == coverage.split("\n\n", 1)[1]
