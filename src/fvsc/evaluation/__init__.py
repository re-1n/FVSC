"""Owner-validated evaluation contracts and metrics."""

from .gold import (
    CaseEvaluation,
    EvidenceRef,
    GoldCase,
    GoldLink,
    GoldSet,
    RankedSources,
    RetrievalEvaluation,
    evaluate_rankings,
    load_gold_set,
)

__all__ = [
    "CaseEvaluation",
    "EvidenceRef",
    "GoldCase",
    "GoldLink",
    "GoldSet",
    "RankedSources",
    "RetrievalEvaluation",
    "evaluate_rankings",
    "load_gold_set",
]
