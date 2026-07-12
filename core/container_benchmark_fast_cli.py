"""Single-process CLI wiring the cached bakeoff to the fast container materializer."""
from __future__ import annotations

from typing import Sequence

from . import container_benchmark_cached as benchmark
from .container_materializer_fast import materialize_fast_container_ledger


def main(argv: Sequence[str] | None = None) -> int:
    original = benchmark.materialize_container_ledger
    benchmark.materialize_container_ledger = materialize_fast_container_ledger
    try:
        return benchmark.main(argv)
    finally:
        benchmark.materialize_container_ledger = original


if __name__ == "__main__":
    raise SystemExit(main())
