from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from fvsc.evaluation import (
    EvidenceRef,
    FrozenCandidateBundle,
    GoldCase,
    Stage4hModelConfig,
    Stage4hRunSpec,
    corpus_digest,
    freeze_stage4h_candidates,
)
from fvsc.ingest import SourceDocument
from fvsc.retrieval import LexicalSearchIndex


def _document(
    source_id: str,
    text: str,
    *,
    observed_at: float,
    reply_to_source_id: str | None = None,
    ingest_status: str | None = None,
    message_id: str | None = None,
) -> SourceDocument:
    metadata = {}
    if reply_to_source_id is not None:
        metadata["reply_to_source_id"] = reply_to_source_id
    if ingest_status is not None:
        metadata["ingest_status"] = ingest_status
    if message_id is not None:
        metadata["message_id"] = message_id
    return SourceDocument.create(
        source_id=source_id,
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=observed_at,
        text=text,
        adapter="test",
        source_kind="owner_reflection",
        raw_chars=len(text),
        metadata=metadata,
    )


class _StructuralIndex:
    def __init__(self, hits=()):
        self.hits = tuple(hits)

    def search(self, query: str, *, top_k: int = 10):
        return self.hits[:top_k]


def _spec(documents, *, cases=("gold-001",), **changes) -> Stage4hRunSpec:
    values = {
        "gold_sha256": "a" * 64,
        "challenge_sha256": "b" * 64,
        "corpus_sha256": corpus_digest(documents),
        "case_ids": cases,
        "arms": ("A0", "A1", "A2", "A4"),
        "model": Stage4hModelConfig(
            backend_id="ollama.local",
            model="test",
            prompt_version="stage4h-v1",
        ),
        "created_at": 1.0,
        "top_k": 1,
        "prompt_source_cap": 2,
        "context_depth": 1,
    }
    values.update(changes)
    return Stage4hRunSpec(**values)


def _case() -> GoldCase:
    return GoldCase(
        case_id="gold-001",
        title="Metaphor",
        question="Какую роль играют паразиты?",
        decision="open",
        evidence=(
            EvidenceRef("Diary:1", "message-1", "primary"),
            EvidenceRef("Diary:2", "message-2", "context"),
            EvidenceRef("Diary:9", "message-9", "negative"),
        ),
        owner_interpretation="Скрытая интерпретация владельца не является prompt input.",
    )


def test_freeze_keeps_a0_a1_identical_and_excludes_gold_meaning_and_negatives() -> None:
    documents = (
        _document("message-1", "Паразиты захватывают внимание.", observed_at=1.0),
        _document(
            "message-2",
            "Внимание становится чужим ресурсом.",
            observed_at=2.0,
            reply_to_source_id="message-1",
        ),
        _document("message-9", "Буквальный паразит.", observed_at=9.0),
    )
    spec = _spec(documents)
    bundle = freeze_stage4h_candidates(
        spec=spec,
        cases=(_case(),),
        documents=documents,
        lexical_index=LexicalSearchIndex(documents),
        structural_index=_StructuralIndex(),
    )

    a0 = bundle.for_case_arm("gold-001", "A0")
    a1 = bundle.for_case_arm("gold-001", "A1")
    assert [item.to_dict() for item in a0.candidates] == [
        item.to_dict() for item in a1.candidates
    ]
    assert a1.candidates[0].source_id == "message-1"
    assert a1.candidates[1].source_id == "message-2"
    assert a1.candidates[1].expanded_from_source_id == "message-1"

    oracle = bundle.for_case_arm("gold-001", "A2")
    assert tuple(item.source_id for item in oracle.candidates) == (
        "message-1",
        "message-2",
    )
    encoded = json.dumps(bundle.to_dict(), ensure_ascii=False)
    assert "Скрытая интерпретация" not in encoded
    assert "message-9" not in tuple(item.source_id for item in oracle.candidates)
    assert FrozenCandidateBundle.from_dict(json.loads(encoded)) == bundle


def test_structural_arm_never_falls_back_to_lexical() -> None:
    documents = (
        _document("message-1", "Паразиты захватывают внимание.", observed_at=1.0),
        _document("message-2", "Другой текст.", observed_at=2.0),
        _document("message-9", "Негатив.", observed_at=9.0),
    )
    bundle = freeze_stage4h_candidates(
        spec=_spec(documents),
        cases=(_case(),),
        documents=documents,
        lexical_index=LexicalSearchIndex(documents),
        structural_index=_StructuralIndex(),
    )

    assert bundle.for_case_arm("gold-001", "A1").candidates
    assert bundle.for_case_arm("gold-001", "A4").candidates == ()
    assert bundle.for_case_arm("gold-001", "A4").retrieval_method == (
        "source-locator-v1+judgment-char-tfidf-v1+text-context-v1"
    )


