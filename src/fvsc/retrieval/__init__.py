"""Deterministic retrieval baselines over transient source documents."""

from .context_compiler import (
    CompiledContext,
    RankingMethod,
    SemanticContextCompiler,
    SemanticContextUnit,
    approximate_tokens,
)
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
    "CompiledContext",
    "FusedHit",
    "JudgmentHit",
    "JudgmentSearchIndex",
    "LexicalHit",
    "LexicalSearchIndex",
    "LocatorMatchKind",
    "LocatorResolution",
    "LocatorStatus",
    "RankingMethod",
    "SemanticContextCompiler",
    "SemanticContextUnit",
    "SourceLocator",
    "SourceLocatorIndex",
    "approximate_tokens",
    "expand_source_context",
    "parse_source_locators",
    "reciprocal_rank_fusion",
    "search_documents",
    "search_judgment_evidence",
]
