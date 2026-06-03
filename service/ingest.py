"""Ingest pipeline: raw text → chunks → FVSC semantic_input → SemanticSpace."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from core.exocortex_ingest import _clean_for_fvsc
from core.text_parser_agnostic import text_to_semantic_input, ParseConfig

from .format_adapter import parse_markdown_to_chunks
from .store import Chunk, SpaceBundle


# ── chunking ──────────────────────────────────────────────────────

_PARA_RE = re.compile(r"\n\s*\n")


def _split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in _PARA_RE.split(text) if p.strip() and len(p.strip()) >= 20]


def _chunkify(texts: List[str], source_id: str) -> List[Chunk]:
    chunks = []
    for idx, text in enumerate(texts):
        chunk_id = f"{source_id}:{idx}"
        chunks.append(Chunk(chunk_id=chunk_id, source_id=source_id, idx=idx, text=text))
    return chunks


# ── core ingest ───────────────────────────────────────────────────

def ingest_text(
    bundle: SpaceBundle,
    text: str,
    source_id: str,
    fmt: str = "plain",
    config: Optional[ParseConfig] = None,
) -> Tuple[SpaceBundle, int, int]:
    """Ingest raw text into a SpaceBundle. Mutates and returns it.

    Returns (bundle, chunks_added, concepts_before).

    fmt="md":    Uses mistune AST to extract structured chunks from Markdown.
                 Tables become row-sentences that preserve column relationships.
                 Headings prepend section context to subsequent paragraphs.
                 Code blocks, HTML, and formatting syntax are stripped.

    fmt="plain": Basic cleaning + paragraph-level splitting. No structural
                 extraction. Suitable for all non-Markdown text.
    """
    if fmt == "md":
        # Structured extraction via AST — table rows, heading context, etc.
        chunk_texts = parse_markdown_to_chunks(text)
    else:
        # Plain text: clean noise, split into paragraphs
        cleaned = _clean_for_fvsc(text)
        chunk_texts = _split_paragraphs(cleaned)

    chunks = _chunkify(chunk_texts, source_id)
    if not chunks:
        return bundle, 0, len(bundle.space.concepts)

    concepts_before = len(bundle.space.concepts)

    for chunk in chunks:
        si = text_to_semantic_input(chunk.text, config=config)
        if not si:
            continue
        bundle.space.load_from_semantic_input(si, source_text=chunk.chunk_id)
        bundle.chunks[chunk.chunk_id] = chunk

    return bundle, len(chunks), concepts_before
