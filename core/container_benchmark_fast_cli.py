"""Resource-bounded CLI for the cached explicit-container benchmark.

The scientific comparison uses one shared deterministic encoder dimension for both the
legacy density-only and container-density backends.  Dimension 16 is intentionally
fixed for the first full-corpus falsification run so dense per-evidence operators fit
within ordinary CI resources.
"""
from __future__ import annotations

import json
from typing import Sequence

from . import container_benchmark_cached as benchmark
from .container_materializer_fast import materialize_fast_container_ledger
from .materializer import DeterministicEvidenceEncoder


BENCHMARK_DIM = 16
_ENCODER = DeterministicEvidenceEncoder(
    dim=BENCHMARK_DIM,
    version="deterministic-role-baseline-dim16-v1",
)


def main(argv: Sequence[str] | None = None) -> int:
    args = benchmark._build_parser().parse_args(argv)
    original_materializer = benchmark.materialize_container_ledger
    original_builder = benchmark.build_runtime_from_sources

    def build_dimensional_runtime(sources, *, encoder=None):
        return original_builder(sources, encoder=encoder or _ENCODER)

    benchmark.materialize_container_ledger = materialize_fast_container_ledger
    benchmark.build_runtime_from_sources = build_dimensional_runtime
    try:
        result = benchmark.evaluate_public_corpus(
            args.input,
            output_path=args.output,
            train_fraction=args.train_fraction,
            bootstrap_samples=args.bootstrap_samples,
            max_threads=args.max_threads,
            max_positives_per_document=args.max_positives_per_document,
            max_negatives_per_document=args.max_negatives_per_document,
        )
        evaluation = result["evaluation"]
        evaluation["resource_bounds"]["semantic_dim"] = BENCHMARK_DIM
        evaluation["container_snapshot"]["semantic_dim"] = BENCHMARK_DIM
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    finally:
        benchmark.materialize_container_ledger = original_materializer
        benchmark.build_runtime_from_sources = original_builder


if __name__ == "__main__":
    raise SystemExit(main())
