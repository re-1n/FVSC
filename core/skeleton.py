# -*- coding: utf-8 -*-
"""
Skeleton layer — on-demand seeding of thesaurus judgments into a space.

The cascade's FIRST layer. ThesaurusLoader can convert ConceptNet edges to
Judgments, but load_for_terms() re-reads the whole JSON per call, which is
why nothing ever called it. SkeletonIndex loads once and indexes by term,
so seeding after each ingest is cheap.

Design decisions:
- Seed ONLY terms that already exist in the space (personal vocabulary
  drives the skeleton, never the other way around — stenographic principle:
  the skeleton supports what was said, it does not add what wasn't).
- Low modality (0.3, set by the loader) keeps personal statements dominant.
- Idempotency: a term that already has thesaurus components is skipped.
  Exact duplicates that slip through (seeding term B re-adding an A→B edge)
  are absorbed by consolidation (identical judgment → identical vectors →
  activation_count++, no component bloat).
- max_per_term caps hub terms (RelatedTo explosion): highest-intensity
  edges win, so IsA/Synonym beat RelatedTo.

Usage:
    index = SkeletonIndex.from_conceptnet("data/conceptnet_ru.json")
    added = seed_skeleton(space, index, terms={"свобода", "код"})
"""

from typing import Iterable, Optional

try:
    from .density_core import Judgment, SemanticSpace
    from .thesaurus_loader import load_conceptnet_judgments
except ImportError:
    from density_core import Judgment, SemanticSpace
    from thesaurus_loader import load_conceptnet_judgments

THESAURUS_SOURCE_PREFIX = "[thesaurus:"


class SkeletonIndex:
    """term → thesaurus judgments, built once per process."""

    def __init__(self, judgments: Iterable[Judgment]):
        self._by_term: dict[str, list[Judgment]] = {}
        n = 0
        for j in judgments:
            self._by_term.setdefault(j.subject, []).append(j)
            if j.object != j.subject:
                self._by_term.setdefault(j.object, []).append(j)
            n += 1
        self._total = n

    @classmethod
    def from_conceptnet(cls, cache_path: str,
                        min_weight: float = 1.0) -> "SkeletonIndex":
        """Build from the pre-filtered ConceptNet RU JSON cache.
        Missing file yields an empty (but valid) index.
        """
        return cls(load_conceptnet_judgments(cache_path, min_weight=min_weight))

    def for_term(self, term: str) -> list[Judgment]:
        return self._by_term.get(term.lower().strip(), [])

    def covers(self, term: str) -> bool:
        return term.lower().strip() in self._by_term

    def __len__(self) -> int:
        return self._total


def has_skeleton(space: SemanticSpace, term: str) -> bool:
    """Does this term's concept already carry thesaurus components?"""
    concept = space.concepts.get(term)
    if concept is None:
        return False
    return any(
        c.judgment.source_text.startswith(THESAURUS_SOURCE_PREFIX)
        for c in concept.components
    )


def seed_skeleton(space: SemanticSpace,
                  index: SkeletonIndex,
                  terms: Optional[Iterable[str]] = None,
                  max_per_term: int = 12) -> int:
    """Materialize skeleton judgments for the given terms (default: all
    concepts currently in the space). Returns number of judgments applied.

    Only terms already present in the space are seeded — the skeleton
    never introduces subjects the person hasn't touched. Terms that
    already have thesaurus components are skipped (idempotent).
    """
    if terms is None:
        candidates = list(space.concepts.keys())
    else:
        candidates = [t for t in terms if t in space.concepts]

    applied = 0
    for term in candidates:
        if has_skeleton(space, term):
            continue
        edges = index.for_term(term)
        if not edges:
            continue
        # Highest-intensity edges first: IsA/Synonym beat RelatedTo noise
        edges = sorted(edges, key=lambda j: -j.intensity)[:max_per_term]
        for j in edges:
            space.materialize_judgment(j)
            applied += 1
    return applied
