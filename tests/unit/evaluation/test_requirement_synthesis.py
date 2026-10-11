from __future__ import annotations

import pytest

from fvsc.evaluation.requirement_gate_fixtures import (
    PUBLIC_REQUIREMENT_GATE_FIXTURES,
)
from fvsc.evaluation.requirement_synthesis import (
    PARTIAL_CONTEXT_PREFIX,
    RequirementCoverage,
    RequirementCoverageOutput,
    evaluate_requirement_gate,
    render_requirement_answer,
)
from fvsc.evaluation.synthesis import SynthesisArmSummary
from fvsc.interpretation import GeneratedClaim


def test_requirement_output_enforces_complete_claim_linkage() -> None:
    output = RequirementCoverageOutput(
        "answered",
        (
            RequirementCoverage("R1", "location", "supported", (0,)),
            RequirementCoverage("R2", "reason", "supported", (1,)),
        ),
        (
            GeneratedClaim("Moved to the secure server.", ("S1",)),
            GeneratedClaim("The move followed an access breach.", ("S2",)),
        ),
    )
    assert render_requirement_answer(output) == (
        "Moved to the secure server. The move followed an access breach."
    )


def test_requirement_status_is_derived_from_supported_requirements() -> None:
    partial = RequirementCoverageOutput(
        "partial",
        (
            RequirementCoverage("R1", "known part", "supported", (0,)),
            RequirementCoverage("R2", "unknown part", "unsupported", ()),
        ),
        (GeneratedClaim("Known.", ("S1",)),),
    )
    assert render_requirement_answer(partial).startswith(PARTIAL_CONTEXT_PREFIX)
    with pytest.raises(ValueError, match="disagrees"):
        RequirementCoverageOutput(
            "answered",
            partial.requirements,
            partial.claims,
        )


def test_unreferenced_or_out_of_range_claims_fail_closed() -> None:
    with pytest.raises(ValueError, match="absent claim"):
        RequirementCoverageOutput(
            "answered",
            (RequirementCoverage("R1", "part", "supported", (1,)),),
            (GeneratedClaim("Known.", ("S1",)),),
        )
    with pytest.raises(ValueError, match="every claim"):
        RequirementCoverageOutput(
            "answered",
            (RequirementCoverage("R1", "part", "supported", (0,)),),
            (
                GeneratedClaim("Known.", ("S1",)),
                GeneratedClaim("Orphan.", ("S2",)),
            ),
        )


def test_heldout_requirement_gate_has_eight_positive_and_four_negative_cases() -> None:
    assert len(PUBLIC_REQUIREMENT_GATE_FIXTURES) == 12
    assert sum(item.should_abstain for item in PUBLIC_REQUIREMENT_GATE_FIXTURES) == 4
    assert len({item.case_id for item in PUBLIC_REQUIREMENT_GATE_FIXTURES}) == 12


def test_requirement_gate_fails_on_schema_or_status_errors() -> None:
    def summary(arm):
        return SynthesisArmSummary(
            arm, 12, 1.0, 0.0, 1.0, 0, 0, 1.0, None, None, None
        )

    decision = evaluate_requirement_gate(
        summary("baseline"),
        summary("requirement_coverage"),
        schema_error_count=1,
        status_error_count=1,
    )
    assert not decision.passed
    assert "requirement arm emitted schema errors" in decision.reasons
    assert "requirement arm misclassified held-out case status" in decision.reasons
