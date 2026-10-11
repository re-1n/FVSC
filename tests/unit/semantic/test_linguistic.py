from __future__ import annotations

import hashlib

import pytest

from fvsc.ingest import SourceDocument
from fvsc.semantic import LinguisticFrontendResult, LinguisticToken


def _document(text: str) -> SourceDocument:
    return SourceDocument.create(
        source_id="public/synthetic/meaning-1.txt",
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=100.0,
        text=text,
        adapter="synthetic-test",
    )


def test_frontend_result_is_language_neutral_source_addressed_and_text_free() -> None:
    document = _document("Freedom requires responsibility.")
    tokens = (
        LinguisticToken.from_text(
            document.text,
            token_id="s1t1",
            sentence_id="s1",
            index=1,
            start=0,
            end=7,
            lemma="freedom",
            upos="NOUN",
            head_token_id="s1t2",
            dependency_relation="nsubj",
        ),
        LinguisticToken.from_text(
            document.text,
            token_id="s1t2",
            sentence_id="s1",
            index=2,
            start=8,
            end=16,
            lemma="require",
            upos="VERB",
            dependency_relation="root",
        ),
        LinguisticToken.from_text(
            document.text,
            token_id="s1t3",
            sentence_id="s1",
            index=3,
            start=17,
            end=31,
            lemma="responsibility",
            upos="NOUN",
            features=(("Number", "Sing"),),
            head_token_id="s1t2",
            dependency_relation="obj",
            confidence=0.9,
        ),
    )
    result = LinguisticFrontendResult(
        source_id=document.source_id,
        source_revision=document.source_revision,
        language_tag="en",
        frontend="synthetic-ud",
        frontend_version="1",
        tokens=tokens,
    )

    result.verify(document)
    payload = result.to_dict()

    assert LinguisticFrontendResult.from_dict(payload) == result
    assert result.digest == LinguisticFrontendResult.from_dict(payload).digest
    assert "Freedom" not in str(payload)
    assert all("text" not in item for item in payload["tokens"])


def test_frontend_result_rejects_cross_sentence_dependency() -> None:
    text = "One. Two."
    tokens = (
        LinguisticToken.from_text(
            text,
            token_id="s1t1",
            sentence_id="s1",
            index=1,
            start=0,
            end=3,
            head_token_id="s2t1",
            dependency_relation="dep",
        ),
        LinguisticToken.from_text(
            text,
            token_id="s2t1",
            sentence_id="s2",
            index=1,
            start=5,
            end=8,
        ),
    )

    with pytest.raises(ValueError, match="same sentence"):
        LinguisticFrontendResult(
            source_id="public/synthetic.txt",
            source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            language_tag="en",
            frontend="test",
            frontend_version="1",
            tokens=tokens,
        )


def test_frontend_result_detects_stale_source_revision() -> None:
    original = _document("Смысл меняется.")
    changed = _document("Смысл уточняется.")
    token = LinguisticToken.from_text(
        original.text,
        token_id="s1t1",
        sentence_id="s1",
        index=1,
        start=0,
        end=5,
    )
    result = LinguisticFrontendResult(
        source_id=original.source_id,
        source_revision=original.source_revision,
        language_tag="ru",
        frontend="test",
        frontend_version="1",
        tokens=(token,),
    )

    with pytest.raises(ValueError, match="source_revision"):
        result.verify(changed)
