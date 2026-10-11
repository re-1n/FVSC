"""Smoke test for the per-source provenance builder (evidence layer).

Provenance attributes each strong concept's mass to its source files and splits
child-containment co-occurrence across sources. The silent pool captures tokens
that were uttered but did not enter the strong vocabulary.
"""

from __future__ import annotations

import pytest

from fvsc.evidence import build_provenance, build_provenance_and_silent
from fvsc.ingest import ParseConfig


def test_build_provenance_partitions_concept_mass_across_sources() -> None:
    si = {"alpha": {"weight": 1.0}, "beta": {"weight": 0.5}}
    files = {"a.txt": "alpha beta", "b.txt": "alpha beta"}
    config = ParseConfig(min_freq=1, window=5)

    provenance = build_provenance(si, files, config)

    assert "alpha" in provenance and "beta" in provenance
    # "self" fractions partition the concept's mass across files -> sum to 1.0
    assert sum(provenance["alpha"]["self"].values()) == pytest.approx(1.0)
    assert sum(provenance["beta"]["self"].values()) == pytest.approx(1.0)


def test_silent_pool_captures_tokens_outside_strong_vocab() -> None:
    si = {"alpha": {"weight": 1.0}}
    files = {"a.txt": "alpha gamma", "b.txt": "alpha gamma"}
    config = ParseConfig(min_freq=1, window=5, min_token_len=2)

    provenance, silent = build_provenance_and_silent(si, files, config)

    # gamma is not strong -> absent from provenance, captured in the silent pool
    assert "gamma" not in provenance
    assert "gamma" in silent
    assert silent["gamma"]["freq"] == 2


def test_contains_splits_child_co_occurrence_across_sources() -> None:
    si = {"alpha": {"weight": 1.0, "contains": {"beta": 0.5}}, "beta": {"weight": 0.5}}
    files = {"a.txt": "alpha beta beta", "b.txt": "alpha beta"}
    config = ParseConfig(min_freq=1, window=5)

    provenance = build_provenance(si, files, config)

    child = provenance["alpha"]["contains"]["beta"]
    # child co-occurrence is split across source files -> sums to 1.0
    assert sum(child.values()) == pytest.approx(1.0)
    assert set(child) == {"a.txt", "b.txt"}
