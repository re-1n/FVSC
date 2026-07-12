from __future__ import annotations

import pickle

import pytest

from core.density_core import SemanticSpace
from core.vault_cache import CACHE_MAGIC, CACHE_VERSION, load_vault_cache, save_vault_cache


def _blob() -> dict:
    return {
        "space": SemanticSpace(dim=16),
        "si": {"свобода": {"weight": 1.0, "contains": {}}},
        "n_files": 1,
        "corpus_chars": 42,
    }


def test_cache_round_trip_uses_versioned_envelope(tmp_path) -> None:
    path = tmp_path / "_fvsc_cache.pkl"

    save_vault_cache(path, _blob())
    loaded = load_vault_cache(path)

    assert loaded["space"].dim == 16
    assert loaded["n_files"] == 1
    with path.open("rb") as handle:
        envelope = pickle.load(handle)
    assert envelope["magic"] == CACHE_MAGIC
    assert envelope["version"] == CACHE_VERSION


def test_legacy_cache_is_readable(tmp_path) -> None:
    path = tmp_path / "legacy.pkl"
    with path.open("wb") as handle:
        pickle.dump(_blob(), handle)

    assert load_vault_cache(path)["corpus_chars"] == 42


def test_invalid_schema_is_rejected(tmp_path) -> None:
    path = tmp_path / "invalid.pkl"
    with path.open("wb") as handle:
        pickle.dump({"space": "not-a-space", "si": {}}, handle)

    with pytest.raises(ValueError, match="SemanticSpace"):
        load_vault_cache(path)


def test_symlink_cache_is_rejected(tmp_path) -> None:
    target = tmp_path / "target.pkl"
    save_vault_cache(target, _blob())
    link = tmp_path / "link.pkl"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks are unavailable on this platform")

    with pytest.raises(ValueError, match="non-regular"):
        load_vault_cache(link)
