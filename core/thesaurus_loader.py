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
import xml.etree.ElementTree as ET
from typing import Optional

try:
    from .density_core import Judgment
except ImportError:
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

def load_ruwordnet_judgments(xml_dir: Optional[str] = None,
                              modality: float = THESAURUS_MODALITY_RUWORDNET
                              ) -> list[Judgment]:
    """Load judgments from RuWordNet XML files (from ruwordnet.ru).

    Args:
        xml_dir: directory containing synsets.N.xml, synset_relations.N.xml, senses.N.xml, etc.
    """
    if xml_dir is None or not os.path.isdir(xml_dir):
        print(f"  [thesaurus] RuWordNet XML dir not found: {xml_dir}")
        return []

    # Step 1: Build synset_id → first lemma mapping from senses files
    # senses.X.xml: flat list of <sense name="..." synset_id="..." synt_type="..."/>
    # We take the first single-word sense (synt_type="N"/"V"/"A") per synset
    synset_lemma = {}
    for pos in ("N", "V", "A"):
        senses_path = os.path.join(xml_dir, f"senses.{pos}.xml")
        if not os.path.exists(senses_path):
            continue
        tree = ET.parse(senses_path)
        for sense_el in tree.getroot():
            sid = sense_el.attrib.get("synset_id", "")
            if sid in synset_lemma:
                continue
            # Prefer single-word senses (synt_type N/V/A, not NG/VG)
            name = sense_el.attrib.get("name", "").strip()
            synt = sense_el.attrib.get("synt_type", "")
            if name and " " not in name and len(synt) <= 2:
                synset_lemma[sid] = name.lower()

    # Step 2: Parse relations and convert to Judgments
    judgments = []
    for pos in ("N", "V", "A"):
        rels_path = os.path.join(xml_dir, f"synset_relations.{pos}.xml")
        if not os.path.exists(rels_path):
            continue
        tree = ET.parse(rels_path)
        for rel_el in tree.getroot():
            rel_name = rel_el.attrib.get("name", "")
            child_id = rel_el.attrib.get("child_id", "")
            parent_id = rel_el.attrib.get("parent_id", "")

            child_lemma = synset_lemma.get(child_id)
            parent_lemma = synset_lemma.get(parent_id)
            if not child_lemma or not parent_lemma or child_lemma == parent_lemma:
                continue
            if len(child_lemma) < 2 or len(parent_lemma) < 2:
                continue

            mapping = RUWORDNET_RELATION_MAP.get(rel_name)
            if mapping is None:
                continue

            verb, intensity, is_negative = mapping
            # parent_id is the "container", child_id is what's inside
            judgments.append(Judgment(
                subject=parent_lemma,
                verb=verb,
                object=child_lemma,
                quality="NEGATIVE" if is_negative else "AFFIRMATIVE",
                modality=modality,
                intensity=intensity,
                source_text=f"[thesaurus:ruwordnet:{rel_name}]",
            ))

    return judgments


# ---------------------------------------------------------------------------
# Unified loader
# ---------------------------------------------------------------------------

class ThesaurusLoader:
    """Unified thesaurus loader: ConceptNet + RuWordNet → Judgment[]."""

    def __init__(self,
                 conceptnet_cache: Optional[str] = None,
                 ruwordnet_dir: Optional[str] = None,
                 conceptnet_min_weight: float = 1.0):
        self.conceptnet_cache = conceptnet_cache
        self.ruwordnet_dir = ruwordnet_dir
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

        if self.ruwordnet_dir:
            rwn = load_ruwordnet_judgments(self.ruwordnet_dir)
            print(f"  [thesaurus] RuWordNet: {len(rwn)} judgments loaded")
            all_judgments.extend(rwn)

        return all_judgments

    def load_for_terms(self, terms: set[str]) -> list[Judgment]:
        """Load only judgments relevant to given terms (for efficiency)."""
        all_j = self.load_all()
        return [j for j in all_j if j.subject in terms or j.object in terms]
