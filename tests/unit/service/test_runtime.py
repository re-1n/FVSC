from __future__ import annotations

import os

import pytest

from fvsc.evidence import FeedbackState
from fvsc.ingest import ParseConfig
from fvsc.ingest.judgment_events import JUDGMENT_EVENT_EXTRACTOR
from fvsc.ingest.vault_sync import VaultSyncConfig
from fvsc.service import StaleSourceStateError, VaultRuntime


def _write(path, text: str, *, mtime: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.utime(path, (mtime, mtime))


def _runtime(tmp_path) -> VaultRuntime:
    return VaultRuntime(
        tmp_path,
        sync_config=VaultSyncConfig(
            parser_config=ParseConfig(
                min_freq=1,
                min_token_len=2,
                max_concepts=None,
                window=4,
                weight_threshold=0.0,
            ),
            materializer_dim=16,
            enable_russian_judgments=True,
        ),
    )


def test_runtime_sync_search_and_reload_keep_lexical_as_ranker(tmp_path) -> None:
    _write(
        tmp_path / "diary" / "parasites.md",
        "---\nsource_kind: owner_reflection\n---\n"
        "Паразиты превращают внимание в чужой ресурс.",
        mtime=10.0,
    )
    _write(
        tmp_path / "diary" / "ocean.md",
        "---\nsource_kind: owner_reflection\n---\n"
        "Внутренний океан освещают маяки.",
        mtime=11.0,
    )
    runtime = _runtime(tmp_path)

    status = runtime.sync(sync_time=20.0)
    hits = runtime.search("роль паразитов во внимании", top_k=2)

    assert status.loaded is True
    assert status.source_count == 2
    assert status.exact_judgments > 0
    assert hits[0].source_id == "diary/parasites.md"
    assert "Паразиты" in hits[0].preview
    assert hits[0].score > 0.0
    assert runtime.source_document(hits[0].source_id).text.startswith("Паразиты")

    reloaded = _runtime(tmp_path)
    assert reloaded.load().snapshot_id == status.snapshot_id
    assert reloaded.search("паразиты", top_k=1)[0].source_id == hits[0].source_id


def test_runtime_refuses_to_pair_stale_cache_with_changed_source_text(tmp_path) -> None:
    note = tmp_path / "note.md"
    _write(note, "Свобода требует ответственности.", mtime=10.0)
    _runtime(tmp_path).sync(sync_time=20.0)
    _write(note, "Свобода допускает одиночество.", mtime=30.0)

    with pytest.raises(StaleSourceStateError, match="synchronize first"):
        _runtime(tmp_path).load()


def test_owner_feedback_is_atomically_persisted_without_replacing_target(tmp_path) -> None:
    _write(tmp_path / "note.md", "Свобода требует ответственности.", mtime=10.0)
    runtime = _runtime(tmp_path)
    runtime.sync(sync_time=20.0)
    target = next(
        event
        for event in runtime.ledger.active_events
        if event.extractor == JUDGMENT_EVENT_EXTRACTOR
    )

    feedback = runtime.record_feedback(
        target_event_id=target.event_id,
        action="reject",
        observed_at=30.0,
        recorded_at=30.0,
    )

    assert runtime.ledger.is_active(target.event_id)
    assert runtime.ledger.is_active(feedback.event_id)
    assert runtime.status().owner_feedback_events == 1
    reloaded = _runtime(tmp_path)
    reloaded.load()
    assert FeedbackState.from_ledger(reloaded.ledger).confirmation_status_for(
        target.event_id
    ) == "rejected"


def test_query_requires_loaded_state_and_unknown_source_fails_closed(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    with pytest.raises(RuntimeError, match="not loaded"):
        runtime.search("anything")
    _write(tmp_path / "note.md", "Текст заметки.", mtime=10.0)
    runtime.sync(sync_time=20.0)
    with pytest.raises(KeyError, match="unknown source"):
        runtime.source_document("missing.md")