def test_explicit_query_locator_anchors_lexical_and_structural_arms() -> None:
    anchor = _document(
        "telegram/private-diary/messages/message-747.json",
        "Поэтический фрагмент без слова реальный.",
        observed_at=1.0,
        message_id="747",
    )
    lexical_decoy = _document(
        "telegram/private-diary/messages/message-1.json",
        "Реальный человек или вымышленный человек?",
        observed_at=2.0,
        message_id="1",
    )
    case = GoldCase(
        case_id="gold-001",
        title="Referent",
        question="Можно ли по Diary:747 установить, был ли человек реальным?",
        decision="open",
        evidence=(EvidenceRef("Diary:747", anchor.source_id, "primary"),),
    )
    structural_hit = SimpleNamespace(
        source_id=lexical_decoy.source_id,
        score=0.9,
        evidence_event_ids=("e" * 64,),
    )
    documents = (anchor, lexical_decoy)

    bundle = freeze_stage4h_candidates(
        spec=_spec(documents),
        cases=(case,),
        documents=documents,
        lexical_index=LexicalSearchIndex(documents),
        structural_index=_StructuralIndex((structural_hit,)),
    )

    for arm in ("A1", "A4"):
        candidates = bundle.for_case_arm("gold-001", arm).candidates
        assert candidates[0].source_id == anchor.source_id
        assert candidates[0].score == 1.0


def test_unresolved_explicit_query_locator_fails_before_generation() -> None:
    document = _document(
        "telegram/private-diary/messages/message-1.json",
        "Другой текст.",
        observed_at=1.0,
        message_id="1",
    )
    case = GoldCase(
        case_id="gold-001",
        title="Missing locator",
        question="Что находится в Diary:747?",
        decision="open",
        evidence=(EvidenceRef("Diary:1", document.source_id, "primary"),),
    )

    with pytest.raises(ValueError, match="Diary:747=absent"):
        freeze_stage4h_candidates(
            spec=_spec((document,)),
            cases=(case,),
            documents=(document,),
            lexical_index=LexicalSearchIndex((document,)),
            structural_index=_StructuralIndex(),
        )


def test_structural_candidates_keep_event_ids_and_source_revisions() -> None:
    documents = (
        _document("message-1", "Паразиты захватывают внимание.", observed_at=1.0),
        _document("message-2", "Контекст.", observed_at=2.0),
        _document("message-9", "Негатив.", observed_at=9.0),
    )
    event_id = "e" * 64
    hit = SimpleNamespace(
        source_id="message-2",
        score=0.8,
        evidence_event_ids=(event_id,),
    )
    bundle = freeze_stage4h_candidates(
        spec=_spec(documents),
        cases=(_case(),),
        documents=documents,
        lexical_index=LexicalSearchIndex(documents),
        structural_index=_StructuralIndex((hit,)),
    )

    frozen = bundle.for_case_arm("gold-001", "A4").candidates[0]
    assert frozen.source_revision == documents[1].source_revision
    assert frozen.evidence_event_ids == (event_id,)


def test_freeze_skips_textless_context_without_removing_it_from_corpus() -> None:
    documents = (
        _document("message-1", "Паразиты захватывают внимание.", observed_at=1.0),
        _document(
            "message-media",
            "",
            observed_at=2.0,
            reply_to_source_id="message-1",
            ingest_status="deferred_media",
        ),
        _document(
            "message-2",
            "Контекст после изображения.",
            observed_at=3.0,
            reply_to_source_id="message-1",
        ),
        _document("message-9", "Негатив.", observed_at=9.0),
    )
    hit = SimpleNamespace(
        source_id="message-1",
        score=0.8,
        evidence_event_ids=("e" * 64,),
    )
    bundle = freeze_stage4h_candidates(
        spec=_spec(documents, prompt_source_cap=3),
        cases=(_case(),),
        documents=documents,
        lexical_index=LexicalSearchIndex(documents),
        structural_index=_StructuralIndex((hit,)),
    )

    assert "message-media" in {document.source_id for document in documents}
    for arm in ("A1", "A4"):
        candidates = bundle.for_case_arm("gold-001", arm).candidates
        assert tuple(item.source_id for item in candidates) == (
            "message-1",
            "message-2",
        )
        assert tuple(item.rank for item in candidates) == (1, 2)


def test_freeze_rejects_textless_direct_oracle_source() -> None:
    documents = (
        _document(
            "message-1",
            "",
            observed_at=1.0,
            ingest_status="deferred_media",
        ),
        _document("message-2", "Контекст.", observed_at=2.0),
        _document("message-9", "Негатив.", observed_at=9.0),
    )

    with pytest.raises(ValueError, match="oracle source has no text"):
        freeze_stage4h_candidates(
            spec=_spec(documents),
            cases=(_case(),),
            documents=documents,
            lexical_index=LexicalSearchIndex(documents),
            structural_index=_StructuralIndex(),
        )


def test_freeze_fails_closed_on_corpus_drift_and_missing_oracle_source() -> None:
    documents = (
        _document("message-1", "Паразиты захватывают внимание.", observed_at=1.0),
        _document("message-2", "Контекст.", observed_at=2.0),
        _document("message-9", "Негатив.", observed_at=9.0),
    )
    spec = _spec(documents)
    changed = documents + (_document("new", "Новый текст.", observed_at=10.0),)
    with pytest.raises(ValueError, match="corpus"):
        freeze_stage4h_candidates(
            spec=spec,
            cases=(_case(),),
            documents=changed,
            lexical_index=LexicalSearchIndex(changed),
            structural_index=_StructuralIndex(),
        )

    with pytest.raises(ValueError, match="gold sources"):
        freeze_stage4h_candidates(
            spec=_spec(documents[:-1]),
            cases=(_case(),),
            documents=documents[:-1],
            lexical_index=LexicalSearchIndex(documents[:-1]),
            structural_index=_StructuralIndex(),
        )
