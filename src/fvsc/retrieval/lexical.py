"""Small Unicode character-TF-IDF baseline with structural context expansion.

This module is deliberately not presented as FVSC semantics. It is the minimum
retrieval baseline that a semantic layer must beat while retaining exact source
provenance. It operates on transient ``SourceDocument`` text and stores nothing.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import math
import re
from typing import Iterable
import unicodedata

from ..ingest.vault_ingest import SourceDocument


_WORD_RE = re.compile(r"\w+", flags=re.UNICODE)


@dataclass(frozen=True)
class LexicalHit:
    source_id: str
    score: float
    document: SourceDocument

    def __post_init__(self) -> None:
        if self.source_id != self.document.source_id:
            raise ValueError("lexical hit source_id must match its document")
        if not math.isfinite(self.score) or not 0.0 <= self.score <= 1.0 + 1e-12:
            raise ValueError("lexical hit score must be finite and in [0, 1]")


def _character_ngrams(text: str, *, minimum: int, maximum: int) -> Counter[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    grams: Counter[str] = Counter()
    for word in _WORD_RE.findall(normalized):
        padded = f" {word} "
        for size in range(minimum, maximum + 1):
            if len(padded) < size:
                continue
            grams.update(padded[index : index + size] for index in range(len(padded) - size + 1))
    return grams


def _tfidf(
    counts: Counter[str],
    *,
    document_frequency: Counter[str],
    document_count: int,
) -> dict[str, float]:
    return {
        gram: (1.0 + math.log(frequency))
        * (math.log((1.0 + document_count) / (1.0 + document_frequency[gram])) + 1.0)
        for gram, frequency in counts.items()
    }


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    dot = sum(value * right.get(key, 0.0) for key, value in left.items())
    return min(max(dot / (left_norm * right_norm), 0.0), 1.0)


def search_documents(
    documents: Iterable[SourceDocument],
    query: str,
    *,
    top_k: int = 10,
    ngram_min: int = 3,
    ngram_max: int = 5,
    owner_adopted_only: bool = False,
) -> tuple[LexicalHit, ...]:
    """Rank source documents using a dependency-free character TF-IDF baseline."""
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    if (
        isinstance(ngram_min, bool)
        or isinstance(ngram_max, bool)
        or not isinstance(ngram_min, int)
        or not isinstance(ngram_max, int)
        or ngram_min <= 0
        or ngram_max < ngram_min
    ):
        raise ValueError("ngram range must contain positive ordered integers")
    query_value = str(query).strip()
    if not query_value:
        return ()

    ordered = tuple(sorted(documents, key=lambda document: document.source_id))
    source_ids = tuple(document.source_id for document in ordered)
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("source documents must have unique source ids")
    candidates = tuple(
        document
        for document in ordered
        if document.text
        and (
            not owner_adopted_only
            or document.metadata.get("owner_adopted_expression") is True
        )
    )
    if not candidates:
        return ()

    document_counts = [
        _character_ngrams(document.text, minimum=ngram_min, maximum=ngram_max)
        for document in candidates
    ]
    query_counts = _character_ngrams(query_value, minimum=ngram_min, maximum=ngram_max)
    if not query_counts:
        return ()
    document_frequency: Counter[str] = Counter()
    for counts in document_counts:
        document_frequency.update(counts.keys())
    document_count = len(candidates)
    query_vector = _tfidf(
        query_counts,
        document_frequency=document_frequency,
        document_count=document_count,
    )

    hits: list[LexicalHit] = []
    for document, counts in zip(candidates, document_counts, strict=True):
        vector = _tfidf(
            counts,
            document_frequency=document_frequency,
            document_count=document_count,
        )
        score = _cosine(vector, query_vector)
        if score > 0.0:
            hits.append(LexicalHit(source_id=document.source_id, score=score, document=document))
    hits.sort(key=lambda hit: (-hit.score, hit.source_id))
    return tuple(hits[:top_k])


def expand_source_context(
    documents: Iterable[SourceDocument],
    source_id: str,
    *,
    max_depth: int = 1,
    include_temporal: bool = True,
) -> tuple[SourceDocument, ...]:
    """Expand one source through reply edges and optional short-gap context."""
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 0:
        raise ValueError("max_depth must be a non-negative integer")
    ordered = tuple(sorted(documents, key=lambda document: document.source_id))
    by_id = {document.source_id: document for document in ordered}
    if len(by_id) != len(ordered):
        raise ValueError("source documents must have unique source ids")
    root = str(source_id).strip()
    if root not in by_id:
        raise KeyError(root)

    adjacency: dict[str, set[str]] = {key: set() for key in by_id}
    for document in ordered:
        metadata = document.metadata
        reply_target = metadata.get("reply_to_source_id")
        if isinstance(reply_target, str) and reply_target in by_id:
            adjacency[document.source_id].add(reply_target)
            adjacency[reply_target].add(document.source_id)
        if include_temporal:
            temporal = metadata.get("temporal_context")
            if isinstance(temporal, dict):
                previous = temporal.get("previous_source_id")
                if isinstance(previous, str) and previous in by_id:
                    adjacency[document.source_id].add(previous)
                    adjacency[previous].add(document.source_id)

    distance = {root: 0}
    queue = deque([root])
    while queue:
        current = queue.popleft()
        if distance[current] >= max_depth:
            continue
        for neighbor in sorted(adjacency[current]):
            if neighbor not in distance:
                distance[neighbor] = distance[current] + 1
                queue.append(neighbor)
    return tuple(
        sorted(
            (by_id[key] for key in distance),
            key=lambda document: (document.observed_at, document.source_id),
        )
    )


__all__ = ["LexicalHit", "expand_source_context", "search_documents"]
