from __future__ import annotations

import numpy as np
import pytest

from core.semantic_metrics import (
    inclusion_margin,
    operator_inclusion,
    relative_entropy_inclusion,
    shape_overlap,
)
from core.semantic_state import SemanticState


def _state(diagonal: list[float], *, mass: float = 1.0) -> SemanticState:
    shape = np.diag(diagonal).astype(float)
    shape /= np.trace(shape)
    return SemanticState(mass=mass, shape=shape)


def test_operator_inclusion_is_directional_for_broad_container() -> None:
    container = _state([0.8, 0.2])
    dominant_facet = _state([1.0, 0.0])
    peripheral_facet = _state([0.0, 1.0])

    dominant_score = operator_inclusion(dominant_facet, container)
    peripheral_score = operator_inclusion(peripheral_facet, container)

    assert dominant_score > peripheral_score
    assert dominant_score == pytest.approx(0.8, abs=2e-5)
    assert peripheral_score == pytest.approx(0.2, abs=2e-5)
    assert inclusion_margin(container, dominant_facet) > 0.0


def test_shape_metrics_are_invariant_to_evidence_mass() -> None:
    container_low_mass = _state([0.75, 0.25], mass=2.0)
    container_high_mass = _state([0.75, 0.25], mass=2000.0)
    contained_low_mass = _state([1.0, 0.0], mass=1.0)
    contained_high_mass = _state([1.0, 0.0], mass=9000.0)

    assert operator_inclusion(contained_low_mass, container_low_mass) == pytest.approx(
        operator_inclusion(contained_high_mass, container_high_mass)
    )
    assert inclusion_margin(container_low_mass, contained_low_mass) == pytest.approx(
        inclusion_margin(container_high_mass, contained_high_mass)
    )
    assert relative_entropy_inclusion(contained_low_mass, container_low_mass) == pytest.approx(
        relative_entropy_inclusion(contained_high_mass, container_high_mass)
    )
    assert shape_overlap(contained_low_mass, container_low_mass) == pytest.approx(
        shape_overlap(contained_high_mass, container_high_mass)
    )


def test_identical_pure_shapes_score_one() -> None:
    first = _state([1.0, 0.0])
    second = _state([1.0, 0.0], mass=10.0)

    assert operator_inclusion(first, second) == pytest.approx(1.0)
    assert operator_inclusion(second, first) == pytest.approx(1.0)
    assert inclusion_margin(first, second) == pytest.approx(0.0)
    assert relative_entropy_inclusion(first, second) == pytest.approx(1.0)
    assert shape_overlap(first, second) == pytest.approx(1.0)


def test_relative_entropy_inclusion_is_asymmetric() -> None:
    broad = _state([0.8, 0.2])
    narrow = _state([1.0, 0.0])

    narrow_in_broad = relative_entropy_inclusion(narrow, broad)
    broad_in_narrow = relative_entropy_inclusion(broad, narrow)

    assert 0.0 <= narrow_in_broad <= 1.0
    assert 0.0 <= broad_in_narrow <= 1.0
    assert narrow_in_broad > broad_in_narrow


def test_empty_states_have_no_shape_signal() -> None:
    empty = SemanticState.empty(2)
    non_empty = _state([0.5, 0.5])

    assert operator_inclusion(empty, non_empty) == 0.0
    assert operator_inclusion(non_empty, empty) == 0.0
    assert relative_entropy_inclusion(empty, non_empty) == 0.0
    assert shape_overlap(empty, non_empty) == 0.0


def test_metrics_reject_incompatible_dimensions_and_regularization() -> None:
    two_dimensional = _state([0.5, 0.5])
    three_dimensional = _state([1.0, 1.0, 1.0])

    with pytest.raises(ValueError, match="equal dimensions"):
        shape_overlap(two_dimensional, three_dimensional)
    with pytest.raises(ValueError, match="regularization"):
        operator_inclusion(two_dimensional, two_dimensional, regularization=0.0)
    with pytest.raises(ValueError, match="regularization"):
        relative_entropy_inclusion(two_dimensional, two_dimensional, regularization=1.0)
