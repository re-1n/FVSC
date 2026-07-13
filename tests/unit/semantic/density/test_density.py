"""Smoke test for the density-matrix optional local backend (ADR-003).

Density is NOT canonical memory (ADR-001) and is NOT asserted to outperform any
baseline. These tests check only that the linear-algebra invariants of a density
matrix hold after materialization, so the 1089-line backend is not silent dead
code in CI. ADR-003: new code must not depend on density for correctness.
"""

from __future__ import annotations

import numpy as np
import pytest

from fvsc.semantic.density import (
    Concept,
    Judgment,
    SemanticSpace,
    containment,
    purity,
    stable_hash,
)


def test_materialize_judgment_builds_symmetric_positive_density_matrix() -> None:
    space = SemanticSpace(dim=8)
    space.materialize_judgment(
        Judgment(subject="свобода", verb="требует", object="ответственность")
    )
    space.materialize_judgment(
        Judgment(subject="ответственность", verb="требует", object="дисциплина")
    )

    freedom = space.concepts["свобода"]
    responsibility = space.concepts["ответственность"]
    assert isinstance(freedom, Concept)
    assert isinstance(responsibility, Concept)

    rho = freedom.rho
    assert rho is not None
    # A real density matrix is symmetric and positive semidefinite.
    assert np.allclose(rho, rho.T, atol=1e-10)
    assert np.all(np.linalg.eigvalsh(rho) >= -1e-10)

    # Normalized form is trace-one.
    rho_norm = freedom.rho_norm
    assert np.trace(rho_norm) == pytest.approx(1.0, abs=1e-9)
    # Purity of a d-dim normalized state is bounded in [1/d, 1].
    assert 1.0 / 8.0 - 1e-9 <= purity(rho_norm) <= 1.0 + 1e-9


def test_containment_is_finite_and_bounded() -> None:
    space = SemanticSpace(dim=8)
    space.materialize_judgment(
        Judgment(subject="система", verb="содержит", object="модуль")
    )

    system = space.concepts["система"].rho_norm
    module = space.concepts["модуль"].rho_norm
    assert system is not None and module is not None

    forward = containment(system, module)
    reverse = containment(module, system)

    assert np.isfinite(forward)
    assert np.isfinite(reverse)
    # containment = Tr(A·B)/Tr(A); for normalized states it lies in [0, 1].
    assert -1e-9 <= forward <= 1.0 + 1e-9
    assert -1e-9 <= reverse <= 1.0 + 1e-9


def test_stable_hash_is_deterministic_across_calls() -> None:
    assert stable_hash("ответственность") == stable_hash("ответственность")
    assert stable_hash("alpha") != stable_hash("beta")
