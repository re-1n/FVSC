"""Deterministic retrieval baselines over transient source documents."""

from .lexical import LexicalHit, LexicalSearchIndex, expand_source_context, search_documents
from .judgments import JudgmentHit, JudgmentSearchIndex, search_judgment_evidence
from .fusion import FusedHit, reciprocal_rank_fusion
from .locators import (
    LocatorMatchKind,
    LocatorResolution,
    LocatorStatus,
    SourceLocator,
    SourceLocatorIndex,
    parse_source_locators,
)

__all__ = [
    "JudgmentHit",
    "JudgmentSearchIndex",
    "LexicalHit",
    "LexicalSearchIndex",
    "LocatorMatchKind",
    "LocatorResolution",
    "LocatorStatus",
    "SourceLocator",
    "SourceLocatorIndex",
    "FusedHit",
    "expand_source_context",
    "search_documents",
    "search_judgment_evidence",
    "reciprocal_rank_fusion",
    "parse_source_locators",
]
