from __future__ import annotations

import json

import pytest

from fvsc.ingest import load_telegram_export
from fvsc.retrieval import expand_source_context, search_documents


def _message(message_id, timestamp, text, **extra):
    return {
        "id": message_id,
        "type": "message",
        "date": timestamp,
        "text": text,
        "from_id": extra.pop("from_id", "owner"),
        **extra,
    }


def _export(tmp_path):
    path = tmp_path / "result.json"
    path.write_text(
        json.dumps(
            {
                "name": "private",
                "messages": [
                    _message(1, "2026-01-01T10:00:00Z", "предыстория к песне"),
                    _message(
                        2,
                        "2026-01-01T10:01:00Z",
                        "друзья пользовались героем как паразитические существа",
                        reply_to_message_id=1,
                    ),
                    _message(
                        3,
                        "2026-01-01T10:02:00Z",
                        "преобразившееся существо всё ещё хочет принятия и любви",
                        reply_to_message_id=2,
                    ),
                    _message(4, "2026-01-02T10:00:00Z", "совсем другая проектная идея"),
                    _message(
                        5,
                        "2026-01-03T10:00:00Z",
                        "чужой комментарий о метафорах",
                        from_id="participant",
                    ),
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return load_telegram_export(
        path,
        owner_author_ids={"owner"},
        source_namespace="same",
        temporal_context_seconds=30 * 60,
    )


def test_character_baseline_handles_inflection_and_keeps_source_provenance(tmp_path) -> None:
    result = _export(tmp_path)

    hits = search_documents(
        result.documents,
        "роль паразитов в моих метафорах",
        owner_adopted_only=True,
    )

    assert hits
    assert hits[0].document.metadata["message_id"] == "2"
    assert hits[0].source_id == "telegram/same/messages/message-2.json"
    assert hits[0].score > 0.0
    assert all(hit.document.metadata["owner_adopted_expression"] for hit in hits)


def test_reply_context_expands_both_framing_and_continuation(tmp_path) -> None:
    result = _export(tmp_path)
    source_id = "telegram/same/messages/message-2.json"

    context = expand_source_context(
        result.documents,
        source_id,
        max_depth=1,
        include_temporal=False,
    )

    assert [document.metadata["message_id"] for document in context] == ["1", "2", "3"]


def test_lexical_search_and_context_validation(tmp_path) -> None:
    result = _export(tmp_path)

    assert search_documents(result.documents, "") == ()
    with pytest.raises(ValueError, match="top_k"):
        search_documents(result.documents, "query", top_k=0)
    with pytest.raises(ValueError, match="ngram range"):
        search_documents(result.documents, "query", ngram_min=5, ngram_max=3)
    with pytest.raises(KeyError):
        expand_source_context(result.documents, "missing")
    with pytest.raises(ValueError, match="max_depth"):
        expand_source_context(result.documents, result.documents[0].source_id, max_depth=-1)
