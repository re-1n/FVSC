"""Mass/shape decomposition for FVSC semantic operators.

Legacy FVSC matrices are positive semidefinite operators whose trace carries
accumulated evidence mass.  ``SemanticState`` makes that contract explicit:

* ``mass`` stores the non-negative trace/evidence strength;
* ``shape`` stores a read-only PSD operator with trace one when non-empty;
* ``uncertainty`` and ``evidence_count`` are state metadata, not matrix mass.

This module is intentionally independent from ``density_core`` so it can be used
by persistence, snapshots and future operator runtimes without circular imports.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


TRACE_EPSILON = 1e-12
SYMMETRY_TOLERANCE = 1e-8
PSD_TOLERANCE = 1e-8
NORMALIZATION_TOLERANCE = 1e-8


def _validated_psd_matrix(value: np.ndarray, *, name: str) -> np.ndarray:
    """Return a symmetric, read-only PSD copy of ``value``.

    Tiny negative eigenvalues caused by floating-point roundoff are projected to
    zero. Materially non-symmetric or indefinite matrices are rejected rather
    than silently reinterpreted.
    """
    matrix = np.asarray(value, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"{name} must be a square matrix")
    if matrix.shape[0] == 0:
        raise ValueError(f"{name} must have positive dimension")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values")

    symmetric = 0.5 * (matrix + matrix.T)
    if not np.allclose(matrix, symmetric, atol=SYMMETRY_TOLERANCE, rtol=0.0):
        raise ValueError(f"{name} must be symmetric")

    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    minimum = float(eigenvalues[0])
    if minimum < -PSD_TOLERANCE:
        raise ValueError(f"{name} must be positive semidefinite; min eigenvalue={minimum:.6g}")

    if minimum < 0.0:
        eigenvalues = np.clip(eigenvalues, 0.0, None)
        symmetric = (eigenvectors * eigenvalues) @ eigenvectors.T
        symmetric = 0.5 * (symmetric + symmetric.T)

    result = np.array(symmetric, dtype=float, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True, eq=False)
class SemanticState:
    """Immutable semantic state with explicit evidence mass and normalized shape.

    Non-empty states require ``trace(shape) == 1``. Empty states use a zero
    matrix and ``mass == 0``. The shape array is copied and marked read-only.
    """

    mass: float
    shape: np.ndarray
    uncertainty: float = 0.0
    evidence_count: int = 0

    def __post_init__(self) -> None:
        mass = float(self.mass)
        uncertainty = float(self.uncertainty)

        if isinstance(self.evidence_count, (bool, np.bool_)):
            raise ValueError("evidence_count must be a non-negative integer")
        evidence_count = int(self.evidence_count)

        if not np.isfinite(mass) or mass < 0.0:
            raise ValueError("mass must be finite and non-negative")
        if not np.isfinite(uncertainty) or not 0.0 <= uncertainty <= 1.0:
            raise ValueError("uncertainty must be finite and in [0, 1]")
        if evidence_count < 0 or evidence_count != self.evidence_count:
            raise ValueError("evidence_count must be a non-negative integer")

        shape = _validated_psd_matrix(self.shape, name="shape")
        trace = float(np.trace(shape))

        if mass <= TRACE_EPSILON:
            if np.linalg.norm(shape, ord="fro") > NORMALIZATION_TOLERANCE:
                raise ValueError("an empty state must use a zero shape matrix")
            mass = 0.0
        elif not np.isclose(trace, 1.0, atol=NORMALIZATION_TOLERANCE, rtol=0.0):
            raise ValueError(f"a non-empty state's shape must have trace 1; got {trace:.12g}")

        object.__setattr__(self, "mass", mass)
        object.__setattr__(self, "shape", shape)
        object.__setattr__(self, "uncertainty", uncertainty)
        object.__setattr__(self, "evidence_count", evidence_count)

    @classmethod
    def from_operator(
        cls,
        operator: np.ndarray,
        *,
        uncertainty: float = 0.0,
        evidence_count: int = 0,
    ) -> "SemanticState":
        """Split an unnormalised PSD operator into trace mass and shape."""
        matrix = _validated_psd_matrix(operator, name="operator")
        mass = float(np.trace(matrix))
        if mass <= TRACE_EPSILON:
            shape = np.zeros_like(matrix)
            mass = 0.0
        else:
            shape = matrix / mass
        return cls(
            mass=mass,
            shape=shape,
            uncertainty=uncertainty,
            evidence_count=evidence_count,
        )

    @classmethod
    def empty(
        cls,
        dim: int,
        *,
        uncertainty: float = 1.0,
        evidence_count: int = 0,
    ) -> "SemanticState":
        """Create an empty state of a known semantic dimension."""
        if isinstance(dim, bool) or not isinstance(dim, int) or dim <= 0:
            raise ValueError("dim must be a positive integer")
        return cls(
            mass=0.0,
            shape=np.zeros((dim, dim), dtype=float),
            uncertainty=uncertainty,
            evidence_count=evidence_count,
        )

    @property
    def dim(self) -> int:
        return int(self.shape.shape[0])

    @property
    def is_empty(self) -> bool:
        return self.mass <= TRACE_EPSILON

    def to_operator(self) -> np.ndarray:
        """Reconstruct a writable copy of the legacy unnormalised operator."""
        return np.array(self.mass * self.shape, dtype=float, copy=True)

    def with_mass(self, mass: float) -> "SemanticState":
        """Return the same semantic shape with a different evidence mass."""
        mass = float(mass)
        if not np.isfinite(mass) or mass < 0.0:
            raise ValueError("mass must be finite and non-negative")
        if mass <= TRACE_EPSILON:
            return SemanticState.empty(
                self.dim,
                uncertainty=self.uncertainty,
                evidence_count=self.evidence_count,
            )
        return SemanticState(
            mass=mass,
            shape=self.shape,
            uncertainty=self.uncertainty,
            evidence_count=self.evidence_count,
        )
