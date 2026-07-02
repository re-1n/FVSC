"""Restart invariance: determinism must hold ACROSS processes, not just within one.

Python's built-in hash() is randomized per process (PYTHONHASHSEED), so any
seed derived from it produces different base vectors after a service restart.
These tests spawn a REAL subprocess with a different PYTHONHASHSEED and verify
that term vectors, role transforms and consolidation behave identically.

Also covers purge_source (live vault-watch path), which previously crashed
with AttributeError by assigning to read-only properties.
"""

import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from density_core import SemanticSpace, Judgment, stable_hash  # noqa: E402

DIM = 32

# Script executed in a child process with a different PYTHONHASHSEED.
_CHILD = """
import sys, json
import numpy as np
sys.path.insert(0, {core_dir!r})
from density_core import SemanticSpace, Judgment
s = SemanticSpace(dim={dim})
v = s.get_term_vector("свобода")
r = s._role_transform(s.get_term_vector("ответственность"), "object_in_subject")
print(json.dumps({{"v": v.tolist(), "r": r.tolist()}}))
"""


def _run_in_fresh_process(hashseed: str):
    core_dir = os.path.dirname(os.path.abspath(__file__))
    env = dict(os.environ, PYTHONHASHSEED=hashseed)
    out = subprocess.run(
        [sys.executable, "-c", _CHILD.format(core_dir=core_dir, dim=DIM)],
        capture_output=True, text=True, env=env, check=True,
    )
    data = json.loads(out.stdout)
    return np.array(data["v"]), np.array(data["r"])


def test_stable_hash_is_process_independent():
    core_dir = os.path.dirname(os.path.abspath(__file__))
    script = (
        f"import sys; sys.path.insert(0, {core_dir!r}); "
        "from density_core import stable_hash; print(stable_hash('свобода'))"
    )
    results = set()
    for seed in ("0", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        out = subprocess.run([sys.executable, "-c", script],
                             capture_output=True, text=True, env=env, check=True)
        results.add(out.stdout.strip())
    assert len(results) == 1, f"stable_hash differs across processes: {results}"
    assert results == {str(stable_hash("свобода"))}


def test_term_vectors_survive_restart():
    """Same term must yield the same base vector in different processes."""
    v1, r1 = _run_in_fresh_process("1")
    v2, r2 = _run_in_fresh_process("424242")
    assert np.allclose(v1, v2, atol=1e-12), "get_term_vector is not restart-invariant"
    assert np.allclose(r1, r2, atol=1e-12), "_role_transform is not restart-invariant"

    # And matches the current process too
    s = SemanticSpace(dim=DIM)
    assert np.allclose(s.get_term_vector("свобода"), v1, atol=1e-12)


def test_consolidation_fires_after_restart_equivalent():
    """Identical judgments produce identical vectors -> consolidation must fire,
    keeping component count at 1 with activation_count growing."""
    s = SemanticSpace(dim=DIM)
    for _ in range(3):
        s.materialize_judgment(Judgment(
            subject="свобода", verb="требует", object="ответственность",
            source_text="note.md",
        ))
    concept = s.concepts["свобода"]
    active = [c for c in concept.components if not c.archived]
    assert len(active) == 1, (
        f"consolidation did not fire: {len(active)} components for identical judgments"
    )
    assert active[0].activation_count >= 3


def test_purge_source_archives_and_rebuilds():
    """Live vault-watch path: purge must archive components, not crash."""
    s = SemanticSpace(dim=DIM)
    for obj in ("ответственность", "выбор", "риск"):
        s.materialize_judgment(Judgment(
            subject="свобода", verb="требует", object=obj, source_text="note.md",
        ))
    s.materialize_judgment(Judgment(
        subject="свобода", verb="дает", object="силу", source_text="other.md",
    ))
    # Force ρ build so caches exist before purge
    _ = s.concepts["свобода"].rho

    n = s.purge_source("note.md")
    assert n > 0

    concept = s.concepts["свобода"]
    live_sources = {c.judgment.source_text for c in concept.components if not c.archived}
    assert "note.md" not in live_sources
    assert "other.md" in live_sources
    # ρ must be rebuildable after invalidation
    rho = concept.rho
    assert rho is not None and np.isfinite(rho).all()
