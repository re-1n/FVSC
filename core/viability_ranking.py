"""All-pairs ranking evaluation used by the FVSC viability benchmark."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .density_core import graded_hyponymy
from .evaluation import GOLD_CONTAINMENT
from .semantic_input import parse_semantic_input
from .text_parser_agnostic import ParseConfig, text_to_semantic_input

_EPS = 1e-9


def _matches(actual: str, expected: str) -> bool:
    actual = actual.casefold()
    expected = expected.casefold()
    if actual == expected:
        return True
    prefix_len = min(4, len(actual), len(expected))
    return prefix_len >= 3 and actual[:prefix_len] == expected[:prefix_len]


def _is_gold_pair(a: str, b: str, expected_pairs: list[tuple[str, str]]) -> bool:
    return any(_matches(a, ga) and _matches(b, gb) for ga, gb in expected_pairs)


def _normalise(rho: np.ndarray) -> np.ndarray:
    trace = float(np.trace(rho))
    return rho if trace <= _EPS else rho / trace


def _direction_margin(rho_a: np.ndarray, rho_b: np.ndarray) -> float:
    """Margin for the hypothesis A contains B."""
    return float(
        graded_hyponymy(rho_b, rho_a)
        - graded_hyponymy(rho_a, rho_b)
    )


def _direct_edge_margin(si: dict, a: str, b: str) -> float:
    ab = float(si.get(a, {}).get("contains", {}).get(b, 0.0))
    ba = float(si.get(b, {}).get("contains", {}).get(a, 0.0))
    return ab - ba


def _pairwise_auc(positive_scores: list[float], negative_scores: list[float]) -> tuple[float, int]:
    """Tie-aware AUC as P(score_positive > score_negative)."""
    outcomes: list[float] = []
    for positive in positive_scores:
        for negative in negative_scores:
            if positive > negative + _EPS:
                outcomes.append(1.0)
            elif positive < negative - _EPS:
                outcomes.append(0.0)
            else:
                outcomes.append(0.5)
    if not outcomes:
        return 0.5, 0
    return float(np.mean(outcomes)), len(outcomes)


def evaluate_all_pairs_ranking(
    *,
    gold_set: Sequence[tuple[str, list[tuple[str, str]]]] = GOLD_CONTAINMENT,
    dim: int = 64,
    config: ParseConfig | None = None,
) -> dict[str, dict]:
    """Rank annotated links against every other directed concept pair.

    The evaluation is micro-averaged over all positive-negative comparisons.
    Sentences with no positive pairs are excluded because AUC is undefined for
    a one-class sample; they remain covered by the separate parser evaluation.
    """
    config = config or ParseConfig(min_freq=1, window=5)
    model_names = (
        "fvsc_density_mass_preserving",
        "fvsc_density_trace_normalized_control",
        "trace_mass_only",
        "direct_parser_edges",
    )
    pairwise_outcomes: dict[str, list[float]] = {name: [] for name in model_names}
    per_sentence: list[dict] = []
    total_positives = 0
    total_negatives = 0

    for sentence, expected_pairs in gold_set:
        if not expected_pairs:
            continue
        si = text_to_semantic_input(sentence, config=config)
        _, rhos = parse_semantic_input(si, dim=dim)
        terms = sorted(rhos)
        scores: dict[str, list[tuple[bool, float]]] = {name: [] for name in model_names}

        for a in terms:
            for b in terms:
                if a == b:
                    continue
                is_positive = _is_gold_pair(a, b, expected_pairs)
                rho_a = rhos[a]
                rho_b = rhos[b]
                scores["fvsc_density_mass_preserving"].append(
                    (is_positive, _direction_margin(rho_a, rho_b))
                )
                scores["fvsc_density_trace_normalized_control"].append(
                    (is_positive, _direction_margin(_normalise(rho_a), _normalise(rho_b)))
                )
                scores["trace_mass_only"].append(
                    (is_positive, float(np.trace(rho_a) - np.trace(rho_b)))
                )
                scores["direct_parser_edges"].append(
                    (is_positive, _direct_edge_margin(si, a, b))
                )

        positive_count = sum(is_positive for is_positive, _ in scores[model_names[0]])
        negative_count = len(scores[model_names[0]]) - positive_count
        total_positives += positive_count
        total_negatives += negative_count
        sentence_result = {
            "sentence": sentence,
            "positive_pairs": positive_count,
            "negative_pairs": negative_count,
            "auc": {},
        }

        for model_name in model_names:
            positive_scores = [score for positive, score in scores[model_name] if positive]
            negative_scores = [score for positive, score in scores[model_name] if not positive]
            sentence_auc, _ = _pairwise_auc(positive_scores, negative_scores)
            sentence_result["auc"][model_name] = sentence_auc
            for positive in positive_scores:
                for negative in negative_scores:
                    if positive > negative + _EPS:
                        pairwise_outcomes[model_name].append(1.0)
                    elif positive < negative - _EPS:
                        pairwise_outcomes[model_name].append(0.0)
                    else:
                        pairwise_outcomes[model_name].append(0.5)
        per_sentence.append(sentence_result)

    result: dict[str, dict] = {}
    for model_name, outcomes in pairwise_outcomes.items():
        result[model_name] = {
            "ranking_auc": float(np.mean(outcomes)) if outcomes else 0.5,
            "ranking_comparisons": len(outcomes),
            "positive_pairs": total_positives,
            "negative_pairs": total_negatives,
        }
    result["details"] = {"per_sentence": per_sentence}
    return result
