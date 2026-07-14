from __future__ import annotations

import os

import pytest

from fvsc.ingest import ParseConfig
from fvsc.ingest.vault_sync import VaultSyncConfig, sync_vault
from fvsc.ingest.judgment_events import JUDGMENT_EVENT_EXTRACTOR
from fvsc.runtime.vault_cache import load_vault_cache


def _write(path, text: str, *, mtime: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.utime(path, (mtime, mtime))


def _config() -> VaultSyncConfig:
    return VaultSyncConfig(
        parser_config=ParseConfig(
            min_freq=1,
            min_token_len=2,
            max_concepts=None,
            window=4,
            weight_threshold=0.0,
        ),
        materializer_dim=16,
    )


def test_full_vault_lifecycle_create_replay_modify_delete_reload(tmp_path) -> None:
    note = tmp_path / "notes" / "value.md"
    _write(
        note,
        "---\nfvsc_source_kind: owner_reflection\n---\nAlpha beta gamma.",
        mtime=10.0,
    )

    created = sync_vault(tmp_path, config=_config(), sync_time=20.0)
    assert not created.loaded_existing_cache
    assert created.cache_path == tmp_path / ".fvsc" / "cache.json"
    assert created.cache_path.is_file()
    assert created.lifecycle.asserted_count > 0
    assert created.lifecycle.retracted_count == 0
    assert created.snapshot.concept_count > 0
    first_digest = created.ledger.digest
    first_snapshot_id = created.snapshot.snapshot_id
    first_event_count = created.ledger.event_count

    replayed = sync_vault(tmp_path, config=_config(), sync_time=30.0)
    assert replayed.loaded_existing_cache
    assert replayed.lifecycle.asserted_count == 0
    assert replayed.lifecycle.retracted_count == 0
    assert replayed.ledger.digest == first_digest
    assert replayed.snapshot.snapshot_id == first_snapshot_id

    _write(
        note,
        "---\nfvsc_source_kind: owner_reflection\n---\nAlpha beta theta.",
        mtime=40.0,
    )
    modified = sync_vault(tmp_path, config=_config(), sync_time=50.0)
    assert modified.lifecycle.asserted_count > 0
    assert modified.lifecycle.retracted_count > 0
    assert "notes/value.md" in modified.lifecycle.changed_sources
    assert modified.ledger.event_count > first_event_count
    assert modified.ledger.digest != first_digest

    note.unlink()
    deleted = sync_vault(tmp_path, config=_config(), sync_time=60.0)
    assert deleted.lifecycle.deleted_sources == ("notes/value.md",)
    assert deleted.lifecycle.retracted_count > 0
    assert deleted.ledger.active_count == 0
    assert deleted.snapshot.concept_count == 0
    assert deleted.cache.file_count == 0

    reloaded = load_vault_cache(deleted.cache_path)
    assert reloaded.ledger.digest == deleted.ledger.digest
    assert reloaded.snapshot.snapshot_id == deleted.snapshot.snapshot_id


def test_empty_note_retracts_semantics_but_remains_a_current_source(tmp_path) -> None:
    note = tmp_path / "note.md"
    _write(note, "Alpha beta gamma.", mtime=10.0)
    sync_vault(tmp_path, config=_config(), sync_time=20.0)

    _write(note, "---\nsource_kind: external_fact\n---\n", mtime=30.0)
    result = sync_vault(tmp_path, config=_config(), sync_time=40.0)

    assert result.lifecycle.deleted_sources == ()
    assert result.lifecycle.changed_sources == ("note.md",)
    assert result.ledger.active_count == 0
    assert result.cache.file_count == 1
    assert result.cache.source_kinds["note.md"] == "external_fact"


def test_invalid_existing_cache_is_not_silently_replaced(tmp_path) -> None:
    _write(tmp_path / "note.md", "Alpha beta gamma.", mtime=10.0)
    cache_path = tmp_path / ".fvsc" / "cache.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="valid UTF-8 JSON"):
        sync_vault(tmp_path, config=_config(), sync_time=20.0)

    assert cache_path.read_text(encoding="utf-8") == "not-json"


def test_additional_exclusions_extend_scanner_defaults(tmp_path) -> None:
    _write(tmp_path / "keep" / "note.md", "Alpha beta gamma.", mtime=10.0)
    _write(tmp_path / "private" / "note.md", "Delta epsilon zeta.", mtime=10.0)
    config = VaultSyncConfig(
        parser_config=_config().parser_config,
        materializer_dim=16,
        exclude_dirs=frozenset({"private"}),
    )

    result = sync_vault(tmp_path, config=config, sync_time=20.0)

    assert set(result.cache.source_revisions) == {"keep/note.md"}


def test_exact_judgments_are_opt_in_and_persist_in_the_same_ledger(tmp_path) -> None:
    _write(
        tmp_path / "thought.md",
        "Свобода требует ответственности.",
        mtime=10.0,
    )
    base = _config()
    config = VaultSyncConfig(
        parser_config=base.parser_config,
        materializer_dim=base.materializer_dim,
        enable_russian_judgments=True,
    )

    result = sync_vault(tmp_path, config=config, sync_time=20.0)
    exact = tuple(
        event
        for event in result.ledger.active_events
        if event.extractor == JUDGMENT_EVENT_EXTRACTOR
    )

    assert exact
    assert exact[0].source_id == "thought.md"
    assert exact[0].context["source_span"]["text_sha256"]
    restored = load_vault_cache(result.cache_path)
    assert restored.ledger.digest == result.ledger.digest
    assert any(
        event.extractor == JUDGMENT_EVENT_EXTRACTOR
        for event in restored.ledger.active_events
    )
