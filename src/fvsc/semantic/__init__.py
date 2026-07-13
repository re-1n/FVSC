"""Semantic representations: graph / containers / density."""

from .state import SemanticState
from .metrics import (
    inclusion_margin,
    operator_inclusion,
    relative_entropy_inclusion,
    shape_overlap,
)

__all__ = [
    "SemanticState",
    "inclusion_margin",
    "operator_inclusion",
    "relative_entropy_inclusion",
    "shape_overlap",
]
