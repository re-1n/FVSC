from __future__ import annotations

import pytest

from fvsc.retrieval import reciprocal_rank_fusion


def test_reciprocal_rank_fusion_retains_channel_ranks_and_is_deterministic() -> None:
    rankings = {
        "lexical": ("a", "b", "c"),
        "judgment": ("b", "d", "a"),
    }

    first = reciprocal_rank_fusion(rankings, rank_constant=10, top_k=4)
    second = reciprocal_rank_fusion(dict(reversed(tuple(rankings.items()))), rank_constant=10, top_k=4)

    assert first == second
    assert first[0].source_id == "b"
    assert first[0].channel_ranks == (("judgment", 1), ("lexical", 2))
    assert 0.0 < first[0].score <= 1.0


def test_weight_can_keep_a_validated_floor_dominant() -> None:
    hits = reciprocal_rank_fusion(
        {"lexical": ("gold", "other"), "experimental": ("other", "gold")},
        weights={"lexical": 3.0, "experimental": 1.0},
        rank_constant=0,
    )

    assert hits[0].source_id == "gold"


def test_fusion_rejects_duplicates_unknown_weights_and_invalid_limits() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        reciprocal_rank_fusion({"a": ("x", "x")})
    with pytest.raises(ValueError, match="unknown channels"):
        reciprocal_rank_fusion({"a": ("x",)}, weights={"b": 1.0})
    with pytest.raises(ValueError, match="rank_constant"):
        reciprocal_rank_fusion({"a": ("x",)}, rank_constant=-1)
