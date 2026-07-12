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


def _comparison_outcome(positive: float, negative: float) -> float:
    if positive > negative + _EPS:
        return 1.0
    if positive < negative - _EPS:
        return 0.0
    return 0.5


def evaluate_all_pairs_ranking(
    *,
    gold_set: Sequence[tuple[str, list[tuple[str, str]]]] = GOLD_CONTAINMENT,
    dim: int = 64,
    config: ParseConfig | None = None,
) -> dict[str, dict]:
    """Rank annotated links against unrelated directed pairs.

    Two AUCs are reported:

    * ``ranking_auc`` compares every gold pair with every negative pair;
    * ``trace_matched_auc`` compares only pairs with the same rounded
      ``Tr(rho_A)-Tr(rho_B)``.  In that subset a trace-only rule is forced to
      tie at 0.5, so any residual signal must come from something beyond total
      mass (or from another correlated feature).
    """
    config = config or ParseConfig(min_freq=1, window=5)
    model_names = (
        "fvsc_density_mass_preserving",
        "fvsc_density_trace_normalized_control",
        "trace_mass_only",
        "direct_parser_edges",
    )
    all_outcomes: dict[str, list[float]] = {name: [] for name in model_names}
    matched_outcomes: dict[str, list[float]] = {name: [] for name in model_names}
    per_sentence: list[dict] = []
    total_positives = 0
    total_negatives = 0

    for sentence, expected_pairs in gold_set:
        if not expected_pairs:
            continue
        si = text_to_semantic_input(sentence, config=config)
        _, rhos = parse_semantic_input(si, dim=dim)
        terms = sorted(rhos)
        records: list[dict] = []

        for a in terms:
            for b in terms:
                if a == b:
                    continue
                rho_a = rhos[a]
                rho_b = rhos[b]
                trace_score = float(np.trace(rho_a) - np.trace(rho_b))
                records.append({
                    "positive": _is_gold_pair(a, b, expected_pairs),
                    "trace_bin": round(trace_score, 8),
                    "scores": {
                        "fvsc_density_mass_preserving": _direction_margin(rho_a, rho_b),
                        "fvsc_density_trace_normalized_control": _direction_margin(
                            _normalise(rho_a), _normalise(rho_b)
                        ),
                        "trace_mass_only": trace_score,
                        "direct_parser_edges": _direct_edge_margin(si, a, b),
                    },
                })

        positives = [record for record in records if record["positive"]]
        negatives = [record for record in records if not record["positive"]]
        total_positives += len(positives)
        total_negatives += len(negatives)
        sentence_result = {
            "sentence": sentence,
            "positive_pairs": len(positives),
            "negative_pairs": len(negatives),
            "auc": {},
            "trace_matched_auc": {},
            "trace_matched_comparisons": {},
        }

        for model_name in model_names:
            sentence_all: list[float] = []
            sentence_matched: list[float] = []
            for positive in positives:
                for negative in negatives:
                    outcome = _comparison_outcome(
                        positive["scores"][model_name],
                        negative["scores"][model_name],
                    )
                    sentence_all.append(outcome)
                    all_outcomes[model_name].append(outcome)
                    if positive["trace_bin"] == negative["trace_bin"]:
                        sentence_matched.append(outcome)
                        matched_outcomes[model_name].append(outcome)
            sentence_result["auc"][model_name] = (
                float(np.mean(sentence_all)) if sentence_all else 0.5
            )
            sentence_result["trace_matched_auc"][model_name] = (
                float(np.mean(sentence_matched)) if sentence_matched else 0.5
            )
            sentence_result["trace_matched_comparisons"][model_name] = len(sentence_matched)
        per_sentence.append(sentence_result)

    result: dict[str, dict] = {}
    for model_name in model_names:
        outcomes = all_outcomes[model_name]
        matched = matched_outcomes[model_name]
        result[model_name] = {
            "ranking_auc": float(np.mean(outcomes)) if outcomes else 0.5,
            "ranking_comparisons": len(outcomes),
            "trace_matched_auc": float(np.mean(matched)) if matched else 0.5,
            "trace_matched_comparisons": len(matched),
            "positive_pairs": total_positives,
            "negative_pairs": total_negatives,
        }
    result["details"] = {"per_sentence": per_sentence}
    return result
