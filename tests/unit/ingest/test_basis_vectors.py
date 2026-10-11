from __future__ import annotations

import numpy as np
import pytest

from fvsc.ingest.basis_vectors import BasisVectorGenerator


def test_random_indexing_is_stable_for_same_seed() -> None:
    a = BasisVectorGenerator(dim=32, seed=7).get_vector("свобода")
    b = BasisVectorGenerator(dim=32, seed=7).get_vector("свобода")

    np.testing.assert_array_equal(a, b)


def test_seed_namespaces_random_indexing() -> None:
    a = BasisVectorGenerator(dim=32, seed=7).get_vector("свобода")
    b = BasisVectorGenerator(dim=32, seed=8).get_vector("свобода")

    assert not np.array_equal(a, b)


def test_custom_vectors_validate_shape_and_norm() -> None:
    gen = BasisVectorGenerator(dim=4, strategy="custom")

    with pytest.raises(ValueError):
        gen.set_custom_vector("bad-shape", np.ones(3))
    with pytest.raises(ValueError):
        gen.set_custom_vector("zero", np.zeros(4))
