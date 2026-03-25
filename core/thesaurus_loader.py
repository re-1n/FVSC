# -*- coding: utf-8 -*-
"""
FVSC Thesaurus Loader — loads structured semantic relations from external
knowledge bases (ConceptNet, RuWordNet) and converts them to Judgment objects.

Thesaurus judgments form the BASE layer of density matrices:
- Low modality (0.3) so personal statements dominate
- source_text marks provenance: "[thesaurus:conceptnet]" or "[thesaurus:ruwordnet]"
- Loaded BEFORE personal judgments into SemanticSpace

Two sources:
  1. ConceptNet 5.7 (Russian subset) — common-sense: IsA, HasProperty, UsedFor, etc.
  2. RuWordNet (when available) — taxonomic: hypernymy, hyponymy, meronymy.

Usage:
    loader = ThesaurusLoader(conceptnet_cache="data/conceptnet_ru.json")
    judgments = loader.load_all()
    for j in judgments:
        space.materialize_judgment(j)
"""

import json
import os
from typing import Optional

from density_core import Judgment


# ---------------------------------------------------------------------------
# ConceptNet relation → Judgment mapping
# ---------------------------------------------------------------------------

# Relation name → (verb for Judgment, intensity_base, is_negative)
CONCEPTNET_RELATION_MAP = {
    "IsA":          ("является",           0.8, False),
    "PartOf":       ("входит_в",           0.7, False),
    "HasA":         ("имеет",              0.7, False),
    "UsedFor":      ("используется_для",   0.6, False),
    "CapableOf":    ("способен_на",        0.6, False),
    "HasProperty":  ("amod",               0.6, False),   # maps to amod — same as adjective modifier
    "MadeOf":       ("состоит_из",         0.7, False),
    "Causes":       ("вызывает",           0.6, False),
    "CreatedBy":    ("создаётся",          0.6, False),
    "DefinedAs":    ("определяется_как",   0.8, False),
    "Synonym":      ("эквивалентен",       0.9, False),
    "Antonym":      ("противоположен",     0.8, True),    # negative quality
    "AtLocation":   ("находится_в",        0.5, False),
    "RelatedTo":    ("связан_с",           0.4, False),   # weakest
    "DerivedFrom":  ("образовано_от",      0.5, False),
    "SimilarTo":    ("похож_на",           0.6, False),
    "Desires":      ("желает",             0.5, False),
    "ReceivesAction": ("подвергается",     0.5, False),
    "HasSubevent":  ("включает_шаг",       0.5, False),
    "HasPrerequisite": ("требует",         0.6, False),
    "HasFirstSubevent": ("начинается_с",   0.5, False),
    "HasLastSubevent":  ("заканчивается",  0.5, False),
    "MotivatedByGoal":  ("мотивировано",   0.5, False),
    "CausesDesire": ("вызывает_желание",   0.5, False),
}

# RuWordNet relation → Judgment mapping
RUWORDNET_RELATION_MAP = {
    "hypernym":    ("является_видом",   0.9, False),   # собака → животное
    "hyponym":     ("включает_вид",     0.9, False),   # животное → собака
    "part_of":     ("часть",            0.7, False),
    "has_part":    ("содержит_часть",   0.7, False),
    "antonym":     ("противоположен",   0.8, True),
    "instance":    ("экземпляр",        0.8, False),
    "cause":       ("вызывает",         0.6, False),
    "entailment":  ("влечёт",           0.6, False),
    "domain":      ("область",          0.5, False),
}

# Default modality for thesaurus judgments (low — personal statements dominate)
THESAURUS_MODALITY_CONCEPTNET = 0.3
THESAURUS_MODALITY_RUWORDNET = 0.4


# ---------------------------------------------------------------------------
# ConceptNet loader
# ---------------------------------------------------------------------------

