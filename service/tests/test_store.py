from __future__ import annotations

import pickle

import pytest

from core.density_core import SemanticSpace
from service.store import SpaceBundle, SpaceStore


def test_distinct_names_do_not_collide_on_disk(tmp_path) -> None:
    store = SpaceStore(tmp_path)
    store.get_or_create("a!", dim=16)
    store.get_or_create("a?", dim=32)
    store.save_all()

    paths = sorted(tmp_path.glob("*.pkl"))
    assert len(paths) == 2
    assert paths[0].name != paths[1].name

    reloaded = SpaceStore(tmp_path)
    assert reloaded.get("a!").space.dim == 16
    assert reloaded.get("a?").space.dim == 32


def test_legacy_bundle_is_still_readable(tmp_path) -> None:
    bundle = SpaceBundle(name="legacy", space=SemanticSpace(dim=12))
    path = tmp_path / "legacy.pkl"
    with path.open("wb") as handle:
        pickle.dump(bundle, handle)

    store = SpaceStore(tmp_path)
    loaded = store.get("legacy")

    assert loaded is not None
    assert loaded.space.dim == 12


def test_name_mismatch_is_rejected(tmp_path) -> None:
    store = SpaceStore(tmp_path)
    path = store._pkl_path("expected")
    payload = {
        "magic": "fvsc-space-bundle",
        "version": 1,
        "bundle": SpaceBundle(name="different", space=SemanticSpace(dim=8)),
    }
    with path.open("wb") as handle:
        pickle.dump(payload, handle)

    with pytest.raises(ValueError, match="name mismatch"):
        store.get("expected")


def test_delete_reports_in_memory_deletion(tmp_path) -> None:
    store = SpaceStore(tmp_path)
    store.get_or_create("temporary")

    assert store.delete("temporary") is True
    assert store.delete("temporary") is False
