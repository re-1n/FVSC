"""Safe, versioned persistence for the FVSC daily pilot runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

from .materializer import EvidenceEncoder
from .pilot_runtime import PilotRuntime


PILOT_MAGIC = "fvsc-daily-pilot"
PILOT_VERSION = 1


def _fsync_directory(path: Path) -> None:
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def save_pilot_state(
    path: Path,
    runtime: PilotRuntime,
    *,
    feedback: Sequence[Mapping[str, Any]] = (),
) -> None:
    """Atomically persist ledger records and user feedback as UTF-8 JSON."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "magic": PILOT_MAGIC,
        "version": PILOT_VERSION,
        "runtime": runtime.status(),
        "events": runtime.to_records(),
        "feedback": [dict(record) for record in feedback],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ).encode("utf-8")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_pilot_state(
    path: Path,
    *,
    encoder: EvidenceEncoder | None = None,
) -> tuple[PilotRuntime, list[dict[str, Any]]]:
    """Load and validate one pilot state file; missing files yield an empty runtime."""
    target = Path(path)
    if not target.exists():
        return PilotRuntime(encoder=encoder), []
    if target.is_symlink() or not target.is_file():
        raise ValueError(f"refusing non-regular pilot state file: {target}")

    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid pilot state file: {target}") from exc
    if not isinstance(payload, dict):
        raise ValueError("pilot state payload must be an object")
    if payload.get("magic") != PILOT_MAGIC:
        raise ValueError("invalid pilot state magic")
    if payload.get("version") != PILOT_VERSION:
        raise ValueError(f"unsupported pilot state version: {payload.get('version')!r}")

    events = payload.get("events")
    feedback = payload.get("feedback", [])
    if not isinstance(events, list):
        raise ValueError("pilot state events must be a list")
    if not isinstance(feedback, list) or any(not isinstance(item, dict) for item in feedback):
        raise ValueError("pilot state feedback must be a list of objects")

    runtime = PilotRuntime.from_records(events, encoder=encoder)
    expected = payload.get("runtime", {})
    if isinstance(expected, dict):
        expected_snapshot = expected.get("snapshot_id")
        if expected_snapshot and expected_snapshot != runtime.snapshot.snapshot_id:
            raise ValueError("pilot state snapshot digest does not match its event ledger")
    return runtime, [dict(item) for item in feedback]
