"""Deterministic retrieval baselines over transient source documents."""

from .lexical import LexicalHit, expand_source_context, search_documents

__all__ = ["LexicalHit", "expand_source_context", "search_documents"]
