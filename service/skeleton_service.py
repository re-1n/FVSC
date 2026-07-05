# -*- coding: utf-8 -*-
"""Service-level singleton for the skeleton layer (first cascade layer).

core/skeleton.py provides SkeletonIndex + seed_skeleton but is pure core —
this module owns the process-wide index instance and the config surface:

- FVSC_SKELETON=0            disables seeding entirely (default: enabled)
- FVSC_CONCEPTNET_PATH=...   overrides the ConceptNet RU JSON location
                             (default: <project>/data/conceptnet_ru.json)

The index is lazy: nothing is loaded until the first ingest actually needs
it (~1.4s one-time cost, then ~0.01s per seeding call). A missing JSON file
yields an empty index — seeding becomes a silent no-op, never an error.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Iterable, Optional

from core.density_core import SemanticSpace
from core.skeleton import SkeletonIndex, seed_skeleton

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_index: Optional[SkeletonIndex] = None
_lock = threading.Lock()


def skeleton_enabled() -> bool:
    return os.environ.get("FVSC_SKELETON", "1").strip().lower() not in ("0", "false", "off")


def conceptnet_path() -> Path:
    override = os.environ.get("FVSC_CONCEPTNET_PATH")
    if override:
        return Path(override)
    return _PROJECT_ROOT / "data" / "conceptnet_ru.json"


def get_index() -> SkeletonIndex:
    """Lazy process-wide SkeletonIndex. Thread-safe: build_from_vault seeds
    from a worker thread while live file_ingest runs on the event loop.
    """
    global _index
    if _index is not None:
        return _index
    with _lock:
        if _index is None:
            _index = SkeletonIndex.from_conceptnet(str(conceptnet_path()))
        return _index


def reset_index() -> None:
    """Drop the cached index (tests / conceptnet path change)."""
    global _index
    with _lock:
        _index = None


def seed_terms(space: SemanticSpace,
               terms: Optional[Iterable[str]] = None) -> int:
    """Seed skeleton judgments for `terms` (None = every concept in space).

    Returns the number of thesaurus judgments applied; 0 when the layer is
    disabled, the index is empty, or all terms are already covered.
    Idempotency lives in core.seed_skeleton (has_skeleton check).
    """
    if not skeleton_enabled():
        return 0
    index = get_index()
    if len(index) == 0:
        return 0
    return seed_skeleton(space, index, terms=terms)
