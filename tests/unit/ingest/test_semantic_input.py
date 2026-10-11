"""Smoke test for the concept-tree -> vectors/matrices bridge (ingest layer).

Also exercises the parser -> semantic_input end-to-end bridge (parse_text), which
becomes functional once both modules are ported into the ingest package.
"""

from __future__ import annotations

import numpy as np

from fvsc.ingest import ParseConfig, parse_semantic_input, parse_text


def test_parse_semantic_input_returns_vectors_and_density_matrices() -> None:
    si = {
        "alpha": {"weight": 1.0, "contains": {"beta": 0.5}},
        "beta": {"weight": 0.5},
    }
    vectors, rhos = parse_semantic_input(si, dim=8)

    assert set(vectors) == {"alpha", "beta"}
    assert set(rhos) == {"alpha", "beta"}
    for vector in vectors.values():
        assert vector.shape == (8,)
    for rho in rhos.values():
        assert rho.shape == (8, 8)
        # density matrices are symmetric
        assert np.allclose(rho, rho.T)


def test_parse_text_bridges_parser_to_density_matrices() -> None:
    # End-to-end: raw text -> parser -> semantic_input -> vectors + rhos.
    si, vectors, rhos = parse_text(
        "alpha beta. alpha beta gamma.",
        dim=8,
        config=ParseConfig(min_freq=1, window=5),
    )
    assert si  # non-empty concept tree
    assert vectors and rhos
    assert "alpha" in rhos and "beta" in rhos
