from __future__ import annotations

import hashlib

import pytest

from fvsc.ingest import SourceDocument
from fvsc.interpretation import (
    InterpretationClaim,
    InterpretationProposal,
    SourceCitation,
)


def _document(text: str = "Паразиты превращают внимание в чужой ресурс.") -> SourceDocument:
    return SourceDocument.create(
        source_id="telegram/diary/message-334",
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=10.0,
        text=text,
        adapter="telegram-export",
        source_kind="owner_reflection",
        raw_chars=len(text),
    )


def _proposal() -> InterpretationProposal:
    citation = SourceCitation.from_document(_document(), start=0, end=8)
    claim = InterpretationClaim.create(
        text="Паразит обозначает захват внимания.",
        citation_ids=(citation.citation_id,),
    )
    return InterpretationProposal.create(
        question="Какую роль играют паразиты?",
        answer=claim.text,
        claims=(claim,),
        citations=(citation,),
        interpretation_layer=2,
        producer="fvsc.owner-gold-comparison",
        prompt_version="1",
        generated_at=20.0,
        retrieval_method="lexical-char-ngram-v1",
    )


def test_source_citation_verifies_exact_document_revision_and_span() -> None:
    document = _document()
    citation = SourceCitation.from_document(document, start=0, end=8)

    citation.verify(document)
    assert SourceCitation.from_dict(citation.to_dict()) == citation

    with pytest.raises(ValueError, match="revision"):
        citation.verify(_document("Паразит меняет смысл."))


def test_proposal_is_content_addressed_round_trippable_and_outside_evidence() -> None:
    proposal = _proposal()
    replay = _proposal()

    assert replay.proposal_id == proposal.proposal_id
    assert proposal.cited_source_ids == ("telegram/diary/message-334",)
    assert proposal.support_level == "evidence_bound"
    assert proposal.defeasible is True
    assert InterpretationProposal.from_dict(proposal.to_dict()) == proposal
    assert "event_id" not in proposal.to_dict()


def test_claim_support_and_proposal_citation_boundaries_fail_closed() -> None:
    with pytest.raises(ValueError, match="require at least one citation"):
        InterpretationClaim.create(text="Unsupported", support_level="evidence_bound")

    free_claim = InterpretationClaim.create(
        text="Possible but unsupported",
        support_level="free_generation",
    )
    free_proposal = InterpretationProposal.create(
        question="What could this mean?",
        answer=free_claim.text,
        claims=(free_claim,),
        citations=(),
        interpretation_layer=3,
        producer="local-model",
        model="example",
        prompt_version="1",
        generated_at=1.0,
        retrieval_method="none",
    )
    assert free_proposal.support_level == "free_generation"

    citation = SourceCitation.from_document(_document())
    foreign = InterpretationClaim.create(
        text="Bound elsewhere",
        citation_ids=(citation.citation_id,),
    )
    with pytest.raises(ValueError, match="outside the proposal"):
        InterpretationProposal.create(
            question="Question",
            answer=foreign.text,
            claims=(foreign,),
            citations=(),
            interpretation_layer=2,
            producer="deterministic",
            prompt_version="1",
            generated_at=1.0,
            retrieval_method="lexical",
        )


def test_proposal_cannot_be_marked_non_defeasible() -> None:
    payload = _proposal().to_dict()
    payload["defeasible"] = False

    with pytest.raises(ValueError, match="remain defeasible"):
        InterpretationProposal.from_dict(payload)
