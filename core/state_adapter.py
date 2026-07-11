"""Compatibility adapters between legacy FVSC concepts and ``SemanticState``.

The adapter keeps Phase 1 non-destructive: ``density_core.Concept`` continues to
expose unnormalised ``rho`` matrices, while new code can consume explicit
mass/shape states without importing or mutating the legacy core.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

import numpy as np

from .semantic_state import SemanticState


class LegacyConcept(Protocol):
    """Structural protocol implemented by ``density_core.Concept``."""

    components: Iterable[Any]

    @property
    def rho(self) -> np.ndarray | None: ...

    @property
    def rho_deep(self) -> np.ndarray | None: ...


def active_evidence_count(concept: LegacyConcept) -> int:
    """Count active evidence activations represented by a legacy concept.

    Consolidated components preserve their reinforcement count in
    ``activation_count``. Archived components are intentionally excluded because
    they are absent from the currently materialized operator.
    """
    total = 0
    for component in concept.components:
        if bool(getattr(component, "archived", False)):
            continue
        activation_count = getattr(component, "activation_count", 1)
        if isinstance(activation_count, bool):
            activation_count = 1
        try:
            count = int(activation_count)
        except (TypeError, ValueError):
            count = 1
        total += max(0, count)
    return total


def concept_state(
    concept: LegacyConcept,
    *,
    recursive: bool = True,
    uncertainty: float = 0.0,
) -> SemanticState | None:
    """Materialize a ``SemanticState`` from a legacy concept.

    ``recursive=True`` mirrors existing query behavior by using ``rho_deep``.
    The adapter never writes to the concept or its cached matrices.
    """
    operator = concept.rho_deep if recursive else concept.rho
    if operator is None:
        return None
    return SemanticState.from_operator(
        operator,
        uncertainty=uncertainty,
        evidence_count=active_evidence_count(concept),
    )


def direct_concept_state(
    concept: LegacyConcept,
    *,
    uncertainty: float = 0.0,
) -> SemanticState | None:
    """Convenience wrapper for the direct, non-recursive operator."""
    return concept_state(concept, recursive=False, uncertainty=uncertainty)


def deep_concept_state(
    concept: LegacyConcept,
    *,
    uncertainty: float = 0.0,
) -> SemanticState | None:
    """Convenience wrapper for the recursively deepened operator."""
    return concept_state(concept, recursive=True, uncertainty=uncertainty)
