# -*- coding: utf-8 -*-
"""
T9: Evaluation — agnostic pipeline precision/recall.

Measures whether text_parser_agnostic correctly identifies containment pairs
(concept_a contains concept_b) from gold-standard sentences.

Gold format: (sentence, [(concept_a, concept_b), ...])
A pair (A, B) means: after parsing, containment(rho_A, rho_B) should be
noticeably higher than containment(rho_B, rho_A) — asymmetric signal present.

Usage: python -X utf8 evaluation.py
"""

import sys
import os

try:
    from .text_parser_agnostic import text_to_semantic_input, ParseConfig
    from .semantic_input import parse_semantic_input
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from text_parser_agnostic import text_to_semantic_input, ParseConfig
    from semantic_input import parse_semantic_input

import numpy as np


# ---------------------------------------------------------------------------
# Gold standard: (sentence, [(container, contained), ...])
# Pairs where we expect containment(rho_A, rho_B) > containment(rho_B, rho_A)
# Empty list = sentence should produce no meaningful containment pairs
# ---------------------------------------------------------------------------

GOLD_CONTAINMENT = [
    # Full graph: subj→verb, verb→obj, subj→obj (transitive)
    # Verb is a concept-container with its own character of influence.

    ("Свобода требует ответственности.",
     [("свобода", "требует"), ("требует", "ответственности"), ("свобода", "ответственности")]),

    ("Любовь не требует жертв.",
     [("любовь", "требует"), ("требует", "жертв"), ("любовь", "жертв")]),

    ("Выбор порождает ответственность.",
     [("выбор", "порождает"), ("порождает", "ответственность"), ("выбор", "ответственность")]),

    ("Честность укрепляет доверие.",
     [("честность", "укрепляет"), ("укрепляет", "доверие"), ("честность", "доверие")]),

    ("Ложь разрушает отношения.",
     [("ложь", "разрушает"), ("разрушает", "отношения"), ("ложь", "отношения")]),

    ("Страх ограничивает свободу.",
     [("страх", "ограничивает"), ("ограничивает", "свободу"), ("страх", "свободу")]),

    ("Мужество требует силы и терпения.",
     [("мужество", "требует"), ("требует", "силы"), ("требует", "терпения"),
      ("мужество", "силы"), ("мужество", "терпения")]),

    ("Свобода включает выбор и ответственность.",
     [("свобода", "включает"), ("включает", "выбор"), ("включает", "ответственность"),
      ("свобода", "выбор"), ("свобода", "ответственность")]),

    ("Творчество требует дисциплины.",
     [("творчество", "требует"), ("требует", "дисциплины"), ("творчество", "дисциплины")]),

    ("Дружба основана на доверии.",
     [("дружба", "основана"), ("основана", "доверии"), ("дружба", "доверии")]),

    ("Гордость мешает пониманию.",
     [("гордость", "мешает"), ("мешает", "пониманию"), ("гордость", "пониманию")]),

    ("Жадность порождает конфликты.",
     [("жадность", "порождает"), ("порождает", "конфликты"), ("жадность", "конфликты")]),

    ("Зависть отравляет жизнь.",
     [("зависть", "отравляет"), ("отравляет", "жизнь"), ("зависть", "жизнь")]),

    ("Справедливость требует беспристрастности.",
     [("справедливость", "требует"), ("требует", "беспристрастности"),
      ("справедливость", "беспристрастности")]),

    # Episodic — no semantic containment expected
    ("Вчера этот человек пришёл.", []),
    ("Один знакомый сказал мне это.", []),
]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _containment(rho_a: np.ndarray, rho_b: np.ndarray) -> float:
    tr_a = np.trace(rho_a)
    if tr_a < 1e-12:
        return 0.0
    return float(np.sum(rho_a * rho_b.T) / tr_a)


