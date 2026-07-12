from __future__ import annotations

import time

import numpy as np
import pytest

from core.density_core import Concept, Judgment
from core.state_adapter import (
    active_evidence_count,
    concept_state,
    deep_concept_state,
    direct_concept_state,
)


def _concept() -> Concept:
    concept = Concept(term="свобода")
    timestamp = time.time() + 3600.0
    first = Judgment(
        subject="свобода",
        verb="требует",
        object="ответственность",
        timestamp=timestamp,
    )
    second = Judgment(
        subject="свобода",
        verb="включает",
        object="выбор",
        timestamp=timestamp,
    )
    concept.add_component(np.array([1.0, 0.0]), 2.0, first)
    concept.add_component(np.array([0.0, 1.0]), 1.0, second)
    return concept


def test_direct_adapter_round_trips_current_operator() -> None:
    concept = _concept()

    state = direct_concept_state(concept)

    assert state is not None
    assert state.mass == pytest.approx(float(np.trace(concept.rho)))
    assert state.evidence_count == 2
    assert np.allclose(state.to_operator(), concept.rho)
    assert np.trace(state.shape) == pytest.approx(1.0)


def test_recursive_adapter_uses_deep_operator_without_mutating_direct_state() -> None:
    concept = _concept()
    direct_before = concept.rho.copy()
    concept._rho_recursive = 4.0 * concept.rho_norm

    direct = concept_state(concept, recursive=False)
    deep = deep_concept_state(concept)

    assert direct is not None and deep is not None
    assert direct.mass == pytest.approx(float(np.trace(direct_before)))
    assert deep.mass == pytest.approx(4.0)
    assert np.allclose(direct.to_operator(), direct_before)
    assert np.allclose(concept.rho, direct_before)


def test_adapter_returns_none_for_unmaterialized_concept() -> None:
    concept = Concept(term="пустота")

    assert concept_state(concept) is None
    assert direct_concept_state(concept) is None


def test_active_evidence_count_respects_consolidation_and_archival() -> None:
    concept = _concept()
    concept.components[0].activation_count = 3
    concept.components[1].archived = True

    assert active_evidence_count(concept) == 3
