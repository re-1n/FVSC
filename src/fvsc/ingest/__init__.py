"""Ingestion — language-agnostic text → semantic_input primitives.

The text parser converts raw text (any language, no spaCy / no language-specific
tooling) into a concept tree of asymmetric containment weights that downstream
representations (graph / containers / density) consume. This is the foundation
of the language-agnostic pivot.

NOTE: ``parse_text`` (the end-to-end wrapper that also builds density matrices)
lives in ``parser.py`` but is NOT re-exported here yet — it depends on
``semantic_input`` (not yet ported). Import it explicitly from
``fvsc.ingest.parser`` once ``semantic_input`` lands.
"""

from .parser import (
    DEFAULT_COORDINATORS,
    DEFAULT_STOPWORDS_RU_EN,
    ParseConfig,
    extract_concepts_and_cooccurrence,
    split_paragraphs,
    split_sentences,
    text_to_semantic_input,
    tokenize,
)

__all__ = [
    "DEFAULT_COORDINATORS",
    "DEFAULT_STOPWORDS_RU_EN",
    "ParseConfig",
    "extract_concepts_and_cooccurrence",
    "split_paragraphs",
    "split_sentences",
    "text_to_semantic_input",
    "tokenize",
]