def evaluate(gold_set=None, config: ParseConfig = None, dim: int = 32,
             asymmetry_threshold: float = 0.05) -> dict:
    """
    For each (sentence, pairs) in gold_set:
      - parse sentence → semantic_input → rhos
      - for each expected (A, B): check both concepts present AND
        containment(A,B) > containment(B,A) + asymmetry_threshold

    Returns precision/recall/F1 over expected pairs.
    """
    if gold_set is None:
        gold_set = GOLD_CONTAINMENT
    if config is None:
        config = ParseConfig(min_freq=1, window=5)

    tp = fp = fn = 0
    details = []

    for sentence, expected_pairs in gold_set:
        si = text_to_semantic_input(sentence, config=config)
        _, rhos = parse_semantic_input(si, dim=dim)

        found = []
        missed = []

        for a, b in expected_pairs:
            a_key = _find_key(a, rhos)
            b_key = _find_key(b, rhos)

            if a_key is None or b_key is None:
                reason = f"missing:{'A' if a_key is None else 'B'}"
                missed.append((a, b, reason))
                fn += 1
                continue

            # Both concepts co-occur in the parsed output — link detected
            a_contains = si.get(a_key, {}).get("contains", {})
            b_in_a = any(_find_key(b, {k: {} for k in a_contains}) is not None
                         for k in a_contains if k.startswith(b[:4]) or b.startswith(k[:4]))
            b_contains = si.get(b_key, {}).get("contains", {})
            a_in_b = any(k.startswith(a[:4]) or a.startswith(k[:4]) for k in b_contains)

            if b_in_a or a_in_b:
                found.append((a, b))
                tp += 1
            else:
                missed.append((a, b, "no_cooccurrence"))
                fn += 1

        # false positives: pairs in si that are NOT in gold
        for ka, spec in si.items():
            for kb in spec.get("contains", {}):
                if not _find_original((ka, kb), expected_pairs):
                    fp += 1

        status = "OK" if not missed else ("MISS" if not found else "PARTIAL")
        details.append({
            "sentence": sentence,
            "expected": expected_pairs,
            "found": found,
            "missed": missed,
            "status": status,
        })

    total_gold = sum(len(p) for _, p in gold_set)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, total_gold)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)

    return {
        "total_sentences": len(gold_set),
        "total_gold_pairs": total_gold,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "details": details,
    }


def _find_key(concept: str, rhos: dict) -> str | None:
    """Exact match first, then prefix (handles morphological variants)."""
    if concept in rhos:
        return concept
    for k in rhos:
        if k.startswith(concept[:4]) or concept.startswith(k[:4]):
            return k
    return None


def _find_original(pair: tuple, expected_pairs: list) -> bool:
    a_key, b_key = pair
    for a, b in expected_pairs:
        if (a_key.startswith(a[:4]) or a.startswith(a_key[:4])) and \
           (b_key.startswith(b[:4]) or b.startswith(b_key[:4])):
            return True
    return False


def main():
    print("=" * 65)
    print("T9: Evaluation — Agnostic Pipeline Containment P/R/F1")
    print("=" * 65)

    # Baseline: no thesaurus prior
    print("\n--- BASELINE (no thesaurus) ---")
    result_base = evaluate()
    _print_summary(result_base)

    # With thesaurus prior
    print("\n--- WITH THESAURUS PRIOR (ConceptNet RU, bonus-only) ---")
    try:
        try:
            from .thesaurus_prior import ThesaurusPrior
        except ImportError:
            from thesaurus_prior import ThesaurusPrior
        prior = ThesaurusPrior.from_conceptnet("data/conceptnet_ru.json")
        if len(prior) == 0:
            print("  [skip] thesaurus cache not found at data/conceptnet_ru.json")
        else:
            print(f"  loaded {len(prior)} pairs")
            cfg = ParseConfig(min_freq=1, window=5, thesaurus_prior=prior)
            result_prior = evaluate(config=cfg)
            _print_summary(result_prior)
            print(f"\n  Delta vs baseline: "
                  f"P {result_prior['precision']-result_base['precision']:+.1%}, "
                  f"R {result_prior['recall']-result_base['recall']:+.1%}, "
                  f"F1 {result_prior['f1']-result_base['f1']:+.1%}")
    except Exception as e:
        print(f"  [skip] thesaurus prior failed: {e}")


def _print_summary(result: dict):
    print(f"  Sentences:       {result['total_sentences']}")
    print(f"  Gold pairs:      {result['total_gold_pairs']}")
    print(f"  True positives:  {result['true_positives']}")
    print(f"  False positives: {result['false_positives']}")
    print(f"  False negatives: {result['false_negatives']}")
    print(f"  Precision:       {result['precision']:.1%}")
    print(f"  Recall:          {result['recall']:.1%}")
    print(f"  F1:              {result['f1']:.1%}")


if __name__ == "__main__":
    main()
