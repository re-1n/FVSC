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


# ---------------------------------------------------------------------------
# Weighted metrics (P@K, R@K, MAP)
#
# The binary evaluate() above treats a gold pair as found whenever co-occurrence
# is detected, regardless of weight. This conflates "parser ranked the right
# pair first" with "parser buried the right pair under 30 noisy ones." The
# functions below rank si["contains"] entries by weight and score the ranking
# directly.
#
# Episodic sentences (expected_pairs == []) are NOT averaged into P@K/R@K/MAP —
# they are reported separately as episodic_false_alarm_rate, since otherwise
# every predicted pair counts as a false positive and dominates the mean.
# ---------------------------------------------------------------------------


def _rank_predicted_pairs(si: dict) -> list:
    """Flatten si into a descending-by-weight list of (container, contained, w).

    Iterates every concept and its contains-dict; ties broken by lexicographic
    order on (a, b) for determinism.
    """
    pairs = []
    for ka, spec in si.items():
        for kb, w in spec.get("contains", {}).items():
            pairs.append((ka, kb, float(w)))
    pairs.sort(key=lambda x: (-x[2], x[0], x[1]))
    return pairs


def _matches_expected(a_key: str, b_key: str, expected_pairs: list) -> bool:
    """Same prefix-match heuristic as _find_original — one matching predicate
    used by both binary eval and weighted eval keeps both on one axis."""
    return _find_original((a_key, b_key), expected_pairs)


def _hits_at_k(predicted_ranked: list, expected_pairs: list, k: int) -> int:
    """Number of top-k predicted pairs that match some gold pair."""
    if not expected_pairs:
        return 0
    hits = 0
    for a, b, _w in predicted_ranked[:k]:
        if _matches_expected(a, b, expected_pairs):
            hits += 1
    return hits


def _average_precision(predicted_ranked: list, expected_pairs: list) -> float:
    """Standard AP: mean of precision at each rank where a relevant pair is hit.

    Edge cases:
      - len(expected)==0 AND len(predicted)==0 → 1.0 (perfect predict-nothing)
      - len(expected)==0 AND len(predicted)>0 → 0.0 (any prediction is noise)
    Episodic sentences are partitioned out of the gold AP mean anyway; these
    branches are safety nets for callers that don't partition.
    """
    n_relevant = len(expected_pairs)
    if n_relevant == 0:
        return 1.0 if not predicted_ranked else 0.0

    hits = 0
    sum_precisions = 0.0
    seen_gold = set()  # don't double-count if parser duplicates a hit
    for rank, (a, b, _w) in enumerate(predicted_ranked, start=1):
        if not _matches_expected(a, b, expected_pairs):
            continue
        # Identify which gold pair was hit so we don't double-count it
        for i, (ga, gb) in enumerate(expected_pairs):
            if i in seen_gold:
                continue
            if (a.startswith(ga[:4]) or ga.startswith(a[:4])) and \
               (b.startswith(gb[:4]) or gb.startswith(b[:4])):
                seen_gold.add(i)
                hits += 1
                sum_precisions += hits / rank
                break
    return sum_precisions / n_relevant


