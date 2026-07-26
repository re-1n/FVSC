from __future__ import annotations

import hashlib

from fvsc.ingest import SourceDocument
from fvsc.retrieval import SourceLocatorIndex, parse_source_locators


def _document(namespace: str, message_id: str, text: str = "text") -> SourceDocument:
    return SourceDocument.create(
        source_id=f"telegram/{namespace}/messages/message-{message_id}.json",
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=1.0,
        text=text,
        adapter="telegram-export",
        source_kind="owner_reflection",
        raw_chars=len(text),
        metadata={"message_id": message_id},
    )


def test_query_locator_resolves_exact_namespace_and_safe_token_alias() -> None:
    document = _document("private-diary", "747")
    index = SourceLocatorIndex((document,))

    exact = index.resolve_query("Проверь private-diary:747")[0]
    alias = index.resolve_query("Можно ли по Diary:747 это установить?")[0]

    assert exact.status == "resolved"
    assert exact.match_kind == "exact_namespace"
    assert exact.source_id == document.source_id
    assert alias.status == "resolved"
    assert alias.match_kind == "namespace_alias"
    assert alias.source_id == document.source_id


def test_locator_absence_and_ambiguity_never_fall_back_by_similarity() -> None:
    documents = (
        _document("private-diary", "747"),
        _document("public-diary", "747"),
    )
    index = SourceLocatorIndex(documents)

    ambiguous = index.resolve_query("Diary:747")[0]
    absent = index.resolve_query("Diary:999")[0]

    assert ambiguous.status == "ambiguous"
    assert ambiguous.source_ids == tuple(sorted(item.source_id for item in documents))
    assert absent.status == "absent"
    assert absent.source_ids == ()


def test_locator_parser_ignores_urls_and_deduplicates_tokens() -> None:
    locators = parse_source_locators(
        "Diary:747 и diary:747; ссылка https://example.test/x и Rein:3"
    )

    assert tuple(item.raw for item in locators) == ("Diary:747", "Rein:3")
