#!/usr/bin/env python3
"""Print the frozen public semantic schema-capacity probe as JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fvsc.evaluation.semantic_probe import load_semantic_probe, run_semantic_capacity_probe


DEFAULT_FIXTURE = Path("data/fixtures/semantic_capacity_probe_v1.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    args = parser.parse_args()
    report = run_semantic_capacity_probe(load_semantic_probe(args.fixture))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
