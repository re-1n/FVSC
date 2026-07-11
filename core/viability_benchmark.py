"""Controlled viability benchmark for FVSC density-matrix semantics.

This benchmark is deliberately falsifiable.  It asks whether the density-matrix
layer preserves the directed containment relations annotated in
``evaluation.GOLD_CONTAINMENT`` and whether the result is stable across matrix
dimensions.  It also compares FVSC with the direct parser-edge baseline.

Passing this benchmark establishes only *controlled technical viability*.
It does not establish ecological validity for personal semantic maps; that
requires blinded human annotations from held-out vault material.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from .density_core import graded_hyponymy
from .evaluation import GOLD_CONTAINMENT
from .semantic_input import parse_semantic_input
from .text_parser_agnostic import ParseConfig, text_to_semantic_input


DEFAULT_DIMS = (16, 32, 64, 128)
_EPS = 1e-9


@dataclass(frozen=True)
class PairObservation:
    sentence: str
    container: str
    contained: str
    resolved: bool
    matrix_margin: float
    direct_edge_margin: float


def _term_matches(actual: str, expected: str) -> bool:
    """Conservative compatibility matcher for the current non-lemmatised parser."""
    actual = actual.casefold()
    expected = expected.casefold()
    if actual == expected:
        return True
    prefix_len = min(4, len(actual), len(expected))
    return prefix_len >= 3 and actual[:prefix_len] == expected[:prefix_len]


def _find_key(term: str, mapping: dict) -> str | None:
    if term in mapping:
        return term
    matches = sorted(key for key in mapping if _term_matches(key, term))
    return matches[0] if matches else None


def _edge_weight(si: dict, source: str, target: str) -> float:
    source_key = _find_key(source, si)
    if source_key is None:
        return 0.0
    contains = si.get(source_key, {}).get("contains", {})
    target_key = _find_key(target, contains)
    if target_key is None:
        return 0.0
    return float(contains[target_key])


def _normalise_density(rho: np.ndarray) -> np.ndarray:
    trace = float(np.trace(rho))
    if trace <= _EPS:
        return rho
    return rho / trace


def _matrix_margin(rhos: dict[str, np.ndarray], container: str, contained: str) -> tuple[bool, float]:
    """Return directional margin for ``container contains contained``.

    ``graded_hyponymy(A, B)`` measures the degree to which A is included in B.
    Therefore the forward direction is ``contained -> container``.
    """
    container_key = _find_key(container, rhos)
    contained_key = _find_key(contained, rhos)
    if container_key is None or contained_key is None:
        return False, 0.0

    rho_container = _normalise_density(rhos[container_key])
    rho_contained = _normalise_density(rhos[contained_key])
    forward = graded_hyponymy(rho_contained, rho_container)
    reverse = graded_hyponymy(rho_container, rho_contained)
    return True, float(forward - reverse)


def collect_observations(
    *,
    gold_set: Sequence[tuple[str, list[tuple[str, str]]]] = GOLD_CONTAINMENT,
    dim: int = 64,
    config: ParseConfig | None = None,
) -> list[PairObservation]:
    """Parse the gold sentences and collect one observation per directed pair."""
    config = config or ParseConfig(min_freq=1, window=5)
    observations: list[PairObservation] = []

    for sentence, expected_pairs in gold_set:
        si = text_to_semantic_input(sentence, config=config)
        _, rhos = parse_semantic_input(si, dim=dim)
        for container, contained in expected_pairs:
            resolved, matrix_margin = _matrix_margin(rhos, container, contained)
            direct_margin = (
                _edge_weight(si, container, contained)
                - _edge_weight(si, contained, container)
            )
            observations.append(
                PairObservation(
                    sentence=sentence,
                    container=container,
                    contained=contained,
                    resolved=resolved,
                    matrix_margin=matrix_margin,
                    direct_edge_margin=direct_margin,
                )
            )
    return observations


def _outcome(margin: float, *, resolved: bool = True) -> float:
    """1=correct direction, 0.5=tie, 0=wrong or unresolved."""
    if not resolved:
        return 0.0
    if margin > _EPS:
        return 1.0
    if margin < -_EPS:
        return 0.0
    return 0.5


def _bootstrap_ci(values: Sequence[float], *, samples: int, seed: int) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rng = np.random.default_rng(seed)
    arr = np.asarray(values, dtype=float)
    means = np.empty(samples, dtype=float)
    for idx in range(samples):
        means[idx] = float(np.mean(rng.choice(arr, size=len(arr), replace=True)))
    low, high = np.quantile(means, [0.025, 0.975])
    return float(low), float(high)


def _one_sided_sign_pvalue(margins: Iterable[float]) -> float:
    """Exact one-sided sign test against chance, excluding numerical ties."""
    non_ties = [margin for margin in margins if abs(margin) > _EPS]
    n = len(non_ties)
    if n == 0:
        return 1.0
    wins = sum(margin > 0 for margin in non_ties)
    tail = sum(math.comb(n, k) for k in range(wins, n + 1))
    return float(tail / (2**n))


def _summarise_model(
    observations: Sequence[PairObservation],
    *,
    field: str,
    bootstrap_samples: int,
    seed: int,
    use_resolution: bool,
) -> dict:
    outcomes = [
        _outcome(
            float(getattr(obs, field)),
            resolved=(obs.resolved if use_resolution else True),
        )
        for obs in observations
    ]
    margins = [
        float(getattr(obs, field))
        for obs in observations
        if (obs.resolved or not use_resolution)
    ]
    ci_low, ci_high = _bootstrap_ci(outcomes, samples=bootstrap_samples, seed=seed)
    return {
        "accuracy": float(np.mean(outcomes)) if outcomes else 0.0,
        "ci95": [ci_low, ci_high],
        "coverage": (
            sum(obs.resolved for obs in observations) / len(observations)
            if observations and use_resolution
            else 1.0
        ),
        "mean_margin": float(np.mean(margins)) if margins else 0.0,
        "median_margin": float(np.median(margins)) if margins else 0.0,
        "p_vs_chance_one_sided": _one_sided_sign_pvalue(margins),
        "wins": sum(margin > _EPS for margin in margins),
        "ties": sum(abs(margin) <= _EPS for margin in margins),
        "losses": sum(margin < -_EPS for margin in margins),
    }


def _decision(matrix: dict, direct: dict, dimensional_scores: dict[str, float]) -> dict:
    score_range = max(dimensional_scores.values()) - min(dimensional_scores.values())
    reasons: list[str] = []

    passes_signal = (
        matrix["coverage"] >= 0.80
        and matrix["accuracy"] >= 0.65
        and matrix["p_vs_chance_one_sided"] < 0.05
    )
    stable = score_range <= 0.15

    if passes_signal and stable:
        controlled_viability = "pass"
        reasons.append("directional signal exceeds the pre-registered chance threshold")
        reasons.append("accuracy is stable across tested dimensions")
    elif matrix["accuracy"] >= 0.55 and matrix["coverage"] >= 0.70:
        controlled_viability = "inconclusive"
        reasons.append("a directional signal exists, but evidence is not strong enough")
        if not stable:
            reasons.append("results are sensitive to matrix dimension")
    else:
        controlled_viability = "fail"
        reasons.append("the density layer does not recover directed relations reliably")

    improvement = matrix["accuracy"] - direct["accuracy"]
    if improvement > 0.02:
        added_value = "demonstrated_on_controlled_set"
    elif improvement >= -0.02:
        added_value = "not_distinguishable_from_parser_edges"
    else:
        added_value = "worse_than_parser_edges"

    return {
        "controlled_viability": controlled_viability,
        "matrix_added_value_over_direct_edges": added_value,
        "accuracy_delta_vs_direct_edges": improvement,
        "dimension_accuracy_range": score_range,
        "reasons": reasons,
    }


def run_benchmark(
    *,
    dims: Sequence[int] = DEFAULT_DIMS,
    bootstrap_samples: int = 2000,
    seed: int = 20260711,
    gold_set: Sequence[tuple[str, list[tuple[str, str]]]] = GOLD_CONTAINMENT,
) -> dict:
    """Run the controlled benchmark and return a JSON-serialisable report."""
    dimensional_scores: dict[str, float] = {}
    observations_by_dim: dict[int, list[PairObservation]] = {}

    for dim in dims:
        observations = collect_observations(gold_set=gold_set, dim=dim)
        observations_by_dim[dim] = observations
        outcomes = [_outcome(obs.matrix_margin, resolved=obs.resolved) for obs in observations]
        dimensional_scores[str(dim)] = float(np.mean(outcomes)) if outcomes else 0.0

    primary_dim = 64 if 64 in observations_by_dim else dims[0]
    primary = observations_by_dim[primary_dim]
    matrix = _summarise_model(
        primary,
        field="matrix_margin",
        bootstrap_samples=bootstrap_samples,
        seed=seed,
        use_resolution=True,
    )
    direct = _summarise_model(
        primary,
        field="direct_edge_margin",
        bootstrap_samples=bootstrap_samples,
        seed=seed + 1,
        use_resolution=False,
    )

    report = {
        "benchmark": "fvsc-controlled-directionality-v1",
        "primary_dimension": primary_dim,
        "n_sentences": len(gold_set),
        "n_directional_pairs": len(primary),
        "models": {
            "fvsc_density": matrix,
            "direct_parser_edges": direct,
            "chance": {"accuracy": 0.5},
        },
        "dimension_accuracy": dimensional_scores,
        "decision": _decision(matrix, direct, dimensional_scores),
        "limitations": [
            "small, hand-authored Russian controlled set",
            "gold relations are not independently annotated",
            "prefix matching compensates for missing lemmatisation",
            "this does not validate personal-semantic interpretation",
            "a blinded held-out human study is required for external validity",
        ],
        "observations": [
            {
                "sentence": obs.sentence,
                "container": obs.container,
                "contained": obs.contained,
                "resolved": obs.resolved,
                "matrix_margin": obs.matrix_margin,
                "direct_edge_margin": obs.direct_edge_margin,
            }
            for obs in primary
        ],
    }
    return report


def _print_summary(report: dict) -> None:
    matrix = report["models"]["fvsc_density"]
    direct = report["models"]["direct_parser_edges"]
    decision = report["decision"]
    print("FVSC controlled viability benchmark")
    print(f"pairs: {report['n_directional_pairs']} | primary dim: {report['primary_dimension']}")
    print(
        "density: "
        f"accuracy={matrix['accuracy']:.3f} "
        f"CI95=[{matrix['ci95'][0]:.3f}, {matrix['ci95'][1]:.3f}] "
        f"coverage={matrix['coverage']:.3f} "
        f"p={matrix['p_vs_chance_one_sided']:.4g}"
    )
    print(f"direct parser edges: accuracy={direct['accuracy']:.3f}")
    print(f"dimension accuracy: {report['dimension_accuracy']}")
    print(f"controlled viability: {decision['controlled_viability']}")
    print(f"added value over direct edges: {decision['matrix_added_value_over_direct_edges']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional path for the JSON report")
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260711)
    args = parser.parse_args()

    report = run_benchmark(
        bootstrap_samples=max(100, args.bootstrap_samples),
        seed=args.seed,
    )
    _print_summary(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"report: {args.output}")


if __name__ == "__main__":
    main()
