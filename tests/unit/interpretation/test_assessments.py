from __future__ import annotations

import hashlib

import pytest

from fvsc.ingest import SourceDocument
from fvsc.interpretation import (
    InterpretationClaim,
    InterpretationProposal,
    OwnerProposalAssessment,
    SourceCitation,
)


def _proposal(*, generated_at: float = 1.0) -> InterpretationProposal:
    text = "Один образ раскрывается в нескольких сообщениях."
    document = SourceDocument.create(
        source_id="message-10",
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=1.0,
        text=text,
        adapter="test",
        source_kind="owner_reflection",
        raw_chars=len(text),
    )
    citation = SourceCitation.from_document(document)
    first = InterpretationClaim.create(
        text="Сообщения используют общий образ.",
        citation_ids=(citation.citation_id,),
    )
    second = InterpretationClaim.create(
        text="Их следует считать одной мыслью.",
        citation_ids=(citation.citation_id,),
        support_level="partially_supported",
    )
    return InterpretationProposal.create(
        question="Связаны ли сообщения?",
        answer=f"{first.text} {second.text}",
        claims=(first, second),
        citations=(citation,),
        interpretation_layer=2,
        producer="test",
        prompt_version="1",
        generated_at=generated_at,
        retrieval_method="lexical",
    )


def test_owner_can_accept_all_claims_without_turning_assessment_into_evidence() -> None:
    proposal = _proposal()
    assessment = OwnerProposalAssessment.create(
        proposal,
        case_id="gold-010",
        verdict="accepted",
        accepted_claim_ids=tuple(claim.claim_id for claim in proposal.claims),
        reason_tags=("meaning-faithful", "citations-valid"),
        recorded_at=2.0,
    )

    assessment.verify(proposal)
    restored = OwnerProposalAssessment.from_dict(assessment.to_dict())
    restored.verify(proposal)
    assert restored == assessment
    assert "event_id" not in assessment.to_dict()


def test_partial_assessment_operates_at_claim_granularity() -> None:
    proposal = _proposal()
    assessment = OwnerProposalAssessment.create(
        proposal,
        case_id="gold-010",
        verdict="partially_accepted",
        accepted_claim_ids=(proposal.claims[0].claim_id,),
        rejected_claim_ids=(proposal.claims[1].claim_id,),
        reason_tags=("do-not-merge",),
        recorded_at=2.0,
    )

    assert assessment.accepted_claim_ids == (proposal.claims[0].claim_id,)
    assert assessment.rejected_claim_ids == (proposal.claims[1].claim_id,)


def test_verdict_shape_and_target_are_verified_against_the_proposal() -> None:
    proposal = _proposal()
    with pytest.raises(ValueError, match="accept every claim"):
        OwnerProposalAssessment.create(
            proposal,
            case_id="gold-010",
            verdict="accepted",
            accepted_claim_ids=(proposal.claims[0].claim_id,),
            recorded_at=2.0,
        )

    rejected = OwnerProposalAssessment.create(
        proposal,
        case_id="gold-010",
        verdict="rejected",
        rejected_claim_ids=tuple(claim.claim_id for claim in proposal.claims),
        recorded_at=2.0,
    )
    with pytest.raises(ValueError, match="does not target"):
        rejected.verify(_proposal(generated_at=3.0))
    assert rejected.verdict == "rejected"


def test_claim_cannot_be_both_accepted_and_rejected() -> None:
    proposal = _proposal()
    claim_id = proposal.claims[0].claim_id

    with pytest.raises(ValueError, match="both accepted and rejected"):
        OwnerProposalAssessment.create(
            proposal,
            case_id="gold-010",
            verdict="needs_revision",
            accepted_claim_ids=(claim_id,),
            rejected_claim_ids=(claim_id,),
            recorded_at=2.0,
        )
