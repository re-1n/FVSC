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


def _message(message_id, date, text):
    return {"id": message_id, "type": "message", "date": date, "text": text}


def test_export_is_monthly_portable_and_keeps_all_languages(tmp_path) -> None:
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
    assert result.message_count == 2
    assert result.skipped_message_count == 2
    assert [document.source_id.rsplit("/", 1)[-1] for document in result.documents] == [
        "2026-01.json",
        "2026-02.json",
    ]
    assert all(document.adapter == TELEGRAM_EXPORT_ADAPTER for document in result.documents)
    assert all(document.source_kind == "owner_reflection" for document in result.documents)
    assert "Русский and English text" in result.documents[0].text
    assert "code" not in result.documents[1].text
    assert "example.test" not in result.documents[1].text


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


def test_message_order_does_not_change_month_revision(tmp_path) -> None:
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

    assert first.documents[0].source_revision == second.documents[0].source_revision
    assert first.documents[0].text == second.documents[0].text


def test_changing_one_month_preserves_other_month_revision(tmp_path) -> None:
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
    january_id = "telegram/same/2026-01.json"
    february_id = "telegram/same/2026-02.json"
    assert first_revisions[january_id] == second_revisions[january_id]
    assert first_revisions[february_id] != second_revisions[february_id]


def test_invalid_message_date_is_explicitly_undated(tmp_path) -> None:
    path = tmp_path / "result.json"
    _write_export(path, [_message(1, "not-a-date", "alpha beta gamma")])

    result = load_telegram_export(path, source_namespace="same")

    assert result.documents[0].source_id == "telegram/same/undated.json"


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
