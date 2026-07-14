"""Deterministic retrieval baselines over transient source documents."""

from .lexical import LexicalHit, LexicalSearchIndex, expand_source_context, search_documents
from .judgments import JudgmentHit, JudgmentSearchIndex, search_judgment_evidence
from .fusion import FusedHit, reciprocal_rank_fusion

__all__ = [
    "JudgmentHit",
    "JudgmentSearchIndex",
    "LexicalHit",
    "LexicalSearchIndex",
    "FusedHit",
    "expand_source_context",
    "search_documents",
    "search_judgment_evidence",
    "reciprocal_rank_fusion",
]
