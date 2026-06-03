"""SpaceStore: CRUD lifecycle and persistence for named SemanticSpace bundles."""

from __future__ import annotations

import os
import pickle
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from core.density_core import SemanticSpace


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
        self.data_dir = data_dir
        self.autosave_threshold = autosave_threshold
        self._bundles: Dict[str, SpaceBundle] = {}

    # ── lifecycle ──────────────────────────────────────────────────

    def list_spaces(self) -> list[dict]:
        spaces = []
        seen = set(self._bundles.keys())

        # Loaded bundles
        for name, b in self._bundles.items():
            spaces.append({
                "name": name,
                "dim": b.space.dim,
                "concept_count": len(b.space.concepts),
                "chunk_count": len(b.chunks),
                "ingest_count": b.meta.get("ingest_count", 0),
                "ingests_since_save": b.meta.get("ingests_since_save", 0),
                "last_modified": b.meta.get("last_modified"),
            })

        # Un-loaded (only on disk) bundles
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for p in sorted(self.data_dir.glob("*.pkl")):
            name = p.stem
            if name not in seen:
                spaces.append({
                    "name": name,
                    "dim": None,
                    "concept_count": None,
                    "chunk_count": None,
                    "ingest_count": None,
                    "ingests_since_save": None,
                    "last_modified": p.stat().st_mtime,
                    "_on_disk": True,
                })
        return spaces

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
        bundle = SpaceBundle(
            name=name,
            space=SemanticSpace(dim=dim),
            meta={"created_at": time.time(), "last_modified": None,
                  "dim": dim, "ingest_count": 0, "ingests_since_save": 0},
        )
        self._bundles[name] = bundle
        return bundle

    def delete(self, name: str) -> bool:
        self._bundles.pop(name, None)
        pkl = self._pkl_path(name)
        if pkl.exists():
            pkl.unlink()
            return True
        return False

    # ── persistence ────────────────────────────────────────────────

    def save(self, name: str):
        bundle = self._bundles.get(name)
        if bundle is None:
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._pkl_path(name).with_suffix(".pkl.tmp")
        bundle.meta["last_modified"] = time.time()
        bundle.meta["ingests_since_save"] = 0
        with open(tmp, "wb") as f:
            pickle.dump(bundle, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(self._pkl_path(name))

    def save_all(self):
        for name in self._bundles:
            self.save(name)

    def mark_dirty(self, name: str):
        b = self._bundles.get(name)
        if b is None:
            return
        b.meta["ingests_since_save"] = b.meta.get("ingests_since_save", 0) + 1
        b.meta["ingest_count"] = b.meta.get("ingest_count", 0) + 1
        b.meta["last_modified"] = time.time()
        if b.meta["ingests_since_save"] >= self.autosave_threshold:
            self.save(name)

    # ── internals ──────────────────────────────────────────────────

    def _pkl_path(self, name: str) -> Path:
        safe = "".join(c for c in name if c.isalnum() or c in "-_")
        return self.data_dir / f"{safe}.pkl"

    def _try_load(self, name: str) -> Optional[SpaceBundle]:
        pkl = self._pkl_path(name)
        if not pkl.exists():
            return None
        with open(pkl, "rb") as f:
            bundle = pickle.load(f)
        self._bundles[name] = bundle
        return bundle
