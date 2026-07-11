"""Mass-invariant metrics for normalized FVSC semantic states.

These functions operate only on ``SemanticState.shape``. Evidence mass is never
consulted, so multiplying a legacy operator by a positive scalar cannot change a
score. This is the basis for trace-matched evaluation and future context-aware
operators.
"""

from __future__ import annotations

import numpy as np

from .semantic_state import SemanticState


DEFAULT_REGULARIZATION = 1e-6
_EPS = 1e-12


def _require_compatible(first: SemanticState, second: SemanticState) -> None:
    if first.dim != second.dim:
        raise ValueError(
            f"semantic states must have equal dimensions; got {first.dim} and {second.dim}"
        )


def _regularized_shape(state: SemanticState, regularization: float) -> np.ndarray:
    if not np.isfinite(regularization) or not 0.0 < regularization < 1.0:
        raise ValueError("regularization must be finite and in (0, 1)")
    identity = np.eye(state.dim, dtype=float) / state.dim
    return (1.0 - regularization) * state.shape + regularization * identity


def shape_overlap(first: SemanticState, second: SemanticState) -> float:
    """Hilbert-Schmidt overlap of two normalized semantic shapes.

    The score is symmetric and lies in ``[0, 1]`` for PSD trace-one states.
    Empty states have no semantic shape and return zero overlap.
    """
    _require_compatible(first, second)
    if first.is_empty or second.is_empty:
        return 0.0
    score = float(np.trace(first.shape @ second.shape))
    return float(np.clip(score, 0.0, 1.0))


def operator_inclusion(
    contained: SemanticState,
    container: SemanticState,
    *,
    regularization: float = DEFAULT_REGULARIZATION,
) -> float:
    """Degree to which ``contained`` is operator-included in ``container``.

    For normalized shapes A (contained) and B (container), the score is the
    largest ``k in [0, 1]`` for which ``B - k A`` is positive semidefinite.
    A small identity mixture makes the calculation stable for rank-deficient
    empirical states without reintroducing evidence mass.
    """
    _require_compatible(contained, container)
    if contained.is_empty or container.is_empty:
        return 0.0

    child = _regularized_shape(contained, regularization)
    parent = _regularized_shape(container, regularization)

    eigenvalues, eigenvectors = np.linalg.eigh(parent)
    eigenvalues = np.clip(eigenvalues, _EPS, None)
    inverse_sqrt = (eigenvectors * (1.0 / np.sqrt(eigenvalues))) @ eigenvectors.T
    relative = inverse_sqrt @ child @ inverse_sqrt
    relative = 0.5 * (relative + relative.T)
    largest = float(np.max(np.linalg.eigvalsh(relative)))
    if largest <= _EPS:
        return 0.0
    return float(np.clip(1.0 / largest, 0.0, 1.0))


def inclusion_margin(
    container: SemanticState,
    contained: SemanticState,
    *,
    regularization: float = DEFAULT_REGULARIZATION,
) -> float:
    """Directional shape margin for the hypothesis ``container contains contained``."""
    forward = operator_inclusion(
        contained,
        container,
        regularization=regularization,
    )
    reverse = operator_inclusion(
        container,
        contained,
        regularization=regularization,
    )
    return float(forward - reverse)


def relative_entropy_inclusion(
    contained: SemanticState,
    container: SemanticState,
    *,
    regularization: float = DEFAULT_REGULARIZATION,
) -> float:
    """Return ``exp(-D(contained || container))`` for normalized shapes.

    Quantum relative entropy is asymmetric. Identity regularization guarantees
    finite matrix logarithms for empirical low-rank states. The returned score is
    clipped to ``[0, 1]``; identical states score one.
    """
    _require_compatible(contained, container)
    if contained.is_empty or container.is_empty:
        return 0.0

    child = _regularized_shape(contained, regularization)
    parent = _regularized_shape(container, regularization)

    child_values, child_vectors = np.linalg.eigh(child)
    parent_values, parent_vectors = np.linalg.eigh(parent)
    child_values = np.clip(child_values, _EPS, None)
    parent_values = np.clip(parent_values, _EPS, None)

    log_child = (child_vectors * np.log(child_values)) @ child_vectors.T
    log_parent = (parent_vectors * np.log(parent_values)) @ parent_vectors.T
    divergence = float(np.trace(child @ (log_child - log_parent)))
    divergence = max(0.0, divergence)
    return float(np.clip(np.exp(-divergence), 0.0, 1.0))
