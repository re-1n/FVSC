from __future__ import annotations

import pytest

from fvsc.evaluation.claim_first_synthesis import (
    INSUFFICIENT_CONTEXT_ANSWER,
    ClaimFirstOutput,
    evaluate_claim_first_gate,
    render_claim_first,
    render_claim_first_answer,
)
from fvsc.evaluation.synthesis import SynthesisArmSummary
from fvsc.interpretation import GeneratedClaim


def _summary(
    arm,
    *,
    recall=1.0,
    citations=1.0,
    prohibited=0,
    abstention=1.0,
):
    return SynthesisArmSummary(
        arm=arm,
        case_count=8,
        macro_required_recall=recall,
        mean_unsupported_facet_rate=0.0,
        mean_citation_correctness=citations,
        prohibited_violations=prohibited,
        role_violations=0,
        abstention_accuracy=abstention,
        prompt_tokens=None,
        output_tokens=None,
        mean_latency_seconds=None,
    )


def test_answer_is_deterministically_rendered_from_claims() -> None:
    output = ClaimFirstOutput(
        status="answered",
        claims=(
            GeneratedClaim("Ceramic was selected.", ("S1",)),
            GeneratedClaim("Application begins Monday.", ("S2",)),
        ),
    )
    rendered = render_claim_first(output)
    assert rendered.answer == "Ceramic was selected. Application begins Monday."
    assert rendered.claims == output.claims


def test_insufficient_output_cannot_smuggle_claims_or_answer_prose() -> None:
    output = ClaimFirstOutput(status="insufficient", claims=())
    assert render_claim_first_answer(output) == INSUFFICIENT_CONTEXT_ANSWER
    with pytest.raises(ValueError, match="no GeneratedInterpretation"):
        render_claim_first(output)
    with pytest.raises(ValueError, match="cannot contain claims"):
        ClaimFirstOutput(
            status="insufficient",
            claims=(GeneratedClaim("Zinc was selected.", ("S1",)),),
        )


def test_claim_first_rejects_non_evidence_bound_claims() -> None:
    with pytest.raises(ValueError, match="evidence-bound"):
        ClaimFirstOutput(
            status="answered",
            claims=(
                GeneratedClaim(
                    "Maybe ceramic.",
                    (),
                    support_level="free_generation",
                ),
            ),
        )


def test_claim_first_gate_requires_perfect_missing_link_abstention() -> None:
    baseline = _summary("baseline", abstention=0.5)
    assert evaluate_claim_first_gate(baseline, _summary("claim_first")).passed

    failed = evaluate_claim_first_gate(
        baseline,
        _summary("claim_first", prohibited=1, abstention=0.875),
    )
    assert not failed.passed
    assert "claim-first arm asserted prohibited relations" in failed.reasons
    assert "claim-first arm did not abstain on every missing-link case" in failed.reasons
