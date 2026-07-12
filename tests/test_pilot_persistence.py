from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.pilot_persistence import load_pilot_state, save_pilot_state
from core.pilot_runtime import PilotRuntime


def _runtime() -> PilotRuntime:
    runtime = PilotRuntime()
    runtime.replace_source(
        source_id="daily.md",
        semantic_input={
            "свобода": {"weight": 0.9, "contains": {"выбор": 0.8}},
            "выбор": {"weight": 0.8, "contains": {}},
        },
        source_revision="a" * 64,
        observed_at=1.0,
        recorded_at=2.0,
    )
    return runtime


def test_pilot_state_round_trip(tmp_path: Path) -> None:
    path = tmp_path / ".fvsc" / "pilot-state.json"
    runtime = _runtime()
    feedback = [{"query_id": "q1", "rating": 4, "useful": True}]

    save_pilot_state(path, runtime, feedback=feedback)
    restored, restored_feedback = load_pilot_state(path)

    assert restored.status() == runtime.status()
    assert restored_feedback == feedback
    assert path.stat().st_size > 0


def test_missing_state_returns_empty_runtime(tmp_path: Path) -> None:
    runtime, feedback = load_pilot_state(tmp_path / "missing.json")

    assert runtime.ledger.event_count == 0
    assert runtime.snapshot.concept_count == 0
    assert feedback == []


def test_tampered_runtime_digest_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "pilot.json"
    save_pilot_state(path, _runtime())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["runtime"]["snapshot_id"] = "0" * 64
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="snapshot digest"):
        load_pilot_state(path)


def test_non_regular_state_file_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "real.json"
    save_pilot_state(target, _runtime())
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")

    with pytest.raises(ValueError, match="non-regular"):
        load_pilot_state(link)
