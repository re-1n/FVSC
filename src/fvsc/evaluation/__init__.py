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
from .interpretations import (
    InterpretationEvaluation,
    ProposalEvaluation,
    evaluate_interpretation_proposal,
    summarize_interpretation_evaluations,
    surface_similarity,
)

__all__ = [
    "CaseEvaluation",
    "EvidenceRef",
    "GoldCase",
    "GoldLink",
    "GoldSet",
    "InterpretationEvaluation",
    "ProposalEvaluation",
    "RankedSources",
    "RetrievalEvaluation",
    "evaluate_rankings",
    "evaluate_interpretation_proposal",
    "load_gold_set",
    "summarize_interpretation_evaluations",
    "surface_similarity",
]
