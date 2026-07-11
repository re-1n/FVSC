"""Chronological held-out evaluation for the FVSC daily pilot.

The evaluation trains only on earlier documents and asks whether semantic shapes
rank directed relations found in later documents above unrelated directed pairs
from those same documents. It compares FVSC with direct-edge frequency,
trace-mass and deterministic-random baselines. This is a technical predictive
test; it does not replace blinded human relevance ratings.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping, Sequence

import numpy as np

from .pilot_batch import PilotSourceDocument, build_runtime_from_sources
from .pilot_runtime import _statement_rows
from .semantic_metrics import operator_inclusion


_EPS = 1e-12
RankedExample = tuple[bool, float, str]


@dataclass(frozen=True)
class HeldoutDocument:
    source_id: str
    observed_at: float
    semantic_input: Mapping[str, Mapping[str, Any]]
    source_revision: str

    def as_source(self) -> PilotSourceDocument:
        return PilotSourceDocument(
            source_id=self.source_id,
            semantic_input=self.semantic_input,
            source_revision=self.source_revision,
            observed_at=self.observed_at,
        )


def _edge_rows(document: HeldoutDocument) -> list[tuple[str, str, float]]:
    return [
        (subject, object_, relation_weight)
        for subject, object_, relation_weight, _subject_weight in _statement_rows(
            document.semantic_input
        )
    ]


def chronological_split(
    documents: Sequence[HeldoutDocument],
    *,
    train_fraction: float = 0.8,
) -> tuple[tuple[HeldoutDocument, ...], tuple[HeldoutDocument, ...]]:
    if not 0.5 <= train_fraction < 1.0:
        raise ValueError("train_fraction must be in [0.5, 1.0)")
    ordered = tuple(sorted(documents, key=lambda item: (item.observed_at, item.source_id)))
    if len(ordered) < 2:
        return ordered, ()
    split_index = int(np.floor(len(ordered) * train_fraction))
    split_index = min(max(1, split_index), len(ordered) - 1)
    return ordered[:split_index], ordered[split_index:]


def _stable_random_score(parent: str, child: str) -> float:
    digest = hashlib.sha256(f"{parent}\0{child}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little") / float(2**64 - 1)


def _pairwise_outcome(positive: float, negative: float) -> float:
    if positive > negative + _EPS:
        return 1.0
    if positive < negative - _EPS:
        return 0.0
    return 0.5


def _average_precision(examples: Sequence[RankedExample]) -> float:
    """Average precision with a label-independent deterministic tie-break."""
    positives = sum(label for label, _score, _key in examples)
    if positives == 0:
        return 0.0
    ranked = sorted(examples, key=lambda item: (-item[1], item[2]))
    hits = 0
    total = 0.0
    for rank, (label, _score, _key) in enumerate(ranked, start=1):
        if label:
            hits += 1
            total += hits / rank
    return total / positives


def _bootstrap_delta(
    fvsc_outcomes: Sequence[float],
    baseline_outcomes: Sequence[float],
    *,
    samples: int,
    seed: int,
) -> tuple[float, float]:
    if len(fvsc_outcomes) != len(baseline_outcomes):
        raise ValueError("paired outcomes must have equal lengths")
    if not fvsc_outcomes:
        return 0.0, 0.0
    rng = np.random.default_rng(seed)
    fvsc = np.asarray(fvsc_outcomes, dtype=float)
    baseline = np.asarray(baseline_outcomes, dtype=float)
    deltas = np.empty(samples, dtype=float)
    for index in range(samples):
        chosen = rng.integers(0, len(fvsc), size=len(fvsc))
        deltas[index] = float(np.mean(fvsc[chosen] - baseline[chosen]))
    low, high = np.quantile(deltas, [0.025, 0.975])
    return float(low), float(high)


def run_heldout_evaluation(
    documents: Sequence[HeldoutDocument],
    *,
    train_fraction: float = 0.8,
    bootstrap_samples: int = 1000,
    seed: int = 20260711,
    max_negatives_per_document: int = 200,
) -> dict[str, Any]:
    """Run a deterministic chronological relation-ranking evaluation."""
    if bootstrap_samples < 100:
        raise ValueError("bootstrap_samples must be at least 100")
    if max_negatives_per_document < 1:
        raise ValueError("max_negatives_per_document must be positive")

    train, test = chronological_split(documents, train_fraction=train_fraction)
    runtime = build_runtime_from_sources([document.as_source() for document in train])
    known_terms = {concept.term for concept in runtime.snapshot.concepts}

    direct_counts: dict[tuple[str, str], float] = {}
    for document in train:
        for parent, child, weight in _edge_rows(document):
            direct_counts[(parent, child)] = direct_counts.get((parent, child), 0.0) + weight

    model_names = ("fvsc_shape", "direct_graph", "trace_mass", "random")
    pairwise: dict[str, list[float]] = {name: [] for name in model_names}
    ranked_examples: dict[str, list[RankedExample]] = {name: [] for name in model_names}
    positive_total = 0
    positive_known = 0
    negative_total = 0
    evaluated_documents = 0
    details: list[dict[str, Any]] = []

    for document in test:
        all_edges = _edge_rows(document)
        positive_total += len(all_edges)
        positives = [
            (parent, child)
            for parent, child, _weight in all_edges
            if parent in known_terms and child in known_terms
        ]
        positive_known += len(positives)
        if not positives:
            details.append({
                "source_id": document.source_id,
                "positives": len(all_edges),
                "known_positives": 0,
                "negatives": 0,
                "skipped": "no_known_positive_pairs",
            })
            continue

        terms = sorted({
            term
            for parent, child, _weight in all_edges
            for term in (parent, child)
            if term in known_terms
        })
        positive_set = set(positives)
        negatives = [
            (parent, child)
            for parent in terms
            for child in terms
            if parent != child and (parent, child) not in positive_set
        ][:max_negatives_per_document]
        negative_total += len(negatives)
        if not negatives:
            details.append({
                "source_id": document.source_id,
                "positives": len(all_edges),
                "known_positives": len(positives),
                "negatives": 0,
                "skipped": "no_candidate_negatives",
            })
            continue

        evaluated_documents += 1

        def scores(pair: tuple[str, str]) -> dict[str, float]:
            parent_term, child_term = pair
            parent = runtime.get(parent_term)
            child = runtime.get(child_term)
            assert parent is not None and child is not None
            return {
                "fvsc_shape": operator_inclusion(child.state, parent.state),
                "direct_graph": direct_counts.get(pair, 0.0),
                "trace_mass": parent.state.mass - child.state.mass,
                "random": _stable_random_score(parent_term, child_term),
            }

        positive_scores = [(pair, scores(pair)) for pair in positives]
        negative_scores = [(pair, scores(pair)) for pair in negatives]
        for model_name in model_names:
            for pair, score_map in positive_scores:
                key = f"{document.source_id}\0{pair[0]}\0{pair[1]}"
                ranked_examples[model_name].append((True, score_map[model_name], key))
            for pair, score_map in negative_scores:
                key = f"{document.source_id}\0{pair[0]}\0{pair[1]}"
                ranked_examples[model_name].append((False, score_map[model_name], key))
            for _positive_pair, positive_map in positive_scores:
                for _negative_pair, negative_map in negative_scores:
                    pairwise[model_name].append(_pairwise_outcome(
                        positive_map[model_name], negative_map[model_name]
                    ))

        details.append({
            "source_id": document.source_id,
            "positives": len(all_edges),
            "known_positives": len(positives),
            "negatives": len(negatives),
            "skipped": None,
        })

    metrics: dict[str, dict[str, Any]] = {}
    for model_name in model_names:
        outcomes = pairwise[model_name]
        metrics[model_name] = {
            "auc": float(np.mean(outcomes)) if outcomes else 0.5,
            "average_precision": _average_precision(ranked_examples[model_name]),
            "pairwise_comparisons": len(outcomes),
        }

    baseline_names = ("direct_graph", "trace_mass", "random")
    best_baseline_name = max(
        baseline_names,
        key=lambda name: (metrics[name]["auc"], name),
    )
    best_baseline = metrics[best_baseline_name]
    delta = metrics["fvsc_shape"]["auc"] - best_baseline["auc"]
    ci_low, ci_high = _bootstrap_delta(
        pairwise["fvsc_shape"],
        pairwise[best_baseline_name],
        samples=bootstrap_samples,
        seed=seed,
    )
    coverage = positive_known / positive_total if positive_total else 0.0
    comparisons = metrics["fvsc_shape"]["pairwise_comparisons"]

    if comparisons < 100 or positive_known < 20 or coverage < 0.5:
        verdict = "insufficient_data"
    elif delta > 0.02 and ci_low > 0.0 and metrics["fvsc_shape"]["auc"] >= 0.6:
        verdict = "promising_added_value"
    elif metrics["fvsc_shape"]["auc"] < 0.55:
        verdict = "not_predictive"
    else:
        verdict = "no_demonstrated_added_value"

    return {
        "benchmark": "fvsc-chronological-heldout-v1",
        "train_documents": len(train),
        "test_documents": len(test),
        "evaluated_test_documents": evaluated_documents,
        "train_cutoff": train[-1].observed_at if train else None,
        "positive_pairs_total": positive_total,
        "positive_pairs_known": positive_known,
        "known_positive_coverage": coverage,
        "negative_pairs": negative_total,
        "models": metrics,
        "best_baseline": best_baseline_name,
        "fvsc_auc_delta_vs_best_baseline": delta,
        "paired_bootstrap_ci95": [ci_low, ci_high],
        "verdict": verdict,
        "details": details,
        "limitations": [
            "parser-derived relations are proxy labels, not independent human annotations",
            "only concepts observed in the training period can be evaluated",
            "the deterministic pilot encoder is a baseline, not a learned contextual encoder",
            "personal usefulness still requires blinded or explicit user ratings",
        ],
    }
