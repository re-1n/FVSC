"""SpaceStore: CRUD lifecycle and persistence for named SemanticSpace bundles.

The on-disk format is versioned and written atomically.  It still uses pickle,
so files in ``data_dir`` must be treated as trusted local application state.
"""

from __future__ import annotations

import base64
import os
import pickle
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from core.density_core import SemanticSpace

STORE_MAGIC = "fvsc-space-bundle"
STORE_VERSION = 1


@dataclass
class Chunk:
    chunk_id: str   # "{source_id}:{idx}"
    source_id: str
    idx: int
    text: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class SpaceBundle:
    name: str
    space: SemanticSpace
    chunks: Dict[str, Chunk] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    def _default_meta(self):
        return {
            "created_at": time.time(),
            "last_modified": None,
            "dim": self.space.dim,
            "ingest_count": 0,
            "ingests_since_save": 0,
        }

    def __post_init__(self):
        if not self.meta:
            self.meta = self._default_meta()


class SpaceStore:
    """In-memory registry of SpaceBundle instances with lazy-load and auto-save.

    Thread-safe for asyncio use (single event-loop, no threading).
    """

    def __init__(self, data_dir: Path, autosave_threshold: int = 10):
        if autosave_threshold < 1:
            raise ValueError("autosave_threshold must be positive")
        self.data_dir = data_dir
        self.autosave_threshold = autosave_threshold
        self._bundles: Dict[str, SpaceBundle] = {}

    # ── lifecycle ──────────────────────────────────────────────────

    def list_spaces(self) -> list[dict]:
        spaces = []
        seen = set(self._bundles.keys())

        for name, bundle in self._bundles.items():
            spaces.append(self._space_meta(name, bundle))

        self.data_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(self.data_dir.glob("*.pkl")):
            name = self._name_from_path(path)
            if name is None or name in seen:
                continue
            seen.add(name)
            spaces.append({
                "name": name,
                "dim": None,
                "concept_count": None,
                "chunk_count": None,
                "ingest_count": None,
                "ingests_since_save": None,
                "last_modified": path.stat().st_mtime,
                "_on_disk": True,
            })
        return spaces

    @staticmethod
    def _space_meta(name: str, bundle: SpaceBundle) -> dict:
        return {
            "name": name,
            "dim": bundle.space.dim,
            "concept_count": len(bundle.space.concepts),
            "chunk_count": len(bundle.chunks),
            "ingest_count": bundle.meta.get("ingest_count", 0),
            "ingests_since_save": bundle.meta.get("ingests_since_save", 0),
            "last_modified": bundle.meta.get("last_modified"),
        }

    def get(self, name: str) -> Optional[SpaceBundle]:
        if name in self._bundles:
            return self._bundles[name]
        return self._try_load(name)

    def get_or_create(self, name: str, dim: int = 64) -> SpaceBundle:
        if name in self._bundles:
            return self._bundles[name]
        bundle = self._try_load(name)
        if bundle is not None:
            return bundle
        bundle = SpaceBundle(name=name, space=SemanticSpace(dim=dim))
        self._bundles[name] = bundle
        return bundle

    def delete(self, name: str) -> bool:
        existed = self._bundles.pop(name, None) is not None
        for path in self._candidate_paths(name):
            if path.exists() or path.is_symlink():
                path.unlink()
                existed = True
        return existed

    # ── persistence ────────────────────────────────────────────────

    def save(self, name: str) -> None:
        bundle = self._bundles.get(name)
        if bundle is None:
            return
        self._validate_bundle(bundle, expected_name=name)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        target = self._pkl_path(name)
        tmp = self.data_dir / f".{target.name}.{uuid.uuid4().hex}.tmp"
        bundle.meta["last_modified"] = time.time()
        bundle.meta["ingests_since_save"] = 0
        payload = {
            "magic": STORE_MAGIC,
            "version": STORE_VERSION,
            "bundle": bundle,
        }

        try:
            with open(tmp, "xb") as handle:
                pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, target)
            self._fsync_directory()
        finally:
            if tmp.exists():
                tmp.unlink()

        legacy = self._legacy_pkl_path(name)
        if legacy != target and legacy.exists():
            legacy.unlink()

    def save_all(self) -> None:
        for name in list(self._bundles):
            self.save(name)

    def mark_dirty(self, name: str) -> None:
        bundle = self._bundles.get(name)
        if bundle is None:
            return
        bundle.meta["ingests_since_save"] = bundle.meta.get("ingests_since_save", 0) + 1
        bundle.meta["ingest_count"] = bundle.meta.get("ingest_count", 0) + 1
        bundle.meta["last_modified"] = time.time()
        if bundle.meta["ingests_since_save"] >= self.autosave_threshold:
            self.save(name)

    # ── internals ──────────────────────────────────────────────────

    @staticmethod
    def _encode_name(name: str) -> str:
        raw = base64.urlsafe_b64encode(name.encode("utf-8")).decode("ascii")
        return raw.rstrip("=")

    @staticmethod
    def _decode_name(token: str) -> Optional[str]:
        try:
            padded = token + "=" * (-len(token) % 4)
            return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None

    def _pkl_path(self, name: str) -> Path:
        return self.data_dir / f"space-{self._encode_name(name)}.pkl"

    def _legacy_pkl_path(self, name: str) -> Path:
        safe = "".join(c for c in name if c.isalnum() or c in "-_")
        return self.data_dir / f"{safe}.pkl"

    def _candidate_paths(self, name: str) -> tuple[Path, ...]:
        current = self._pkl_path(name)
        legacy = self._legacy_pkl_path(name)
        return (current,) if current == legacy else (current, legacy)

    def _name_from_path(self, path: Path) -> Optional[str]:
        if path.stem.startswith("space-"):
            return self._decode_name(path.stem.removeprefix("space-"))
        return path.stem or None

    def _try_load(self, name: str) -> Optional[SpaceBundle]:
        path = next((p for p in self._candidate_paths(name) if p.exists()), None)
        if path is None:
            return None
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Refusing non-regular space file: {path}")

        with open(path, "rb") as handle:
            loaded = pickle.load(handle)

        if isinstance(loaded, SpaceBundle):
            bundle = loaded  # legacy v0 payload
        elif isinstance(loaded, dict):
            if loaded.get("magic") != STORE_MAGIC:
                raise ValueError(f"Invalid space file magic: {path}")
            if loaded.get("version") != STORE_VERSION:
                raise ValueError(
                    f"Unsupported space file version {loaded.get('version')!r}: {path}"
                )
            bundle = loaded.get("bundle")
        else:
            raise ValueError(f"Invalid space file payload: {path}")

        self._validate_bundle(bundle, expected_name=name)
        self._bundles[name] = bundle
        return bundle

    @staticmethod
    def _validate_bundle(bundle: object, expected_name: str) -> None:
        if not isinstance(bundle, SpaceBundle):
            raise ValueError("Persisted payload is not a SpaceBundle")
        if bundle.name != expected_name:
            raise ValueError(
                f"Persisted space name mismatch: expected {expected_name!r}, got {bundle.name!r}"
            )
        if not isinstance(bundle.space, SemanticSpace):
            raise ValueError("Persisted bundle does not contain a SemanticSpace")
        if bundle.space.dim < 1:
            raise ValueError("Persisted SemanticSpace has invalid dimension")
        if not isinstance(bundle.chunks, dict) or not isinstance(bundle.meta, dict):
            raise ValueError("Persisted SpaceBundle has invalid metadata")

    def _fsync_directory(self) -> None:
        if not hasattr(os, "O_DIRECTORY"):
            return
        try:
            fd = os.open(self.data_dir, os.O_RDONLY | os.O_DIRECTORY)
        except OSError:
            return
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