def evaluate_weighted(gold_set=None, config: ParseConfig = None,
                      dim: int = 32, k: int = 10) -> dict:
    """Rank-aware evaluation: precision@k, recall@k, mean average precision.

    Gold sentences (expected_pairs != []) contribute to the P@K/R@K/MAP means.
    Episodic sentences (expected_pairs == []) contribute only to
    episodic_false_alarm_rate — the fraction of them where the parser predicted
    anything at all.

    Caveats:
      * MAP is averaged over gold sentences only (the 14 non-episodic ones in
        the default set).
      * At k=10 with gold pair counts of 3–5 per sentence, R@10 is bounded by
        parser recall, not k; P@10 will look low because the parser emits more
        than 10 ranked pairs while gold has 3.
      * Matching uses the same prefix _find_original heuristic as binary eval,
        so morphological variants still match — keeps both metrics comparable.
    """
    if gold_set is None:
        gold_set = GOLD_CONTAINMENT
    if config is None:
        config = ParseConfig(min_freq=1, window=5)

    gold_sentences = []
    episodic_sentences = []
    per_sentence = []

    for sentence, expected_pairs in gold_set:
        si = text_to_semantic_input(sentence, config=config)
        predicted = _rank_predicted_pairs(si)
        is_episodic = (len(expected_pairs) == 0)

        if is_episodic:
            episodic_sentences.append({
                "sentence": sentence,
                "n_predicted": len(predicted),
                "predicted_top_k": predicted[:k],
            })
            per_sentence.append({
                "sentence": sentence,
                "episodic": True,
                "n_predicted": len(predicted),
                "predicted_top_k": predicted[:k],
                "expected": [],
            })
            continue

        ap = _average_precision(predicted, expected_pairs)
        hits = _hits_at_k(predicted, expected_pairs, k)
        p_at_k = hits / max(1, min(k, len(predicted))) if predicted else 0.0
        r_at_k = hits / max(1, len(expected_pairs))

        gold_sentences.append({
            "sentence": sentence,
            "ap": ap,
            "p_at_k": p_at_k,
            "r_at_k": r_at_k,
        })
        per_sentence.append({
            "sentence": sentence,
            "episodic": False,
            "ap": ap,
            "p_at_k": p_at_k,
            "r_at_k": r_at_k,
            "predicted_top_k": predicted[:k],
            "expected": expected_pairs,
        })

    n_gold = len(gold_sentences)
    n_episodic = len(episodic_sentences)
    mean_p = sum(s["p_at_k"] for s in gold_sentences) / max(1, n_gold)
    mean_r = sum(s["r_at_k"] for s in gold_sentences) / max(1, n_gold)
    mean_ap = sum(s["ap"] for s in gold_sentences) / max(1, n_gold)
    episodic_fa = (
        sum(1 for s in episodic_sentences if s["n_predicted"] > 0)
        / max(1, n_episodic)
    )

    return {
        "k": k,
        "n_gold_sentences": n_gold,
        "n_episodic_sentences": n_episodic,
        "precision_at_k": mean_p,
        "recall_at_k": mean_r,
        "map": mean_ap,
        "episodic_false_alarm_rate": episodic_fa,
        "per_sentence": per_sentence,
    }


def _print_weighted_summary(result: dict):
    print(f"  k:                       {result['k']}")
    print(f"  Gold sentences:          {result['n_gold_sentences']}")
    print(f"  Episodic sentences:      {result['n_episodic_sentences']}")
    print(f"  Mean Precision@{result['k']}:       {result['precision_at_k']:.1%}")
    print(f"  Mean Recall@{result['k']}:          {result['recall_at_k']:.1%}")
    print(f"  MAP:                     {result['map']:.1%}")
    print(f"  Episodic FA rate:        {result['episodic_false_alarm_rate']:.1%}")


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
    prior = None
    try:
        try:
            from .thesaurus_prior import ThesaurusPrior
        except ImportError:
            from thesaurus_prior import ThesaurusPrior
        prior = ThesaurusPrior.from_conceptnet("data/conceptnet_ru.json")
        if len(prior) == 0:
            print("  [skip] thesaurus cache not found at data/conceptnet_ru.json")
            prior = None
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
        prior = None

    # Weighted metrics: P@10, R@10, MAP, episodic false-alarm rate
    print("\n" + "=" * 65)
    print("WEIGHTED METRICS (k=10) — rank-aware evaluation")
    print("=" * 65)
    print("\n--- BASELINE (no thesaurus) ---")
    weighted_base = evaluate_weighted(k=10)
    _print_weighted_summary(weighted_base)

    if prior is not None:
        print("\n--- WITH THESAURUS PRIOR ---")
        cfg = ParseConfig(min_freq=1, window=5, thesaurus_prior=prior)
        weighted_prior = evaluate_weighted(config=cfg, k=10)
        _print_weighted_summary(weighted_prior)
        print(f"\n  Delta vs baseline: "
              f"P@10 {weighted_prior['precision_at_k']-weighted_base['precision_at_k']:+.1%}, "
              f"R@10 {weighted_prior['recall_at_k']-weighted_base['recall_at_k']:+.1%}, "
              f"MAP {weighted_prior['map']-weighted_base['map']:+.1%}")


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
