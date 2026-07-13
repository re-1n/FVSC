"""Ingestion — language-agnostic text → concept tree → vectors primitives.

The text parser converts raw text (any language, no spaCy / no language-specific
tooling) into a concept tree of asymmetric containment weights.
``semantic_input`` then turns that tree into concept vectors and density matrices.
Together they are the foundation of the language-agnostic pivot.
"""

from .basis_vectors import BasisVectorGenerator, create_basis_generator
from .parser import (
    DEFAULT_COORDINATORS,
    DEFAULT_STOPWORDS_RU_EN,
    ParseConfig,
    extract_concepts_and_cooccurrence,
    parse_text,
    split_paragraphs,
    split_sentences,
    text_to_semantic_input,
    tokenize,
)
from .semantic_input import (
    ConceptDef,
    SemanticInput,
    SemanticInputParser,
    parse_semantic_input,
)
from .vault_ingest import (
    DEFAULT_VAULT_EXCLUDE_DIRS,
    OBSIDIAN_VAULT_ADAPTER,
    SOURCE_KINDS,
    SourceDocument,
    SourceKind,
    VaultScan,
    normalize_markdown,
    scan_vault,
)

__all__ = [
    "BasisVectorGenerator",
    "ConceptDef",
    "DEFAULT_VAULT_EXCLUDE_DIRS",
    "DEFAULT_COORDINATORS",
    "DEFAULT_STOPWORDS_RU_EN",
    "ParseConfig",
    "OBSIDIAN_VAULT_ADAPTER",
    "SOURCE_KINDS",
    "SemanticInput",
    "SemanticInputParser",
    "SourceDocument",
    "SourceKind",
    "VaultScan",
    "create_basis_generator",
    "extract_concepts_and_cooccurrence",
    "normalize_markdown",
    "parse_semantic_input",
    "parse_text",
    "scan_vault",
    "split_paragraphs",
    "split_sentences",
    "text_to_semantic_input",
    "tokenize",
]
