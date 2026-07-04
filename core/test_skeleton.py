# -*- coding: utf-8 -*-
"""Skeleton layer: index + seeding contract.

Verifies the first cascade layer wiring: ConceptNet edges become low-modality
judgments seeded ONLY for terms the person has personally touched, with
idempotency and hub capping.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from density_core import SemanticSpace, Judgment  # noqa: E402
from skeleton import SkeletonIndex, seed_skeleton, has_skeleton  # noqa: E402

DIM = 32


def _make_cache(tmp_path, edges):
    p = tmp_path / "conceptnet_test.json"
    p.write_text(json.dumps(edges, ensure_ascii=False), encoding="utf-8")
    return str(p)


def _space_with(*terms):
    """Space where each term has one personal judgment."""
    s = SemanticSpace(dim=DIM)
    for t in terms:
        s.materialize_judgment(Judgment(
            subject=t, verb="упоминается", object="запись",
            source_text="note.md",
        ))
    return s


EDGES = [
    {"rel": "IsA", "start": "свобода", "end": "ценность", "weight": 2.0},
    {"rel": "Synonym", "start": "свобода", "end": "воля", "weight": 2.0},
    {"rel": "RelatedTo", "start": "свобода", "end": "птица", "weight": 1.0},
    {"rel": "IsA", "start": "код", "end": "текст", "weight": 2.0},
    {"rel": "Antonym", "start": "свобода", "end": "рабство", "weight": 2.0},
]


def test_index_builds_and_covers(tmp_path):
    idx = SkeletonIndex.from_conceptnet(_make_cache(tmp_path, EDGES))
    assert len(idx) == 5
    assert idx.covers("свобода")
    assert idx.covers("ценность")      # object side is indexed too
    assert not idx.covers("несуществующее")
    assert len(idx.for_term("свобода")) == 4


def test_missing_cache_is_empty_index(tmp_path):
    idx = SkeletonIndex.from_conceptnet(str(tmp_path / "nope.json"))
    assert len(idx) == 0
    assert idx.for_term("свобода") == []


def test_seed_only_existing_terms(tmp_path):
    """Skeleton never introduces terms the person hasn't touched."""
    idx = SkeletonIndex.from_conceptnet(_make_cache(tmp_path, EDGES))
    s = _space_with("свобода")          # only свобода is personal
    n = seed_skeleton(s, idx)
    assert n == 4                        # only свобода's edges; "код" untouched
    assert "код" not in s.concepts or not has_skeleton(s, "код")

    concept = s.concepts["свобода"]
    thes = [c for c in concept.components
            if c.judgment.source_text.startswith("[thesaurus:")]
    assert len(thes) > 0
    # Low modality: personal statements must dominate
    assert all(c.judgment.modality <= 0.5 for c in thes)


def test_seed_is_idempotent(tmp_path):
    idx = SkeletonIndex.from_conceptnet(_make_cache(tmp_path, EDGES))
    s = _space_with("свобода")
    n1 = seed_skeleton(s, idx)
    n2 = seed_skeleton(s, idx)
    assert n1 > 0
    assert n2 == 0, "second seed must be a no-op for already-seeded terms"


def test_max_per_term_prefers_high_intensity(tmp_path):
    """Hub capping: IsA/Synonym must beat RelatedTo noise."""
    idx = SkeletonIndex.from_conceptnet(_make_cache(tmp_path, EDGES))
    s = _space_with("свобода")
    seed_skeleton(s, idx, max_per_term=2)

    concept = s.concepts["свобода"]
    verbs = {c.judgment.verb for c in concept.components
             if c.judgment.source_text.startswith("[thesaurus:")}
    # RelatedTo ("связан_с", intensity 0.4*0.5=0.2) must be cut first
    assert "связан_с" not in verbs


def test_personal_component_flag_survives_seeding(tmp_path):
    """recursive_deepen targets only personal concepts — seeding must not
    turn a personal concept into a thesaurus-only one."""
    idx = SkeletonIndex.from_conceptnet(_make_cache(tmp_path, EDGES))
    s = _space_with("свобода")
    seed_skeleton(s, idx)
    concept = s.concepts["свобода"]
    has_personal = any(
        not c.archived and not c.judgment.source_text.startswith("[thesaurus:")
        for c in concept.components
    )
    assert has_personal


def test_explicit_terms_subset(tmp_path):
    idx = SkeletonIndex.from_conceptnet(_make_cache(tmp_path, EDGES))
    s = _space_with("свобода", "код")
    n = seed_skeleton(s, idx, terms={"код"})
    assert n == 1                        # only код→текст
    assert has_skeleton(s, "код")
    assert not has_skeleton(s, "свобода")
