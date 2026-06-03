"""Quantum retrieval: query → ρ_query → Tr(ρ_query · ρ_chunk) → ranked chunks.

Uses the core FVSC operation — trace inner product between density matrices —
not keyword matching. The query becomes a density matrix, each chunk becomes
a density matrix (reconstructed from its contributions to the SemanticSpace),
and the score is the quantum semantic overlap: Tr(ρ_query·ρ_chunk).
"""

from __future__ import annotations

import numpy as np
from collections import defaultdict
from typing import Dict, List

from core.density_core import trace_inner_product
from core.text_parser_agnostic import text_to_semantic_input, ParseConfig

from .store import SpaceBundle


def retrieve_by_query(
    bundle: SpaceBundle,
    query: str,
    top_k: int = 5,
    config: ParseConfig | None = None,
) -> list[dict]:
    """Quantum retrieval: Tr(ρ_query · ρ_chunk) for every chunk.

    1. Parse query into concepts, build ρ_query from their basis vectors.
    2. For each candidate chunk, reconstruct ρ_chunk from the components
       that were contributed by that chunk (tracked via source_text).
    3. Score = Tr(ρ_query_norm · ρ_chunk_norm).
    4. Return top-k chunks with scores and matched concepts.
    """
    space = bundle.space
    if not space.concepts or not bundle.chunks:
        return []

    si = text_to_semantic_input(query, config=config)
    if not si:
        return []

    # ── Build ρ_query ──────────────────────────────────────────
    # Use the space's basis generator for consistent vector identities
    q_dim = space.dim
    rho_query = np.zeros((q_dim, q_dim))
    q_weight_sum = 0.0
    q_matched: Dict[str, float] = {}  # query concept → weight in ρ_query

    for q_concept, q_spec in si.items():
        q_vec = space.get_term_vector(q_concept)
        q_weight = q_spec.get("weight", 1.0)
        rho_query += q_weight * np.outer(q_vec, q_vec)
        q_weight_sum += q_weight
        q_matched[q_concept] = q_weight

        # Also include query's contained children with their weights
        for child, child_weight in q_spec.get("contains", {}).items():
            child_vec = space.get_term_vector(child)
            rho_query += child_weight * np.outer(child_vec, child_vec)
            q_weight_sum += child_weight

    if q_weight_sum < 1e-12:
        return []
    rho_query /= q_weight_sum  # normalize

    # ── Collect candidate chunks ───────────────────────────────
    # For each query concept, find which chunks contributed components
    candidate_chunks: set[str] = set()
    for q_concept in q_matched:
        conc = space.concepts.get(q_concept)
        if conc is None:
            continue
        for comp in conc.components:
            if not comp.archived and comp.judgment.source_text in bundle.chunks:
                candidate_chunks.add(comp.judgment.source_text)

    if not candidate_chunks:
        return []

    # ── Build per-chunk ρ and score ────────────────────────────
    # Reconstruct ρ_chunk from only components contributed by that chunk
    hits = []
    for chunk_id in candidate_chunks:
        rho_chunk = np.zeros((q_dim, q_dim))
        ch_weight_sum = 0.0

        for concept in space.concepts.values():
            for comp in concept.components:
                if comp.archived:
                    continue
                if comp.judgment.source_text != chunk_id:
                    continue
                rho_chunk += comp.weight * np.outer(comp.vector, comp.vector)
                ch_weight_sum += comp.weight

        if ch_weight_sum < 1e-12:
            continue
        rho_chunk /= ch_weight_sum

        score = trace_inner_product(rho_query, rho_chunk)

        ch = bundle.chunks[chunk_id]
        # Which query concepts matched this chunk?
        matched = []
        for qc in q_matched:
            conc = space.concepts.get(qc)
            if conc is None:
                continue
            for comp in conc.components:
                if comp.judgment.source_text == chunk_id:
                    matched.append(qc)
                    break

        hits.append({
            "chunk_id": chunk_id,
            "source_id": ch.source_id,
            "text": ch.text,
            "score": round(float(score), 4),
            "matched_concepts": matched,
        })

    hits.sort(key=lambda h: -h["score"])
    return hits[:top_k]