def load_conceptnet_judgments(cache_path: str,
                              min_weight: float = 1.0,
                              modality: float = THESAURUS_MODALITY_CONCEPTNET
                              ) -> list[Judgment]:
    """Load judgments from pre-filtered ConceptNet Russian JSON cache.

    Cache format (produced by build_conceptnet_cache.py):
    [
        {"rel": "IsA", "start": "банан", "end": "фрукт", "weight": 2.0},
        ...
    ]
    """
    if not os.path.exists(cache_path):
        print(f"  [thesaurus] ConceptNet cache not found: {cache_path}")
        return []

    with open(cache_path, encoding="utf-8") as f:
        edges = json.load(f)

    judgments = []
    for edge in edges:
        rel = edge["rel"]
        start = edge["start"]
        end = edge["end"]
        weight = edge.get("weight", 1.0)

        if weight < min_weight:
            continue

        mapping = CONCEPTNET_RELATION_MAP.get(rel)
        if mapping is None:
            continue

        verb, intensity_base, is_negative = mapping
        intensity = min(1.0, intensity_base * (weight / 2.0))

        judgments.append(Judgment(
            subject=start,
            verb=verb,
            object=end,
            quality="NEGATIVE" if is_negative else "AFFIRMATIVE",
            modality=modality,
            intensity=intensity,
            source_text=f"[thesaurus:conceptnet:{rel}]",
        ))

    return judgments


# ---------------------------------------------------------------------------
# RuWordNet loader (for when XML files are available)
# ---------------------------------------------------------------------------

def load_ruwordnet_judgments(db_path: Optional[str] = None,
                              modality: float = THESAURUS_MODALITY_RUWORDNET
                              ) -> list[Judgment]:
    """Load judgments from RuWordNet database.

    Requires: pip install ruwordnet + database file.
    If DB not available, returns empty list.
    """
    try:
        from ruwordnet import RuWordNet
        wn = RuWordNet(filename=db_path) if db_path else RuWordNet()
    except (ImportError, FileNotFoundError) as e:
        print(f"  [thesaurus] RuWordNet not available: {e}")
        return []

    judgments = []

    for synset in wn.get_all_synsets():
        # Get the most common lemma for this synset
        senses = synset.senses
        if not senses:
            continue
        term = senses[0].lemma.lower()

        # Hypernyms: term → hypernym (is-a)
        for hyper in synset.hypernyms:
            hyper_senses = hyper.senses
            if hyper_senses:
                hyper_term = hyper_senses[0].lemma.lower()
                judgments.append(Judgment(
                    subject=term,
                    verb="является_видом",
                    object=hyper_term,
                    quality="AFFIRMATIVE",
                    modality=modality,
                    intensity=0.9,
                    source_text="[thesaurus:ruwordnet:hypernym]",
                ))

        # Hyponyms: term → hyponym (includes)
        for hypo in synset.hyponyms:
            hypo_senses = hypo.senses
            if hypo_senses:
                hypo_term = hypo_senses[0].lemma.lower()
                judgments.append(Judgment(
                    subject=term,
                    verb="включает_вид",
                    object=hypo_term,
                    quality="AFFIRMATIVE",
                    modality=modality,
                    intensity=0.9,
                    source_text="[thesaurus:ruwordnet:hyponym]",
                ))

    return judgments


# ---------------------------------------------------------------------------
# Unified loader
# ---------------------------------------------------------------------------

class ThesaurusLoader:
    """Unified thesaurus loader: ConceptNet + RuWordNet → Judgment[]."""

    def __init__(self,
                 conceptnet_cache: Optional[str] = None,
                 ruwordnet_db: Optional[str] = None,
                 conceptnet_min_weight: float = 1.0):
        self.conceptnet_cache = conceptnet_cache
        self.ruwordnet_db = ruwordnet_db
        self.conceptnet_min_weight = conceptnet_min_weight

    def load_all(self) -> list[Judgment]:
        """Load judgments from all available thesaurus sources."""
        all_judgments = []

        if self.conceptnet_cache:
            cn = load_conceptnet_judgments(
                self.conceptnet_cache,
                min_weight=self.conceptnet_min_weight,
            )
            print(f"  [thesaurus] ConceptNet: {len(cn)} judgments loaded")
            all_judgments.extend(cn)

        if self.ruwordnet_db:
            rwn = load_ruwordnet_judgments(self.ruwordnet_db)
            print(f"  [thesaurus] RuWordNet: {len(rwn)} judgments loaded")
            all_judgments.extend(rwn)

        return all_judgments

    def load_for_terms(self, terms: set[str]) -> list[Judgment]:
        """Load only judgments relevant to given terms (for efficiency)."""
        all_j = self.load_all()
        return [j for j in all_j if j.subject in terms or j.object in terms]
