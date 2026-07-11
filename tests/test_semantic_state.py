from __future__ import annotations

import numpy as np
import pytest

from core.semantic_state import SemanticState


def _operator() -> np.ndarray:
    first = np.array([1.0, 0.0, 0.0])
    second = np.array([0.0, 1.0, 1.0]) / np.sqrt(2.0)
    return 2.0 * np.outer(first, first) + 0.5 * np.outer(second, second)


def test_from_operator_round_trips_legacy_matrix() -> None:
    operator = _operator()

    state = SemanticState.from_operator(
        operator,
        uncertainty=0.2,
        evidence_count=3,
    )

    assert state.mass == pytest.approx(2.5)
    assert np.trace(state.shape) == pytest.approx(1.0)
    assert state.uncertainty == pytest.approx(0.2)
    assert state.evidence_count == 3
    assert np.allclose(state.to_operator(), operator)


def test_semantic_shape_is_invariant_under_positive_rescaling() -> None:
    operator = _operator()

    original = SemanticState.from_operator(operator)
    rescaled = SemanticState.from_operator(17.0 * operator)

    assert rescaled.mass == pytest.approx(17.0 * original.mass)
    assert np.allclose(rescaled.shape, original.shape)


def test_shape_is_copied_and_read_only() -> None:
    source = np.eye(2) / 2.0
    state = SemanticState(mass=4.0, shape=source)

    source[0, 0] = 0.25
    assert state.shape[0, 0] == pytest.approx(0.5)

    with pytest.raises(ValueError):
        state.shape[0, 0] = 0.25


def test_empty_state_has_zero_mass_and_zero_operator() -> None:
    state = SemanticState.empty(4)

    assert state.is_empty
    assert state.dim == 4
    assert state.mass == 0.0
    assert state.uncertainty == 1.0
    assert np.count_nonzero(state.shape) == 0
    assert np.count_nonzero(state.to_operator()) == 0


def test_with_mass_preserves_shape_and_metadata() -> None:
    state = SemanticState.from_operator(
        _operator(),
        uncertainty=0.3,
        evidence_count=9,
    )

    changed = state.with_mass(11.0)

    assert changed.mass == pytest.approx(11.0)
    assert np.allclose(changed.shape, state.shape)
    assert changed.uncertainty == state.uncertainty
    assert changed.evidence_count == state.evidence_count


def test_rejects_non_symmetric_or_indefinite_operators() -> None:
    with pytest.raises(ValueError, match="symmetric"):
        SemanticState.from_operator(np.array([[1.0, 1.0], [0.0, 1.0]]))

    with pytest.raises(ValueError, match="positive semidefinite"):
        SemanticState.from_operator(np.diag([1.0, -0.1]))


def test_rejects_invalid_state_metadata() -> None:
    shape = np.eye(2) / 2.0

    with pytest.raises(ValueError, match="mass"):
        SemanticState(mass=-1.0, shape=shape)
    with pytest.raises(ValueError, match="uncertainty"):
        SemanticState(mass=1.0, shape=shape, uncertainty=1.1)
    with pytest.raises(ValueError, match="evidence_count"):
        SemanticState(mass=1.0, shape=shape, evidence_count=1.5)
    with pytest.raises(ValueError, match="evidence_count"):
        SemanticState(mass=1.0, shape=shape, evidence_count=True)
    with pytest.raises(ValueError, match="mass"):
        SemanticState(mass=1.0, shape=shape).with_mass(-0.5)


def test_non_empty_state_requires_unit_trace_shape() -> None:
    with pytest.raises(ValueError, match="trace 1"):
        SemanticState(mass=2.0, shape=np.eye(2))

    with pytest.raises(ValueError, match="zero shape"):
        SemanticState(mass=0.0, shape=np.eye(2) / 2.0)
