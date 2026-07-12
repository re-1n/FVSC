"""Resource-bounded ablation for the explicit FVSC container hypothesis.

This is the production benchmark path for ContainerCore v1.  It preserves the frozen
chronological split and candidate models from :mod:`core.container_benchmark`, but uses
:class:`core.container_query.ContainerQueryIndex` so each root/context neighbourhood is
expanded once instead of once per candidate pair.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

import numpy as np

from .container_benchmark import (
    _DocumentOutcome,
    _average_precision,
    _edge_rows,
    _paired_document_bootstrap,
    _stable_random_score,
    _stable_sample_pairs,
)
from .container_core import ContainerSnapshot, materialize_container_ledger
from .container_query import ContainerQueryIndex
from .pilot_batch import build_runtime_from_sources
from .pilot_evaluation import HeldoutDocument, chronological_split
from .representation_bakeoff import SparseGraphState
from .semantic_metrics import operator_inclusion


BENCHMARK_VERSION = "fvsc-explicit-container-cached-bakeoff-v2"
CONTAINER_MAX_DEPTH = 2
_EPS = 1e-12
RankedExample = tuple[bool, float, str]


@dataclass(frozen=True)
class CachedContainerSuite:
    graph: SparseGraphState
    runtime: Any
    containers: ContainerSnapshot
    query: ContainerQueryIndex
    known_terms: frozenset[str]
    _score_cache: dict[tuple[str, str], dict[str, float]] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )

    MODEL_NAMES = (
        "direct_graph",
        "conditional_graph",
        "ppmi_graph",
        "fvsc_density_shape",
        "container_structure",
        "container_density",
        "container_hybrid",
        "random",
    )

    @classmethod
    def fit(
        cls,
        documents: Sequence[HeldoutDocument],
        *,
        branch_limit: int = 12,
        max_paths_per_target: int = 2,
    ) -> "CachedContainerSuite":
        graph = SparseGraphState.fit(documents)
        runtime = build_runtime_from_sources([document.as_source() for document in documents])
        containers = materialize_container_ledger(runtime.ledger, encoder=runtime.encoder)
        query = ContainerQueryIndex(
            containers,
            branch_limit=branch_limit,
            max_paths_per_target=max_paths_per_target,
        )
        runtime_terms = frozenset(item.term for item in runtime.snapshot.concepts)
        container_terms = frozenset(item.container_id for item in containers.containers)
        return cls(
            graph=graph,
            runtime=runtime,
            containers=containers,
            query=query,
            known_terms=frozenset(graph.known_terms & runtime_terms & container_terms),
        )

    def scores(self, parent: str, child: str) -> dict[str, float]:
        key = (str(parent), str(child))
        cached = self._score_cache.get(key)
        if cached is not None:
            return dict(cached)
        parent_concept = self.runtime.get(parent)
        child_concept = self.runtime.get(child)
        if parent_concept is None or child_concept is None:
            raise KeyError("pair contains a term absent from the fitted representations")

        projection = self.query.project(parent, child, max_depth=CONTAINER_MAX_DEPTH)
        structure = projection.path_strength
        if projection.state.is_empty:
            container_density = 0.0
        else:
            activation = self.query.activate(parent, max_depth=CONTAINER_MAX_DEPTH)
            if activation.state.is_empty:
                container_density = 0.0
            else:
                container_density = float(np.clip(
                    projection.path_strength
                    * operator_inclusion(projection.state, activation.state),
                    0.0,
                    1.0,
                ))
        result = {
            "direct_graph": self.graph.direct(parent, child),
            "conditional_graph": self.graph.conditional(parent, child),
            "ppmi_graph": self.graph.ppmi(parent, child),
            "fvsc_density_shape": operator_inclusion(child_concept.state, parent_concept.state),
            "container_structure": structure,
            "container_density": container_density,
            "container_hybrid": float(np.clip(
                0.5 * structure + 0.5 * container_density,
                0.0,
                1.0,
            )),
            "random": _stable_random_score(parent, child),
        }
        self._score_cache[key] = result
        return dict(result)


def run_cached_container_bakeoff(
    documents: Sequence[HeldoutDocument],
    *,
    train_fraction: float = 0.8,
    bootstrap_samples: int = 1000,
    seed: int = 20260712,
    max_positives_per_document: int = 40,
    max_negatives_per_document: int = 40,
    branch_limit: int = 12,
    max_paths_per_target: int = 2,
    record_runtime: bool = False,
) -> dict[str, Any]:
    """Compare explicit containers and simple baselines on one frozen split."""
    if bootstrap_samples < 100:
        raise ValueError("bootstrap_samples must be at least 100")
    if max_positives_per_document < 1 or max_negatives_per_document < 1:
        raise ValueError("pair limits must be positive")
    started = time.perf_counter()
    train, test = chronological_split(documents, train_fraction=train_fraction)
    suite = CachedContainerSuite.fit(
        train,
        branch_limit=branch_limit,
        max_paths_per_target=max_paths_per_target,
    )
    model_names = suite.MODEL_NAMES
    total_wins = {name: 0.0 for name in model_names}
    total_comparisons = {name: 0 for name in model_names}
    ranked_examples: dict[str, list[RankedExample]] = {name: [] for name in model_names}
    document_outcomes: list[_DocumentOutcome] = []
    positive_total = 0
    positive_known = 0
    sampled_positive_total = 0
    sampled_negative_total = 0
    asymmetric_positive_pairs = 0
    evaluated_positive_pairs = 0
    details: list[dict[str, Any]] = []

    for document in test:
        all_edges = _edge_rows(document)
        positive_total += len(all_edges)
        known_positives = [
            (parent, child)
            for parent, child, _weight in all_edges
            if parent in suite.known_terms and child in suite.known_terms
        ]
        positive_known += len(known_positives)
        positives = _stable_sample_pairs(
            known_positives,
            source_id=document.source_id,
            kind="positive",
            limit=max_positives_per_document,
        )
        sampled_positive_total += len(positives)
        if not positives:
            details.append({
                "source_id": document.source_id,
                "positives": len(all_edges),
                "known_positives": 0,
                "sampled_positives": 0,
                "sampled_negatives": 0,
                "skipped": "no_known_positive_pairs",
            })
            continue

        terms = sorted({
            term
            for parent, child, _weight in all_edges
            for term in (parent, child)
            if term in suite.known_terms
        })
        positive_set = set(known_positives)
        negative_candidates = [
            (parent, child)
            for parent in terms
            for child in terms
            if parent != child and (parent, child) not in positive_set
        ]
        negatives = _stable_sample_pairs(
            negative_candidates,
            source_id=document.source_id,
            kind="negative",
            limit=max_negatives_per_document,
        )
        sampled_negative_total += len(negatives)
        if not negatives:
            details.append({
                "source_id": document.source_id,
                "positives": len(all_edges),
                "known_positives": len(known_positives),
                "sampled_positives": len(positives),
                "sampled_negatives": 0,
                "skipped": "no_candidate_negatives",
            })
            continue

        positive_scores = [(pair, suite.scores(*pair)) for pair in positives]
        negative_scores = [(pair, suite.scores(*pair)) for pair in negatives]
        comparisons = len(positives) * len(negatives)
        document_wins: dict[str, float] = {}

        for pair, score_map in positive_scores:
            reverse = suite.query.structure_score(
                pair[1],
                pair[0],
                max_depth=CONTAINER_MAX_DEPTH,
            )
            asymmetric_positive_pairs += int(
                abs(score_map["container_structure"] - reverse) > _EPS
            )
            evaluated_positive_pairs += 1

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
                ranked_examples[model_name].append((
                    True,
                    score_map[model_name],
                    f"{document.source_id}\0{pair[0]}\0{pair[1]}",
                ))
            for pair, score_map in negative_scores:
                ranked_examples[model_name].append((
                    False,
                    score_map[model_name],
                    f"{document.source_id}\0{pair[0]}\0{pair[1]}",
                ))

        document_outcomes.append(_DocumentOutcome(
            wins=document_wins,
            comparisons=comparisons,
        ))
        details.append({
            "source_id": document.source_id,
            "positives": len(all_edges),
            "known_positives": len(known_positives),
            "sampled_positives": len(positives),
            "sampled_negatives": len(negatives),
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

    container_names = ("container_structure", "container_density", "container_hybrid")
    non_container_names = (
        "direct_graph",
        "conditional_graph",
        "ppmi_graph",
        "fvsc_density_shape",
        "random",
    )
    best_container = max(container_names, key=lambda name: (metrics[name]["auc"], name))
    best_non_container = max(
        non_container_names,
        key=lambda name: (metrics[name]["auc"], name),
    )
    delta = metrics[best_container]["auc"] - metrics[best_non_container]["auc"]
    ci_low, ci_high = _paired_document_bootstrap(
        document_outcomes,
        candidate=best_container,
        baseline=best_non_container,
        samples=bootstrap_samples,
        seed=seed,
    )
    coverage = positive_known / positive_total if positive_total else 0.0
    comparisons = metrics[best_container]["pairwise_comparisons"]
    if comparisons < 100 or positive_known < 20 or coverage < 0.5:
        verdict = "insufficient_data"
    elif delta > 0.02 and ci_low > 0.0:
        verdict = "container_model_leads"
    elif ci_high < 0.0:
        verdict = "simpler_backend_preferred"
    elif abs(delta) <= 0.01:
        verdict = "container_model_competitive"
    else:
        verdict = "inconclusive"

    result: dict[str, Any] = {
        "benchmark": BENCHMARK_VERSION,
        "train_documents": len(train),
        "test_documents": len(test),
        "evaluated_test_documents": len(document_outcomes),
        "train_cutoff": train[-1].observed_at if train else None,
        "positive_pairs_total": positive_total,
        "positive_pairs_known": positive_known,
        "sampled_positive_pairs": sampled_positive_total,
        "sampled_negative_pairs": sampled_negative_total,
        "known_positive_coverage": coverage,
        "models": metrics,
        "best_container_backend": best_container,
        "best_non_container_backend": best_non_container,
        "container_auc_delta_vs_best_non_container": delta,
        "paired_document_bootstrap_ci95": [ci_low, ci_high],
        "asymmetric_positive_pair_rate": (
            asymmetric_positive_pairs / evaluated_positive_pairs
            if evaluated_positive_pairs else 0.0
        ),
        "container_snapshot": {
            "version": suite.containers.version,
            "containers": suite.containers.container_count,
            "embeddings": suite.containers.embedding_count,
            "query_edges": suite.query.edge_count,
            "snapshot_id": suite.containers.snapshot_id,
        },
        "resource_bounds": {
            "max_positives_per_document": max_positives_per_document,
            "max_negatives_per_document": max_negatives_per_document,
            "branch_limit": branch_limit,
            "max_paths_per_target": max_paths_per_target,
            "max_depth": CONTAINER_MAX_DEPTH,
        },
        "verdict": verdict,
        "details": details,
        "decision_scope": {
            "canonical_store": "not tested; append-only evidence ledger is retained",
            "container_structure": "cached explicit asymmetric paths",
            "density_without_containers": "current deterministic FVSC materializer",
            "density_with_containers": "local child state projected through explicit path operators",
        },
        "limitations": [
            "parser-derived relations remain proxy labels until blinded manual audit",
            "pair candidates are deterministically capped per test document",
            "v1 projection operators are deterministic rather than learned",
            "the strongest path is used for state projection",
            "relation ranking does not exhaust contextual polysemy or order effects",
            "personal usefulness still requires real-vault ratings",
        ],
    }
    if record_runtime:
        result["runtime_seconds"] = time.perf_counter() - started
    return result


def evaluate_public_corpus(
    input_path: Path,
    *,
    output_path: Path,
    train_fraction: float = 0.8,
    bootstrap_samples: int = 1000,
    max_threads: int | None = None,
    max_positives_per_document: int = 40,
    max_negatives_per_document: int = 40,
) -> dict[str, Any]:
    from .natural_language_benchmark import _thread_documents, load_corpus

    records = load_corpus(input_path)
    documents, parser_diagnostics = _thread_documents(records, max_threads=max_threads)
    evaluation = run_cached_container_bakeoff(
        documents,
        train_fraction=train_fraction,
        bootstrap_samples=bootstrap_samples,
        max_positives_per_document=max_positives_per_document,
        max_negatives_per_document=max_negatives_per_document,
        record_runtime=True,
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
    parser.add_argument("--max-positives-per-document", type=int, default=40)
    parser.add_argument("--max-negatives-per-document", type=int, default=40)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = evaluate_public_corpus(
        args.input,
        output_path=args.output,
        train_fraction=args.train_fraction,
        bootstrap_samples=args.bootstrap_samples,
        max_threads=args.max_threads,
        max_positives_per_document=args.max_positives_per_document,
        max_negatives_per_document=args.max_negatives_per_document,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
