"""Density-matrix local state — optional swappable backend (ADR-003).

Density is NEVER canonical memory (that is the EvidenceLedger, ADR-001). It is one
of several local-state backends and may represent the local contextual state of a
container. New code must not depend on density for correctness. NOTE: density
snapshots inject wall-clock time and are therefore NOT restart-invariant — do not
wire them into any determinism/digest.
"""

from .core import (
    Component,
    Concept,
    Judgment,
    SemanticSpace,
    containment,
    facets,
    graded_hyponymy,
    purity,
    stable_hash,
    trace_inner_product,
    von_neumann_entropy,
)

__all__ = [
    "Component",
    "Concept",
    "Judgment",
    "SemanticSpace",
    "containment",
    "facets",
    "graded_hyponymy",
    "purity",
    "stable_hash",
    "trace_inner_product",
    "von_neumann_entropy",
]
