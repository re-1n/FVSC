"""Deterministic retrieval baselines over transient source documents."""

from .lexical import LexicalHit, expand_source_context, search_documents
from .judgments import JudgmentHit, search_judgment_evidence

__all__ = [
    "JudgmentHit",
    "LexicalHit",
    "expand_source_context",
    "search_documents",
    "search_judgment_evidence",
]
