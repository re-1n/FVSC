"""Deterministic rank fusion for independent source-cited retrievers."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence


@dataclass(frozen=True)
class FusedHit:
    source_id: str
    score: float
    channel_ranks: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if not str(self.source_id).strip():
            raise ValueError("fused hit source_id must not be empty")
        if not math.isfinite(self.score) or not 0.0 <= self.score <= 1.0 + 1e-12:
            raise ValueError("fused hit score must be finite and in [0, 1]")


def reciprocal_rank_fusion(
    rankings: Mapping[str, Sequence[str]],
    *,
    weights: Mapping[str, float] | None = None,
    rank_constant: int = 60,
    top_k: int = 10,
) -> tuple[FusedHit, ...]:
    """Fuse ranked source ids while retaining each channel's exact rank."""
    if isinstance(rank_constant, bool) or not isinstance(rank_constant, int) or rank_constant < 0:
        raise ValueError("rank_constant must be a non-negative integer")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    channels = tuple(sorted(str(name).strip() for name in rankings))
    if not channels or any(not name for name in channels):
        return ()
    provided = dict(weights or {})
    unknown = set(provided) - set(channels)
    if unknown:
        raise ValueError(f"weights reference unknown channels: {sorted(unknown)}")
    channel_weights: dict[str, float] = {}
    for channel in channels:
        weight = float(provided.get(channel, 1.0))
        if not math.isfinite(weight) or weight < 0.0:
            raise ValueError("fusion weights must be finite and non-negative")
        channel_weights[channel] = weight
    maximum = math.fsum(
        weight / (rank_constant + 1)
        for weight in channel_weights.values()
        if weight > 0.0
    )
    if maximum <= 0.0:
        return ()

    scores: dict[str, float] = {}
    ranks: dict[str, list[tuple[str, int]]] = {}
    for channel in channels:
        source_ids = tuple(str(value).strip() for value in rankings[channel])
        if any(not value for value in source_ids):
            raise ValueError("ranked source ids must not be empty")
        if len(source_ids) != len(set(source_ids)):
            raise ValueError(f"channel {channel!r} contains duplicate source ids")
        weight = channel_weights[channel]
        for rank, source_id in enumerate(source_ids, start=1):
            scores[source_id] = scores.get(source_id, 0.0) + weight / (
                rank_constant + rank
            )
            ranks.setdefault(source_id, []).append((channel, rank))

    hits = [
        FusedHit(
            source_id=source_id,
            score=min(max(score / maximum, 0.0), 1.0),
            channel_ranks=tuple(sorted(ranks[source_id])),
        )
        for source_id, score in scores.items()
    ]
    hits.sort(key=lambda item: (-item.score, item.source_id))
    return tuple(hits[:top_k])


__all__ = ["FusedHit", "reciprocal_rank_fusion"]
