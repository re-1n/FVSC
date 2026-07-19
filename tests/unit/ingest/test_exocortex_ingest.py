from __future__ import annotations

import json

import pytest

from fvsc.ingest import TELEGRAM_EXPORT_ADAPTER, ParseConfig, load_telegram_export
from fvsc.ingest.document_ingest import build_evidence_batch


def _write_export(path, messages, *, name="Private channel name") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"name": name, "messages": messages}, ensure_ascii=False),
        encoding="utf-8",
    )


def _message(message_id, date, text, **extra):
    return {"id": message_id, "type": "message", "date": date, "text": text, **extra}


def test_export_is_message_level_portable_and_keeps_all_languages_and_locators(tmp_path) -> None:
    path = tmp_path / "private-name" / "result.json"
    _write_export(
        path,
        [
            _message(
                1,
                "2026-01-02T10:00:00+00:00",
                ["Русский and English ", {"type": "link", "text": "text"}],
            ),
            _message(2, "2026-02-03T10:00:00+00:00", "Value `code` https://example.test"),
            {"id": 3, "type": "service", "text": "joined"},
            _message(4, "2026-02-04T10:00:00+00:00", "https://example.test"),
        ],
    )

    result = load_telegram_export(path, source_kind="owner_reflection")

    assert result.namespace.startswith("export-")
    assert "private-name" not in result.namespace
    assert result.message_count == 3
    assert result.text_message_count == 2
    assert result.deferred_message_count == 1
    assert result.skipped_message_count == 1
    assert [document.source_id.rsplit("/", 1)[-1] for document in result.documents] == [
        "message-1.json",
        "message-2.json",
        "message-4.json",
    ]
    assert all(document.adapter == TELEGRAM_EXPORT_ADAPTER for document in result.documents)
    assert all(document.source_kind == "owner_reflection" for document in result.documents)
    assert "Русский and English text" in result.documents[0].text
    assert "code" not in result.documents[1].text
    assert "example.test" not in result.documents[1].text
    assert result.documents[2].text == ""
    assert result.documents[2].metadata["ingest_status"] == "locator_only"
    assert result.documents[2].metadata["locators"] == ["https://example.test"]


@pytest.mark.parametrize("kind", ["dream_report", "external_fact", "unknown"])
def test_source_kind_is_explicit_and_reaches_evidence_context(tmp_path, kind) -> None:
    path = tmp_path / "result.json"
    _write_export(path, [_message(1, "2026-01-01T00:00:00Z", "alpha beta gamma")])

    result = load_telegram_export(path, source_kind=kind, source_namespace="portable")
    batch = build_evidence_batch(
        result.documents,
        config=ParseConfig(min_freq=1, min_token_len=2, max_concepts=None),
    )

    assert result.documents[0].source_kind == kind
    assert batch.events
    assert {event.context["source_kind"] for event in batch.events} == {kind}
    assert {event.provenance["source_adapter"] for event in batch.events} == {
        TELEGRAM_EXPORT_ADAPTER
    }


def test_message_order_does_not_change_message_revisions(tmp_path) -> None:
    first_path = tmp_path / "a" / "result.json"
    second_path = tmp_path / "b" / "result.json"
    messages = [
        _message(2, "2026-01-02T00:00:00Z", "delta epsilon"),
        _message(1, "2026-01-01T00:00:00Z", "alpha beta"),
    ]
    _write_export(first_path, messages)
    _write_export(second_path, list(reversed(messages)))

    first = load_telegram_export(first_path, source_namespace="same")
    second = load_telegram_export(second_path, source_namespace="same")

    assert {
        document.source_id: (document.source_revision, document.text)
        for document in first.documents
    } == {
        document.source_id: (document.source_revision, document.text)
        for document in second.documents
    }


def test_changing_one_message_preserves_other_message_revision(tmp_path) -> None:
    path = tmp_path / "result.json"
    january = _message(1, "2026-01-01T00:00:00Z", "alpha beta")
    february = _message(2, "2026-02-01T00:00:00Z", "gamma delta")
    _write_export(path, [january, february])
    first = load_telegram_export(path, source_namespace="same")

    february_changed = _message(2, "2026-02-01T00:00:00Z", "gamma theta")
    _write_export(path, [january, february_changed])
    second = load_telegram_export(path, source_namespace="same")

    first_revisions = {document.source_id: document.source_revision for document in first.documents}
    second_revisions = {document.source_id: document.source_revision for document in second.documents}
    january_id = "telegram/same/messages/message-1.json"
    february_id = "telegram/same/messages/message-2.json"
    assert first_revisions[january_id] == second_revisions[january_id]
    assert first_revisions[february_id] != second_revisions[february_id]


def test_invalid_message_date_is_explicitly_undated(tmp_path) -> None:
    path = tmp_path / "result.json"
    _write_export(path, [_message(1, "not-a-date", "alpha beta gamma")])

    result = load_telegram_export(path, source_namespace="same")

    assert result.documents[0].source_id == "telegram/same/messages/message-1.json"
    assert result.documents[0].metadata["date_status"] == "undated"
    assert result.documents[0].metadata["period"] == "undated"
    assert result.documents[0].metadata["display_time"] is None


