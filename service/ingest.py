"""Ingest pipeline: raw text → chunks → FVSC semantic_input → SemanticSpace."""

from __future__ import annotations

import re
import time
from typing import Dict, List, Optional, Tuple

from core.density_core import SemanticSpace
from core.exocortex_ingest import _clean_for_fvsc, _RU_STOPWORDS
from core.text_parser_agnostic import text_to_semantic_input, ParseConfig
from core.vault_ingest import strip_markdown

from .store import Chunk, SpaceBundle


# ── chunking ──────────────────────────────────────────────────────

_PARA_RE = re.compile(r"\n\s*\n")
_WS_RUNS = re.compile(r"\s+")


def _split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in _PARA_RE.split(text) if p.strip() and len(p.strip()) >= 20]


def _chunkify(text: str, source_id: str) -> List[Chunk]:
    paragraphs = _split_paragraphs(text)
    chunks = []
    for idx, para in enumerate(paragraphs):
        chunk_id = f"{source_id}:{idx}"
        chunks.append(Chunk(chunk_id=chunk_id, source_id=source_id, idx=idx, text=para))
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
    """
    # Preprocess
    cleaned = text
    if fmt == "md":
        cleaned = strip_markdown(cleaned)
    cleaned = _clean_for_fvsc(cleaned)

    # Chunk
    chunks = _chunkify(cleaned, source_id)
    if not chunks:
        return bundle, 0, len(bundle.space.concepts)

    concepts_before = len(bundle.space.concepts)

    # Parse each chunk individually and load into space with chunk_id as source_text
    for chunk in chunks:
        si = text_to_semantic_input(chunk.text, config=config)
        if not si:
            continue
        bundle.space.load_from_semantic_input(si, source_text=chunk.chunk_id)
        bundle.chunks[chunk.chunk_id] = chunk

    return bundle, len(chunks), concepts_before
