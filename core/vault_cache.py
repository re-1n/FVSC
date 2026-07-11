"""Versioned persistence helpers for the vault-level FVSC cache.

The current payload still uses pickle for compatibility with existing
``SemanticSpace`` objects. Consequently, cache files must be treated as trusted
local application state and must never be loaded from an untrusted source.
"""

from __future__ import annotations

import os
import pickle
import uuid
from pathlib import Path
from typing import Any

from .density_core import SemanticSpace

CACHE_MAGIC = "fvsc-vault-cache"
CACHE_VERSION = 1


def validate_cache_blob(blob: object) -> dict[str, Any]:
    """Validate and normalize a decoded cache payload.

    Legacy unversioned dictionaries are accepted and normalized in memory so
    existing users can upgrade without rebuilding immediately.
    """
    if not isinstance(blob, dict):
        raise ValueError("Vault cache payload must be a dictionary")

    if blob.get("magic") == CACHE_MAGIC:
        version = blob.get("version")
        if version != CACHE_VERSION:
            raise ValueError(f"Unsupported vault cache version: {version!r}")
        data = blob.get("data")
        if not isinstance(data, dict):
            raise ValueError("Versioned vault cache is missing its data object")
    elif "space" in blob and "si" in blob:
        data = blob  # legacy v0 payload
    else:
        raise ValueError("Invalid vault cache magic or schema")

    space = data.get("space")
    semantic_input = data.get("si")
    if not isinstance(space, SemanticSpace):
        raise ValueError("Vault cache does not contain a SemanticSpace")
    if not isinstance(semantic_input, dict):
        raise ValueError("Vault cache semantic_input must be a dictionary")
    if space.dim < 1:
        raise ValueError("Vault cache SemanticSpace has invalid dimension")

    normalized = dict(data)
    normalized.setdefault("n_files", None)
    normalized.setdefault("corpus_chars", None)
    return normalized


def load_vault_cache(path: Path) -> dict[str, Any]:
    """Load and validate a trusted local vault cache file."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Refusing non-regular vault cache file: {path}")
    with path.open("rb") as handle:
        decoded = pickle.load(handle)
    return validate_cache_blob(decoded)


def save_vault_cache(path: Path, data: dict[str, Any]) -> None:
    """Validate and atomically persist a vault cache payload."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = validate_cache_blob(data)
    payload = {
        "magic": CACHE_MAGIC,
        "version": CACHE_VERSION,
        "data": normalized,
    }
    tmp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"

    try:
        with tmp.open("xb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
        _fsync_directory(path.parent)
    finally:
        if tmp.exists():
            tmp.unlink()


def _fsync_directory(directory: Path) -> None:
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
