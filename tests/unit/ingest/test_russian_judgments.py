from __future__ import annotations

import hashlib

import pytest

from fvsc.ingest import RussianJudgmentExtractor, SourceDocument


@pytest.fixture(scope="module")
def extractor() -> RussianJudgmentExtractor:
    return RussianJudgmentExtractor()


def _document(text: str) -> SourceDocument:
    return SourceDocument.create(
        source_id="telegram/messages/message-1.json",
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=100.0,
        text=text,
        adapter="telegram-json",
        source_kind="owner_reflection",
    )


def test_extracts_exact_lemma_relation_and_negation(
    extractor: RussianJudgmentExtractor,
) -> None:
    document = _document("Свобода не требует подчинения.")

    candidates = extractor.extract(document)

    assert len(candidates) == 1
    judgment = candidates[0].judgment
    assert (judgment.subject, judgment.verb, judgment.object) == (
        "свобода",
        "требовать",
        "подчинение",
    )
    assert judgment.quality == "NEGATIVE"
    assert judgment.negation_scope is True
    assert judgment.clause_type == "GENERIC"
    assert judgment.interpretation_layer == 1
    assert judgment.defeasible is True
    candidates[0].source_span.verify(document)


def test_modal_envelope_applies_to_inner_clause_without_emitting_envelope(
    extractor: RussianJudgmentExtractor,
) -> None:
    document = _document("Я думаю, что внимание сканирует реальность.")

    judgments = [candidate.judgment for candidate in extractor.extract(document)]

    assert [(item.subject, item.verb, item.object) for item in judgments] == [
        ("внимание", "сканировать", "реальность")
    ]
    assert judgments[0].modality == pytest.approx(0.5)
    assert judgments[0].modality_type == "EPISTEMIC"
    assert "modal-envelope:думать" in judgments[0].inference_chain


def test_conditional_pair_has_stable_shared_id_and_roles(
    extractor: RussianJudgmentExtractor,
) -> None:
    document = _document("Если система хранит след, человек находит связь.")

    first = [candidate.judgment for candidate in extractor.extract(document)]
    replay = [candidate.judgment for candidate in extractor.extract(document)]

    assert [(item.subject, item.verb, item.object) for item in first] == [
        ("система", "хранить", "след"),
        ("человек", "находить", "связь"),
    ]
    assert {item.condition_role for item in first} == {"ANTECEDENT", "CONSEQUENT"}
    assert len({item.condition_id for item in first}) == 1
    assert [item.condition_id for item in first] == [item.condition_id for item in replay]
    assert all(item.modality_type == "CONDITIONAL" for item in first)
    assert all(item.modality == pytest.approx(0.4) for item in first)


def test_nominal_copula_and_adjective_are_separate_open_relations(
    extractor: RussianJudgmentExtractor,
) -> None:
    document = _document("Свобода — это ответственность. Внутри живой океан.")

    triples = {
        (candidate.judgment.subject, candidate.judgment.verb, candidate.judgment.object)
        for candidate in extractor.extract(document)
    }

    assert ("свобода", "cop:это", "ответственность") in triples
    assert ("океан", "amod", "живой") in triples


def test_quantifier_modifies_scope_without_becoming_an_attribute(
    extractor: RussianJudgmentExtractor,
) -> None:
    document = _document("Каждый человек строит мир.")

    judgments = [candidate.judgment for candidate in extractor.extract(document)]

    assert [(item.subject, item.verb, item.object) for item in judgments] == [
        ("человек", "строить", "мир")
    ]
    assert "quantifier:universal" in judgments[0].inference_chain
