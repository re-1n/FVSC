"""Density-matrix retrieval over ingested chunks.

A query is projected into the user's existing semantic space. Every chunk with
active components is then scored by normalized trace overlap; candidate
selection does not require an exact query-token occurrence in that chunk.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict

import numpy as np

from core.text_parser_agnostic import ParseConfig, text_to_semantic_input

from .store import SpaceBundle


def retrieve_by_query(
    bundle: SpaceBundle,
    query: str,
    top_k: int = 5,
    config: ParseConfig | None = None,
) -> list[dict]:
    """Rank chunks by overlap with a query density matrix.

    Query terms that already exist in the map contribute their normalized
    personal density matrices. Unknown terms are ignored rather than mapped to
    arbitrary random basis vectors. Chunk scores include component decay and
    consolidation activation counts.
    """
    space = bundle.space
    if not space.concepts or not bundle.chunks or top_k < 1:
        return []

    semantic_input = text_to_semantic_input(query, config=config)
    if not semantic_input:
        return []

    rho_query = np.zeros((space.dim, space.dim))
    query_mass = 0.0
    query_terms: Dict[str, float] = {}

    def add_query_term(term: str, weight: float) -> None:
        nonlocal query_mass
        concept = space.concepts.get(term)
        rho = concept.rho_deep_norm if concept is not None else None
        if rho is None or weight <= 0:
            return
        rho_query[:] += weight * rho
        query_mass += weight
        query_terms[term] = query_terms.get(term, 0.0) + weight

    for term, spec in semantic_input.items():
        add_query_term(term, float(spec.get("weight", 1.0)))
        for child, child_weight in spec.get("contains", {}).items():
            add_query_term(child, float(child_weight))

    if query_mass < 1e-12:
        return []
    rho_query /= query_mass

    # A normalized chunk density is Σ w|v><v| / Σw. Therefore its trace
    # overlap with rho_query can be accumulated component-by-component as
    # Σ w(vᵀ rho_query v) / Σw, avoiding a dense matrix per chunk.
    now = time.time()
    score_numerator: dict[str, float] = defaultdict(float)
    chunk_mass: dict[str, float] = defaultdict(float)
    term_contribution: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for term, concept in space.concepts.items():
        for component in concept.components:
            chunk_id = component.judgment.source_text
            if component.archived or chunk_id not in bundle.chunks:
                continue
            weight = concept._decayed_weight(component, now)
            if weight <= 0:
                continue
            vector = component.vector
            overlap = float(vector @ rho_query @ vector)
            contribution = weight * max(0.0, overlap)
            score_numerator[chunk_id] += contribution
            chunk_mass[chunk_id] += weight
            term_contribution[chunk_id][term] += contribution

    hits = []
    for chunk_id, mass in chunk_mass.items():
        if mass < 1e-12:
            continue
        score = score_numerator[chunk_id] / mass
        chunk = bundle.chunks[chunk_id]
        matched = [
            term
            for term, contribution in sorted(
                term_contribution[chunk_id].items(),
                key=lambda item: (-item[1], item[0]),
            )
            if contribution > 0
        ][:5]
        hits.append({
            "chunk_id": chunk_id,
            "source_id": chunk.source_id,
            "text": chunk.text,
            "score": round(float(score), 4),
            "matched_concepts": matched,
        })

    hits.sort(key=lambda hit: (-hit["score"], hit["chunk_id"]))
    return hits[:top_k]
