"""Leakage-controlled comparison of candidate semantic representations.

This module separates the canonical evidence store from derived semantic backends.
Every backend receives the same earlier documents and scores the same directed pairs
in later documents.  The first bakeoff intentionally uses dependency-free models so
that a result is reproducible in ordinary CI and does not depend on model downloads.

The benchmark evaluates the *current instantiation* of each representation.  A poor
score for the deterministic density encoder is not a proof against density matrices
in general; it identifies which implementation has or has not earned its complexity.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .pilot_batch import build_runtime_from_sources
from .pilot_evaluation import HeldoutDocument, chronological_split
from .pilot_runtime import _statement_rows
from .semantic_metrics import operator_inclusion


BENCHMARK_VERSION = "fvsc-representation-bakeoff-v1"
_EPS = 1e-12
RankedExample = tuple[bool, float, str]


def _edge_rows(document: HeldoutDocument) -> list[tuple[str, str, float]]:
    return [
        (parent, child, float(weight))
        for parent, child, weight, _subject_weight in _statement_rows(
            document.semantic_input
        )
    ]


def _stable_random_score(parent: str, child: str) -> float:
    digest = hashlib.sha256(f"{parent}\0{child}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little") / float(2**64 - 1)


def _average_precision(examples: Sequence[RankedExample]) -> float:
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


@dataclass(frozen=True)
class SparseGraphState:
    """Train-only directed graph statistics used by simple baselines."""

    counts: Mapping[tuple[str, str], float]
    outgoing: Mapping[str, Mapping[str, float]]
    row_totals: Mapping[str, float]
    column_totals: Mapping[str, float]
    total_weight: float
    known_terms: frozenset[str]

    @classmethod
    def fit(cls, documents: Sequence[HeldoutDocument]) -> "SparseGraphState":
        counts: dict[tuple[str, str], float] = {}
        outgoing: dict[str, dict[str, float]] = {}
        row_totals: dict[str, float] = {}
        column_totals: dict[str, float] = {}
        known_terms: set[str] = set()
        total_weight = 0.0

        for document in documents:
            for parent, child, weight in _edge_rows(document):
                if not math.isfinite(weight) or weight <= 0.0:
                    continue
                key = (parent, child)
                counts[key] = counts.get(key, 0.0) + weight
                row = outgoing.setdefault(parent, {})
                row[child] = row.get(child, 0.0) + weight
                row_totals[parent] = row_totals.get(parent, 0.0) + weight
                column_totals[child] = column_totals.get(child, 0.0) + weight
                total_weight += weight
                known_terms.update((parent, child))

        return cls(
            counts=counts,
            outgoing=outgoing,
            row_totals=row_totals,
            column_totals=column_totals,
            total_weight=total_weight,
            known_terms=frozenset(known_terms),
        )

    def direct(self, parent: str, child: str) -> float:
        return float(self.counts.get((parent, child), 0.0))

    def conditional(self, parent: str, child: str) -> float:
        total = float(self.row_totals.get(parent, 0.0))
        if total <= _EPS:
            return 0.0
        return self.direct(parent, child) / total

    def ppmi(self, parent: str, child: str) -> float:
        count = self.direct(parent, child)
        row = float(self.row_totals.get(parent, 0.0))
        column = float(self.column_totals.get(child, 0.0))
        if count <= _EPS or row <= _EPS or column <= _EPS or self.total_weight <= _EPS:
            return 0.0
        value = math.log2((count * self.total_weight) / (row * column))
        return max(0.0, value)

    def context_inclusion(self, parent: str, child: str) -> float:
        """Coverage of the child's outgoing context by the parent's context.

        Both rows are L1-normalized.  The score is the histogram intersection and
        therefore lies in [0, 1].  It is asymmetric because the arguments identify
        which concept is expected to contain the other's context.
        """
        parent_total = float(self.row_totals.get(parent, 0.0))
        child_total = float(self.row_totals.get(child, 0.0))
        if parent_total <= _EPS or child_total <= _EPS:
            return 0.0
        parent_row = self.outgoing.get(parent, {})
        child_row = self.outgoing.get(child, {})
        return float(sum(
            min(
                float(child_weight) / child_total,
                float(parent_row.get(context, 0.0)) / parent_total,
            )
            for context, child_weight in child_row.items()
        ))


@dataclass(frozen=True)
class RepresentationSuite:
    graph: SparseGraphState
    runtime: Any
    known_terms: frozenset[str]

    MODEL_NAMES = (
        "direct_graph",
        "conditional_graph",
        "ppmi_graph",
        "sparse_context_inclusion",
        "fvsc_density_shape",
        "trace_mass",
        "random",
    )

    @classmethod
    def fit(cls, documents: Sequence[HeldoutDocument]) -> "RepresentationSuite":
        graph = SparseGraphState.fit(documents)
        runtime = build_runtime_from_sources([document.as_source() for document in documents])
        runtime_terms = frozenset(concept.term for concept in runtime.snapshot.concepts)
        return cls(
            graph=graph,
            runtime=runtime,
            known_terms=frozenset(graph.known_terms & runtime_terms),
        )

    def scores(self, parent: str, child: str) -> dict[str, float]:
        parent_concept = self.runtime.get(parent)
        child_concept = self.runtime.get(child)
        if parent_concept is None or child_concept is None:
            raise KeyError("pair contains a term absent from the fitted representation")
        return {
            "direct_graph": self.graph.direct(parent, child),
            "conditional_graph": self.graph.conditional(parent, child),
            "ppmi_graph": self.graph.ppmi(parent, child),
            "sparse_context_inclusion": self.graph.context_inclusion(parent, child),
            "fvsc_density_shape": operator_inclusion(
                child_concept.state,
                parent_concept.state,
            ),
            "trace_mass": parent_concept.state.mass - child_concept.state.mass,
            "random": _stable_random_score(parent, child),
        }


@dataclass(frozen=True)
class _DocumentOutcome:
    wins: Mapping[str, float]
    comparisons: int


def _paired_document_bootstrap(
    outcomes: Sequence[_DocumentOutcome],
    *,
    candidate: str,
    baseline: str,
    samples: int,
    seed: int,
) -> tuple[float, float]:
    if not outcomes:
        return 0.0, 0.0
    rng = np.random.default_rng(seed)
    deltas = np.empty(samples, dtype=float)
    for sample_index in range(samples):
        chosen = rng.integers(0, len(outcomes), size=len(outcomes))
        candidate_wins = 0.0
        baseline_wins = 0.0
        comparisons = 0
        for index in chosen:
            outcome = outcomes[int(index)]
            candidate_wins += float(outcome.wins[candidate])
            baseline_wins += float(outcome.wins[baseline])
            comparisons += outcome.comparisons
        if comparisons:
            deltas[sample_index] = (candidate_wins - baseline_wins) / comparisons
        else:
            deltas[sample_index] = 0.0
    low, high = np.quantile(deltas, [0.025, 0.975])
    return float(low), float(high)


def run_representation_bakeoff(
    documents: Sequence[HeldoutDocument],
    *,
    train_fraction: float = 0.8,
    bootstrap_samples: int = 1000,
    seed: int = 20260712,
    max_negatives_per_document: int = 200,
) -> dict[str, Any]:
    """Compare candidate backends on one chronological relation-ranking task."""
    if bootstrap_samples < 100:
        raise ValueError("bootstrap_samples must be at least 100")
    if max_negatives_per_document < 1:
        raise ValueError("max_negatives_per_document must be positive")

    train, test = chronological_split(documents, train_fraction=train_fraction)
    suite = RepresentationSuite.fit(train)
    model_names = suite.MODEL_NAMES
    total_wins = {name: 0.0 for name in model_names}
    total_comparisons = {name: 0 for name in model_names}
    ranked_examples: dict[str, list[RankedExample]] = {name: [] for name in model_names}
    document_outcomes: list[_DocumentOutcome] = []
    positive_total = 0
    positive_known = 0
    negative_total = 0
    details: list[dict[str, Any]] = []

    for document in test:
        all_edges = _edge_rows(document)
        positive_total += len(all_edges)
        positives = [
            (parent, child)
            for parent, child, _weight in all_edges
            if parent in suite.known_terms and child in suite.known_terms
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
            if term in suite.known_terms
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

        positive_scores = [(pair, suite.scores(*pair)) for pair in positives]
        negative_scores = [(pair, suite.scores(*pair)) for pair in negatives]
        comparisons = len(positives) * len(negatives)
        document_wins: dict[str, float] = {}

        for model_name in model_names:
            pos = np.asarray([score_map[model_name] for _pair, score_map in positive_scores])
            neg = np.asarray([score_map[model_name] for _pair, score_map in negative_scores])
            difference = pos[:, None] - neg[None, :]
            wins = float(np.count_nonzero(difference > _EPS))
            wins += 0.5 * float(np.count_nonzero(np.abs(difference) <= _EPS))
            document_wins[model_name] = wins
            total_wins[model_name] += wins
            total_comparisons[model_name] += comparisons

            for pair, score_map in positive_scores:
                key = f"{document.source_id}\0{pair[0]}\0{pair[1]}"
                ranked_examples[model_name].append((True, score_map[model_name], key))
            for pair, score_map in negative_scores:
                key = f"{document.source_id}\0{pair[0]}\0{pair[1]}"
                ranked_examples[model_name].append((False, score_map[model_name], key))

        document_outcomes.append(
            _DocumentOutcome(wins=document_wins, comparisons=comparisons)
        )
        details.append({
            "source_id": document.source_id,
            "positives": len(all_edges),
            "known_positives": len(positives),
            "negatives": len(negatives),
            "skipped": None,
        })

    metrics: dict[str, dict[str, Any]] = {}
    for model_name in model_names:
        comparisons = total_comparisons[model_name]
        metrics[model_name] = {
            "auc": total_wins[model_name] / comparisons if comparisons else 0.5,
            "average_precision": _average_precision(ranked_examples[model_name]),
            "pairwise_comparisons": comparisons,
        }

    baseline_names = tuple(name for name in model_names if name != "fvsc_density_shape")
    best_baseline = max(
        baseline_names,
        key=lambda name: (metrics[name]["auc"], name),
    )
    delta = metrics["fvsc_density_shape"]["auc"] - metrics[best_baseline]["auc"]
    ci_low, ci_high = _paired_document_bootstrap(
        document_outcomes,
        candidate="fvsc_density_shape",
        baseline=best_baseline,
        samples=bootstrap_samples,
        seed=seed,
    )
    coverage = positive_known / positive_total if positive_total else 0.0
    comparisons = metrics["fvsc_density_shape"]["pairwise_comparisons"]

    if comparisons < 100 or positive_known < 20 or coverage < 0.5:
        verdict = "insufficient_data"
    elif delta > 0.02 and ci_low > 0.0:
        verdict = "density_shape_leads"
    elif ci_high < 0.0:
        verdict = "simpler_backend_preferred"
    elif abs(delta) <= 0.01:
        verdict = "density_shape_competitive"
    else:
        verdict = "inconclusive"

    return {
        "benchmark": BENCHMARK_VERSION,
        "train_documents": len(train),
        "test_documents": len(test),
        "evaluated_test_documents": len(document_outcomes),
        "train_cutoff": train[-1].observed_at if train else None,
        "positive_pairs_total": positive_total,
        "positive_pairs_known": positive_known,
        "known_positive_coverage": coverage,
        "negative_pairs": negative_total,
        "models": metrics,
        "best_non_density_backend": best_baseline,
        "density_auc_delta_vs_best_backend": delta,
        "paired_document_bootstrap_ci95": [ci_low, ci_high],
        "verdict": verdict,
        "details": details,
        "decision_scope": {
            "canonical_store": "not tested; retain append-only typed evidence with provenance",
            "semantic_backend": "current relation-ranking implementations only",
            "density_matrix_claim": "tests current deterministic materializer, not the whole formalism",
        },
        "limitations": [
            "parser-derived relations are proxy labels, not independent semantic truth",
            "this task emphasizes directed relation prediction, not lexical ambiguity",
            "the density backend still uses deterministic hash-role features",
            "no learned embedding or language-model baseline is included in v1",
            "personal usefulness requires real-vault ratings",
        ],
    }


def evaluate_public_corpus(
    input_path: Path,
    *,
    output_path: Path,
    train_fraction: float = 0.8,
    bootstrap_samples: int = 1000,
    max_threads: int | None = None,
) -> dict[str, Any]:
    """Load an attributed JSONL corpus and run the representation bakeoff."""
    from .natural_language_benchmark import _thread_documents, load_corpus

    records = load_corpus(input_path)
    documents, parser_diagnostics = _thread_documents(records, max_threads=max_threads)
    evaluation = run_representation_bakeoff(
        documents,
        train_fraction=train_fraction,
        bootstrap_samples=bootstrap_samples,
    )
    report = {
        "benchmark": BENCHMARK_VERSION,
        "corpus_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "records": len(records),
        "threads": len({(record.site, record.thread_id) for record in records}),
        "parser_diagnostics": parser_diagnostics,
        "evaluation": evaluation,
        "raw_text_in_report": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-fraction", type=float, default=0.8)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--max-threads", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = evaluate_public_corpus(
        args.input,
        output_path=args.output,
        train_fraction=args.train_fraction,
        bootstrap_samples=args.bootstrap_samples,
        max_threads=args.max_threads,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
