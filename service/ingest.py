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


def _purge_existing_source(bundle: SpaceBundle, source_id: str) -> int:
    """Remove all previously indexed chunks and semantic mass for a source."""
    old_chunk_ids = [
        chunk_id
        for chunk_id, chunk in bundle.chunks.items()
        if chunk.source_id == source_id
    ]
    purged = 0
    for chunk_id in old_chunk_ids:
        purged += bundle.space.purge_source(chunk_id)
        del bundle.chunks[chunk_id]
    return purged


# ── core ingest ───────────────────────────────────────────────────

def ingest_text(
    bundle: SpaceBundle,
    text: str,
    source_id: str,
    fmt: str = "plain",
    config: Optional[ParseConfig] = None,
) -> Tuple[SpaceBundle, int, int]:
    """Replace one source's indexed representation in a SpaceBundle.

    Re-ingesting the same ``source_id`` first purges all previous chunks and
    their density components. This keeps retrieval and concept provenance in
    sync when a document shrinks, changes structure, or becomes empty.

    Returns ``(bundle, chunks_added, concepts_before)``. ``chunks_added`` counts
    only chunks that produced a non-empty semantic input.
    """
    concepts_before = len(bundle.space.concepts)
    _purge_existing_source(bundle, source_id)

    if fmt == "md":
        chunk_texts = parse_markdown_to_chunks(text)
    else:
        cleaned = _clean_for_fvsc(text)
        chunk_texts = _split_paragraphs(cleaned)

    chunks = _chunkify(chunk_texts, source_id)
    added = 0
    for chunk in chunks:
        semantic_input = text_to_semantic_input(chunk.text, config=config)
        if not semantic_input:
            continue
        bundle.space.load_from_semantic_input(semantic_input, source_text=chunk.chunk_id)
        bundle.chunks[chunk.chunk_id] = chunk
        added += 1

    return bundle, added, concepts_before
