from __future__ import annotations

import hashlib

import pytest

from fvsc.ingest import SourceDocument
from fvsc.interpretation import (
    InterpretationClaim,
    InterpretationProposal,
    InterpretationStore,
    SourceCitation,
    load_interpretation_journal,
)


def _proposal() -> tuple[InterpretationProposal, str]:
    private_text = "Приватный исходный текст не должен попасть в журнал."
    document = SourceDocument.create(
        source_id="diary/private.md",
        source_revision=hashlib.sha256(private_text.encode("utf-8")).hexdigest(),
        observed_at=1.0,
        text=private_text,
        adapter="test",
        source_kind="owner_reflection",
        raw_chars=len(private_text),
    )
    citation = SourceCitation.from_document(document)
    claim = InterpretationClaim.create(
        text="Смысл предложен отдельно от исходника.",
        citation_ids=(citation.citation_id,),
    )
    proposal = InterpretationProposal.create(
        question="Что это значит?",
        answer=claim.text,
        claims=(claim,),
        citations=(citation,),
        interpretation_layer=3,
        producer="test",
        model="fake",
        prompt_version="1",
        generated_at=2.0,
        retrieval_method="lexical-char-ngram-v1",
    )
    return proposal, private_text


def test_store_persists_proposals_and_claim_level_owner_assessments(tmp_path) -> None:
    path = tmp_path / ".fvsc" / "interpretations.json"
    proposal, private_text = _proposal()
    store = InterpretationStore(path)

    assert store.append_proposal(proposal) is True
    assert store.append_proposal(proposal) is False
    assessment = store.record_assessment(
        proposal_id=proposal.proposal_id,
        case_id="interactive-1",
        verdict="accepted",
        accepted_claim_ids=(proposal.claims[0].claim_id,),
        reason_tags=("meaning-faithful",),
        recorded_at=3.0,
    )

    restored = InterpretationStore(path)
    assert restored.get_proposal(proposal.proposal_id) == proposal
    assert restored.latest_assessment(proposal.proposal_id) == assessment
    assert private_text not in path.read_text(encoding="utf-8")


def test_store_updates_are_validated_before_replacing_durable_state(tmp_path) -> None:
    path = tmp_path / "interpretations.json"
    proposal, _ = _proposal()
    store = InterpretationStore(path)
    store.append_proposal(proposal)
    before = path.read_bytes()

    with pytest.raises(ValueError, match="proper non-empty"):
        store.record_assessment(
            proposal_id=proposal.proposal_id,
            case_id="interactive-1",
            verdict="partially_accepted",
            accepted_claim_ids=(proposal.claims[0].claim_id,),
            recorded_at=3.0,
        )

    assert path.read_bytes() == before


def test_corrupt_and_symlinked_journals_fail_closed(tmp_path) -> None:
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="valid UTF-8 JSON"):
        load_interpretation_journal(corrupt)

    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises(ValueError, match="non-regular"):
        InterpretationStore(link)