def test_configured_owner_is_per_message_and_forwarding_does_not_override_it(tmp_path) -> None:
    path = tmp_path / "result.json"
    _write_export(
        path,
        [
            _message(
                1,
                "2026-01-01T00:00:00Z",
                "owner forwarded text",
                from_id="channel-owner-private-id",
                forwarded_from="External Private Name",
                forwarded_from_id="channel-external-private-id",
                **{"from": "Owner Name"},
            ),
            _message(
                2,
                "2026-01-01T00:01:00Z",
                "participant comment",
                from_id="user-participant-private-id",
                reply_to_message_id=1,
                **{"from": "Participant Name"},
            ),
        ],
    )

    result = load_telegram_export(
        path,
        owner_author_ids={"channel-owner-private-id"},
        source_namespace="same",
    )

    owner, participant = result.documents
    assert owner.source_kind == "owner_reflection"
    assert owner.metadata["owner_authored"] is True
    assert owner.metadata["owner_adopted_expression"] is True
    assert owner.metadata["forwarded"] is True
    assert owner.metadata["forward_source_key"].startswith("actor-")
    assert owner.metadata["source_attribution"] == {
        "expression_spans": [],
        "forward_origin_role": "non_owner",
        "forwarded": True,
        "owner_adopted_expression": True,
        "schema_version": 1,
        "text_origin_status": "unresolved",
        "transport_author_role": "owner",
    }
    assert participant.source_kind == "unknown"
    assert participant.metadata["owner_authored"] is False
    assert participant.metadata["reply_to_source_id"] == owner.source_id
    combined_metadata = owner.metadata_json + participant.metadata_json
    assert "private-id" not in combined_metadata
    assert "Owner Name" not in combined_metadata
    assert "Participant Name" not in combined_metadata
    assert "External Private Name" not in combined_metadata


def test_explicit_blockquote_becomes_a_verified_expression_span(tmp_path) -> None:
    path = tmp_path / "result.json"
    plain_before = "Мой комментарий\n"
    quotation = "Чужая строка https://example.test\nвторая строка"
    plain_after = "\nМой вывод"
    text_entities = [
        {"type": "plain", "text": plain_before},
        {"type": "blockquote", "text": quotation},
        {"type": "plain", "text": plain_after},
    ]
    _write_export(
        path,
        [
            _message(
                1,
                "2026-01-01T00:00:00Z",
                text_entities,
                text_entities=text_entities,
                from_id="owner",
            )
        ],
    )

    result = load_telegram_export(
        path,
        owner_author_ids={"owner"},
        source_namespace="same",
    )
    document = result.documents[0]
    attribution = document.metadata["source_attribution"]

    assert attribution["transport_author_role"] == "owner"
    assert attribution["text_origin_status"] == "unresolved"
    assert len(attribution["expression_spans"]) == 1
    span = attribution["expression_spans"][0]
    excerpt = document.text[span["start"] : span["end"]]
    assert excerpt == "Чужая строка\nвторая строка"
    assert span["kind"] == "quotation"
    assert span["owner_relation"] == "adopted"
    assert quotation not in document.metadata_json


def test_mismatched_text_entities_fail_closed(tmp_path) -> None:
    path = tmp_path / "result.json"
    _write_export(
        path,
        [
            _message(
                1,
                "2026-01-01T00:00:00Z",
                "actual",
                text_entities=[{"type": "plain", "text": "different"}],
            )
        ],
    )

    with pytest.raises(ValueError, match="do not match"):
        load_telegram_export(path)


def test_reply_temporal_context_and_moscow_calendar_are_preserved(tmp_path) -> None:
    path = tmp_path / "result.json"
    _write_export(
        path,
        [
            _message(
                10,
                "2026-05-01T02:04:25",
                "framing",
                date_unixtime="1777590265",
                from_id="owner",
            ),
            _message(
                11,
                "2026-05-01T02:05:25",
                "elaboration",
                date_unixtime="1777590325",
                from_id="owner",
                reply_to_message_id=10,
            ),
            _message(
                12,
                "2026-05-01T03:05:26",
                "later",
                date_unixtime="1777593926",
                from_id="owner",
            ),
        ],
    )

    result = load_telegram_export(
        path,
        owner_author_ids={"owner"},
        source_namespace="same",
        display_timezone="Europe/Moscow",
        temporal_context_seconds=60 * 60,
    )
    first, second, third = result.documents

    assert first.metadata["display_time"] == "2026-05-01T02:04:25+03:00"
    assert first.metadata["period"] == "2026-05"
    assert second.metadata["reply_to_source_id"] == first.source_id
    assert second.metadata["temporal_context"] == {
        "gap_seconds": 60.0,
        "heuristic": True,
        "previous_source_id": first.source_id,
        "threshold_seconds": 3600,
    }
    assert third.metadata["temporal_context"] is None


def test_duplicate_message_ids_and_invalid_configuration_fail_closed(tmp_path) -> None:
    path = tmp_path / "result.json"
    _write_export(
        path,
        [
            _message(1, "2026-01-01T00:00:00Z", "alpha"),
            _message(1, "2026-01-02T00:00:00Z", "beta"),
        ],
    )
    with pytest.raises(ValueError, match="duplicate message id"):
        load_telegram_export(path)

    _write_export(path, [_message(1, "2026-01-01T00:00:00Z", "alpha")])
    with pytest.raises(ValueError, match="unknown display timezone"):
        load_telegram_export(path, display_timezone="Mars/Olympus")
    with pytest.raises(ValueError, match="temporal_context_seconds"):
        load_telegram_export(path, temporal_context_seconds=-1)
    with pytest.raises(TypeError, match="owner_author_ids"):
        load_telegram_export(path, owner_author_ids="owner")


def test_invalid_schema_kind_and_symlink_are_rejected(tmp_path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="messages array"):
        load_telegram_export(path)

    _write_export(path, [])
    with pytest.raises(ValueError, match="unknown source kind"):
        load_telegram_export(path, source_kind="owner_fact")  # type: ignore[arg-type]

    link = tmp_path / "link.json"
    try:
        link.symlink_to(path)
    except OSError:
        pytest.skip("symlinks are unavailable on this platform")
    with pytest.raises(ValueError, match="non-regular"):
        load_telegram_export(link)
