from __future__ import annotations

import numpy as np

from core.density_core import Judgment, SemanticSpace
from core.text_parser_agnostic import ParseConfig
from service.retrieval import retrieve_by_query
from service.store import Chunk, SpaceBundle


def _add_component(
    space: SemanticSpace,
    term: str,
    vector: np.ndarray,
    chunk_id: str,
) -> None:
    judgment = Judgment(
        subject=term,
        verb="содержит",
        object=term,
        source_text=chunk_id,
        modality=1.0,
        intensity=1.0,
    )
    space.get_or_create(term).add_component(vector, 1.0, judgment)


def test_semantically_aligned_chunk_is_candidate_without_exact_term() -> None:
    space = SemanticSpace(dim=2, min_components_for_query=1)
    _add_component(space, "свобода", np.array([1.0, 0.0]), "exact")
    _add_component(space, "автономия", np.array([1.0, 0.0]), "semantic")
    _add_component(space, "случайность", np.array([0.0, 1.0]), "unrelated")

    bundle = SpaceBundle(
        name="test",
        space=space,
        chunks={
            "exact": Chunk("exact", "note-a", 0, "Свобода как личная ценность"),
            "semantic": Chunk("semantic", "note-b", 0, "Автономия и самостоятельность"),
            "unrelated": Chunk("unrelated", "note-c", 0, "Случайная заметка"),
        },
    )
    config = ParseConfig(min_freq=1, min_token_len=3, max_concepts=20)

    hits = retrieve_by_query(bundle, "свобода", top_k=3, config=config)
    by_id = {hit["chunk_id"]: hit for hit in hits}

    assert "semantic" in by_id
    assert by_id["semantic"]["score"] > by_id["unrelated"]["score"]
    assert "автономия" in by_id["semantic"]["matched_concepts"]


def test_unknown_query_terms_do_not_produce_random_results() -> None:
    space = SemanticSpace(dim=2, min_components_for_query=1)
    _add_component(space, "свобода", np.array([1.0, 0.0]), "known")
    bundle = SpaceBundle(
        name="test",
        space=space,
        chunks={"known": Chunk("known", "note", 0, "Известная заметка")},
    )
    config = ParseConfig(min_freq=1, min_token_len=3, max_concepts=20)

    assert retrieve_by_query(bundle, "несуществующийтермин", config=config) == []
