# -*- coding: utf-8 -*-
"""
Thesaurus Prior — weak structural prior for the agnostic parser.

Builds a fast set of (a, b) pairs that are related according to external
knowledge bases (ConceptNet, RuWordNet). The parser uses this to weight
co-occurrence pairs:
  - pair confirmed by thesaurus → keep at full weight
  - pair NOT in thesaurus → downweight (possible noise from short window)

This is a SOFT prior, not a hard filter — personal co-occurrence remains
the primary signal. The prior just helps precision in noisy short texts.

Usage:
    prior = ThesaurusPrior.from_conceptnet("data/conceptnet_ru.json")
    weight = prior.score("свобода", "ответственность")  # 1.0 if known, else 0.0
"""

from __future__ import annotations
import json
import os
from typing import Optional


# Relations to include in the prior (skip pure derivational and weak ones)
_DEFAULT_RELATIONS = frozenset({
    "IsA", "PartOf", "HasA", "UsedFor", "CapableOf", "HasProperty",
    "MadeOf", "Causes", "CreatedBy", "DefinedAs", "Synonym",
    "AtLocation", "RelatedTo", "SimilarTo", "Desires",
    "HasSubevent", "HasPrerequisite", "CausesDesire",
    "Antonym",  # antonyms still indicate semantic relatedness
})


class ThesaurusPrior:
    """A symmetric (A, B) → relatedness lookup built from thesaurus edges."""

    def __init__(self):
        self._pairs: set[tuple[str, str]] = set()
        self._lemmas: set[str] = set()

    @classmethod
    def from_conceptnet(cls, cache_path: str,
                        min_weight: float = 1.0,
                        relations: Optional[frozenset[str]] = None) -> "ThesaurusPrior":
        """Load from pre-filtered ConceptNet RU JSON cache.

        Cache format: [{"rel": str, "start": str, "end": str, "weight": float}, ...]
        """
        prior = cls()
        if not os.path.exists(cache_path):
            return prior

        rels = relations or _DEFAULT_RELATIONS
        with open(cache_path, encoding="utf-8") as f:
            edges = json.load(f)

        for edge in edges:
            if edge["rel"] not in rels:
                continue
            if edge.get("weight", 1.0) < min_weight:
                continue
            a = edge["start"].lower().strip()
            b = edge["end"].lower().strip()
            if not a or not b or a == b:
                continue
            # Store symmetric — relatedness is undirected at this layer
            prior._pairs.add((a, b))
            prior._pairs.add((b, a))
            prior._lemmas.add(a)
            prior._lemmas.add(b)

        return prior

    def score(self, a: str, b: str) -> float:
        """1.0 if pair is in thesaurus, else 0.0.
        Both terms lowercased before lookup.
        """
        a = a.lower().strip()
        b = b.lower().strip()
        return 1.0 if (a, b) in self._pairs else 0.0

    def score_prefix(self, a: str, b: str, prefix_len: int = 4) -> float:
        """Like score() but matches by 4-char prefix to handle morphology.
        Returns 1.0 if any (a', b') in pairs with matching prefixes.
        """
        a = a.lower().strip()[:prefix_len]
        b = b.lower().strip()[:prefix_len]
        if not a or not b:
            return 0.0
        # Only check if both terms are at least known by prefix
        for known in self._lemmas:
            if known.startswith(a):
                for (ka, kb) in self._pairs:
                    if ka == known and kb.startswith(b):
                        return 1.0
        return 0.0

    def __len__(self) -> int:
        return len(self._pairs) // 2  # undirected pair count

    def __contains__(self, pair) -> bool:
        a, b = pair
        return (a.lower(), b.lower()) in self._pairs

    def covers(self, term: str) -> bool:
        """Is this term known to the thesaurus at all?"""
        return term.lower() in self._lemmas
