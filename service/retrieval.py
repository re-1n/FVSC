"""Retrieval: query → concepts → chunk_ids → scored chunks."""

from __future__ import annotations

from collections import defaultdict
from typing import List

from core.text_parser_agnostic import text_to_semantic_input, ParseConfig

from .store import SpaceBundle


def retrieve_by_query(
    bundle: SpaceBundle,
    query: str,
    top_k: int = 5,
    config: ParseConfig | None = None,
) -> list[dict]:
    """Given a free-text query, return top-k chunks ranked by FVSC containment.

    Process:
    1. Parse the query into a semantic_input dict (same parser as ingest).
    2. For each concept in the query, look up in the space and collect
       chunk_ids from every Component's judgment.source_text.
    3. Weight each chunk by containment(ρ_concept, ρ_chunk_concept) summed
       over all query concepts.
    4. Return top-k chunks with scores and matched concepts.
    """
    if not bundle.space.concepts or not bundle.chunks:
        return []

    # Parse query into concepts
    si = text_to_semantic_input(query, config=config)
    if not si:
        return []

    # Collect chunk candidates with scores
    # score[chunk_id][concept] = accumulated containment weight
    chunk_scores: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for q_concept, q_spec in si.items():
        conc = bundle.space.concepts.get(q_concept)
        if conc is None:
            continue
        q_rho = conc.rho_deep_norm
        if q_rho is None:
            continue

        for child, child_weight in q_spec.get("contains", {}).items():
            child_conc = bundle.space.concepts.get(child)
            if child_conc is None:
                continue
            child_rho = child_conc.rho_deep_norm
            if child_rho is None:
                continue
            # Collect chunk_ids from components of the child concept
            for comp in child_conc.components:
                if comp.archived:
                    continue
                st = comp.judgment.source_text
                if st in bundle.chunks:
                    chunk_scores[st][q_concept] += child_weight * comp.weight

        # Also check self-components of the query concept
        for comp in conc.components:
            if comp.archived:
                continue
            st = comp.judgment.source_text
            if st in bundle.chunks:
                chunk_scores[st][q_concept] += comp.weight

    # Aggregate: for each chunk, sum its matched concept scores
    hits = []
    for chunk_id, concept_weights in chunk_scores.items():
        ch = bundle.chunks.get(chunk_id)
        if ch is None:
            continue
        score = sum(concept_weights.values())
        matched = sorted(concept_weights, key=concept_weights.get, reverse=True)
        hits.append({
            "chunk_id": chunk_id,
            "source_id": ch.source_id,
            "text": ch.text,
            "score": round(score, 4),
            "matched_concepts": matched,
        })

    hits.sort(key=lambda h: -h["score"])
    return hits[:top_k]
