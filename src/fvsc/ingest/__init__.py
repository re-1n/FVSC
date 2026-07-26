"""Ingestion — language-agnostic text → concept tree → vectors primitives.

The text parser converts raw text (any language, no spaCy / no language-specific
tooling) into a concept tree of asymmetric containment weights.
``semantic_input`` then turns that tree into concept vectors and density matrices.
Together they are the foundation of the language-agnostic pivot.
"""

from .basis_vectors import BasisVectorGenerator, create_basis_generator
from .exocortex_ingest import (
    TELEGRAM_EXPORT_ADAPTER,
    TelegramExportResult,
    clean_external_text,
    load_telegram_export,
)
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
from .judgment_events import (
    JUDGMENT_DERIVATION,
    JUDGMENT_EVENT_EXTRACTOR,
    JUDGMENT_EVENT_EXTRACTOR_VERSION,
    SourceSpan,
    judgment_to_evidence_event,
)
from .language_frontend import LanguageFrontend
from .russian_judgments import (
    JudgmentCandidate,
    JudgmentExtractor,
    MorphAnalysis,
    Morphology,
    Pymorphy3Morphology,
    RussianJudgmentExtractor,
)
from .semantic_input import (
    ConceptDef,
    SemanticInput,
    SemanticInputParser,
    parse_semantic_input,
)
from .source_provenance import (
    ACTOR_ROLES,
    EXPRESSION_KINDS,
    OWNER_ENDORSEMENTS,
    OWNER_RELATIONS,
    TEXT_ORIGIN_STATUSES,
    ActorRole,
    ExpressionKind,
    ExpressionSpan,
    OwnerEndorsement,
    OwnerRelation,
    SourceAttribution,
    TextOriginStatus,
    source_attribution,
)
from .source_annotations import (
    MAX_OWNER_ANNOTATION_BYTES,
    OWNER_ANNOTATION_DERIVATION,
    OwnerAnnotationOverlay,
    OwnerExpressionAnnotation,
    apply_owner_annotation_overlay,
    load_owner_annotation_overlay,
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
    "ACTOR_ROLES",
    "ConceptDef",
    "DEFAULT_VAULT_EXCLUDE_DIRS",
    "DEFAULT_COORDINATORS",
    "DEFAULT_STOPWORDS_RU_EN",
    "EXPRESSION_KINDS",
    "ParseConfig",
    "JUDGMENT_DERIVATION",
    "JUDGMENT_EVENT_EXTRACTOR",
    "JUDGMENT_EVENT_EXTRACTOR_VERSION",
    "JudgmentCandidate",
    "JudgmentExtractor",
    "LanguageFrontend",
    "MorphAnalysis",
    "Morphology",
    "MAX_OWNER_ANNOTATION_BYTES",
    "OWNER_RELATIONS",
    "OWNER_ENDORSEMENTS",
    "OWNER_ANNOTATION_DERIVATION",
    "OBSIDIAN_VAULT_ADAPTER",
    "Pymorphy3Morphology",
    "RussianJudgmentExtractor",
    "SOURCE_KINDS",
    "SemanticInput",
    "SemanticInputParser",
    "SourceDocument",
    "SourceAttribution",
    "SourceSpan",
    "SourceKind",
    "ExpressionKind",
    "ExpressionSpan",
    "OwnerEndorsement",
    "OwnerAnnotationOverlay",
    "OwnerExpressionAnnotation",
    "ActorRole",
    "OwnerRelation",
    "TextOriginStatus",
    "TEXT_ORIGIN_STATUSES",
    "TELEGRAM_EXPORT_ADAPTER",
    "TelegramExportResult",
    "VaultScan",
    "clean_external_text",
    "apply_owner_annotation_overlay",
    "create_basis_generator",
    "extract_concepts_and_cooccurrence",
    "judgment_to_evidence_event",
    "load_telegram_export",
    "load_owner_annotation_overlay",
    "normalize_markdown",
    "parse_semantic_input",
    "parse_text",
    "scan_vault",
    "source_attribution",
    "split_paragraphs",
    "split_sentences",
    "text_to_semantic_input",
    "tokenize",
]
