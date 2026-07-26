from __future__ import annotations

import hashlib

import pytest

from fvsc.evaluation import (
    EvidenceRef,
    GoldCase,
    GoldLink,
    evaluate_interpretation_proposal,
    summarize_interpretation_evaluations,
    surface_similarity,
)
from fvsc.ingest import SourceDocument
from fvsc.interpretation import (
    InterpretationClaim,
    InterpretationProposal,
    SourceCitation,
)


def _document(source_id: str, text: str) -> SourceDocument:
    return SourceDocument.create(
        source_id=source_id,
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=1.0,
        text=text,
        adapter="test",
        source_kind="owner_reflection",
        raw_chars=len(text),
    )


def _case() -> GoldCase:
    return GoldCase(
        case_id="gold-001",
        title="Open metaphor",
        question="Какую роль играют паразиты?",
        decision="accepted",
        evidence=(
            EvidenceRef("Diary:334", "message-334", "primary"),
            EvidenceRef("Diary:335", "message-335", "support"),
            EvidenceRef("Diary:333", "message-333", "context"),
            EvidenceRef("Diary:900", "message-900", "negative"),
        ),
        links=(GoldLink("Diary:334", "Diary:900", "separate"),),
        owner_interpretation="Паразиты обозначают захват и перенаправление внимания.",
        rejected_interpretations=("Паразит — это буквальное животное.",),
    )


def _citation(source_id: str, text: str) -> SourceCitation:
    return SourceCitation.from_document(_document(source_id, text))


def _proposal(*, include_forbidden: bool) -> InterpretationProposal:
    primary = _citation("message-334", "Паразиты захватывают внимание.")
    support = _citation("message-335", "Внимание становится чужим ресурсом.")
    negative = _citation("message-900", "Буквальный биологический паразит.")
    first = InterpretationClaim.create(
        text="Паразит обозначает захват внимания.",
        citation_ids=(primary.citation_id, support.citation_id),
    )
    claims = (first,)
    citations = (primary, support)
    if include_forbidden:
        forbidden = InterpretationClaim.create(
            text="Буквальный паразит и метафора являются одной мыслью.",
            citation_ids=(primary.citation_id, negative.citation_id),
        )
        claims += (forbidden,)
        citations += (negative,)
    return InterpretationProposal.create(
        question=_case().question,
        answer=" ".join(claim.text for claim in claims),
        claims=claims,
        citations=citations,
        interpretation_layer=2,
        producer="test",
        prompt_version="1",
        generated_at=1.0,
        retrieval_method="lexical",
    )


def test_evaluation_rewards_source_coverage_without_calling_surface_match_truth() -> None:
    result = evaluate_interpretation_proposal(_case(), _proposal(include_forbidden=False))

    assert result.primary_citation_recall == pytest.approx(1.0)
    assert result.relevant_citation_recall == pytest.approx(1.0)
    assert result.context_citation_recall == pytest.approx(0.0)
    assert result.citation_precision == pytest.approx(1.0)
    assert result.negative_citation_count == 0
    assert result.forbidden_link_violations == 0
    assert result.structurally_safe is True
    assert result.surface_similarity_to_owner is not None
    assert 0.0 < result.surface_similarity_to_owner < 1.0


def test_separate_link_is_forbidden_only_when_one_claim_composes_both_sources() -> None:
    result = evaluate_interpretation_proposal(_case(), _proposal(include_forbidden=True))

    assert result.negative_citation_count == 1
    assert result.forbidden_link_violations == 1
    assert result.citation_precision == pytest.approx(2 / 3)
    assert result.structurally_safe is False


def test_free_generation_is_visible_and_summary_rejects_duplicate_cases() -> None:
    claim = InterpretationClaim.create(
        text="Непроверенная гипотеза.", support_level="free_generation"
    )
    proposal = InterpretationProposal.create(
        question=_case().question,
        answer=claim.text,
        claims=(claim,),
        citations=(),
        interpretation_layer=3,
        producer="test",
        prompt_version="1",
        generated_at=2.0,
        retrieval_method="none",
    )
    result = evaluate_interpretation_proposal(_case(), proposal)
    summary = summarize_interpretation_evaluations((result,))

    assert result.unsupported_claim_count == 1
    assert result.citation_precision is None
    assert summary.unsupported_claim_count == 1
    assert summary.structurally_safe_cases == 0
    with pytest.raises(ValueError, match="duplicate case ids"):
        summarize_interpretation_evaluations((result, result))


def test_question_mismatch_fails_closed_and_surface_similarity_is_symmetric() -> None:
    proposal = _proposal(include_forbidden=False)
    wrong_case = GoldCase(
        case_id="other",
        title="Other",
        question="Другой вопрос",
        decision="open",
        evidence=(),
    )

    with pytest.raises(ValueError, match="question"):
        evaluate_interpretation_proposal(wrong_case, proposal)
    assert surface_similarity("роль паразитов", "паразиты и их роль") == pytest.approx(
        surface_similarity("паразиты и их роль", "роль паразитов")
    )
