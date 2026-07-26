from __future__ import annotations

import hashlib
import json

import pytest

from fvsc.evidence import EvidenceLedger
from fvsc.ingest import OBSIDIAN_VAULT_ADAPTER, ParseConfig, SourceDocument
from fvsc.ingest.document_ingest import (
    build_evidence_batch,
    materialize_evidence_ledger,
    reconcile_evidence_batch,
)
from fvsc.runtime.vault_cache import (
    CACHE_MAGIC,
    CACHE_VERSION,
    VaultCache,
    load_vault_cache,
    save_vault_cache,
)


RAW_NOTE = "Private owner sentence with alpha beta gamma."


def _cache(tmp_path) -> VaultCache:
    document = SourceDocument.create(
        source_id="notes/value.md",
        source_revision=hashlib.sha256(RAW_NOTE.encode("utf-8")).hexdigest(),
        observed_at=10.0,
        text=RAW_NOTE,
        adapter=OBSIDIAN_VAULT_ADAPTER,
        source_kind="owner_reflection",
        raw_chars=len(RAW_NOTE),
    )
    config = ParseConfig(
        min_freq=1,
        min_token_len=2,
        max_concepts=None,
        weight_threshold=0.0,
    )
    batch = build_evidence_batch([document], config=config)
    ledger = EvidenceLedger()
    reconcile_evidence_batch(ledger, batch, sync_time=20.0)
    snapshot = materialize_evidence_ledger(ledger, dim=16)
    return VaultCache(
        adapter=batch.adapter,
        ledger=ledger,
        snapshot=snapshot,
        materializer_dim=16,
        source_revisions=batch.source_revisions,
        source_observed_at=batch.source_observed_at,
        source_kinds=batch.source_kinds,
        semantic_input=batch.semantic_input,
        silent_pool=batch.silent_pool,
        file_count=batch.source_count,
        raw_chars=batch.raw_chars,
        cleaned_chars=batch.cleaned_chars,
    )


def test_cache_round_trip_replays_ledger_and_snapshot(tmp_path) -> None:
    path = tmp_path / ".fvsc" / "cache.json"
    original = _cache(tmp_path)

    save_vault_cache(path, original)
    loaded = load_vault_cache(path)

    assert loaded.ledger.to_records() == original.ledger.to_records()
    assert loaded.ledger.digest == original.ledger.digest
    assert loaded.snapshot.snapshot_id == original.snapshot.snapshot_id
    assert loaded.snapshot.state_digest == original.snapshot.state_digest
    assert loaded.source_revisions == original.source_revisions
    envelope = json.loads(path.read_text(encoding="utf-8"))
    assert envelope["magic"] == CACHE_MAGIC
    assert envelope["version"] == CACHE_VERSION


def test_cache_does_not_persist_raw_body_or_absolute_vault_path(tmp_path) -> None:
    path = tmp_path / ".fvsc" / "cache.json"

    save_vault_cache(path, _cache(tmp_path))
    payload = path.read_text(encoding="utf-8")

    assert RAW_NOTE not in payload
    assert str(tmp_path) not in payload
    assert "notes/value.md" in payload


def test_atomic_replacement_leaves_no_temporary_files(tmp_path) -> None:
    path = tmp_path / "cache.json"
    cache = _cache(tmp_path)

    save_vault_cache(path, cache)
    save_vault_cache(path, cache)

    assert load_vault_cache(path).ledger.digest == cache.ledger.digest
    assert list(tmp_path.glob(".cache.json.*.tmp")) == []


def test_invalid_magic_version_and_ledger_digest_are_rejected(tmp_path) -> None:
    path = tmp_path / "cache.json"
    save_vault_cache(path, _cache(tmp_path))
    payload = json.loads(path.read_text(encoding="utf-8"))

    payload["magic"] = "other"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="magic"):
        load_vault_cache(path)

    save_vault_cache(path, _cache(tmp_path))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = 999
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        load_vault_cache(path)

    save_vault_cache(path, _cache(tmp_path))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["data"]["ledger"]["digest"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="ledger digest mismatch"):
        load_vault_cache(path)


def test_materializer_metadata_tampering_is_rejected(tmp_path) -> None:
    path = tmp_path / "cache.json"
    save_vault_cache(path, _cache(tmp_path))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["data"]["materializer"]["snapshot_id"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="materializer metadata mismatch"):
        load_vault_cache(path)


def test_symlink_cache_is_rejected_for_load_and_save(tmp_path) -> None:
    target = tmp_path / "target.json"
    save_vault_cache(target, _cache(tmp_path))
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks are unavailable on this platform")

    with pytest.raises(ValueError, match="non-regular"):
        load_vault_cache(link)
    with pytest.raises(ValueError, match="non-regular"):
        save_vault_cache(link, _cache(tmp_path))


def test_cache_rejects_absolute_source_ids_before_writing(tmp_path) -> None:
    original = _cache(tmp_path)
    with pytest.raises(ValueError, match="POSIX-relative"):
        VaultCache(
            adapter=original.adapter,
            ledger=original.ledger,
            snapshot=original.snapshot,
            materializer_dim=original.materializer_dim,
            source_revisions={str(tmp_path / "note.md"): "0" * 64},
            source_observed_at={str(tmp_path / "note.md"): 1.0},
            source_kinds={str(tmp_path / "note.md"): "unknown"},
            semantic_input={},
            silent_pool={},
            file_count=1,
            raw_chars=0,
            cleaned_chars=0,
        )
