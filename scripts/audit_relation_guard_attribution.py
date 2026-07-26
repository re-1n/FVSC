"""Audit surface S6 eligibility against frozen F1 expression boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.relation_guard_attribution_fixtures import (
    PUBLIC_RELATION_GUARD_ATTRIBUTION_FIXTURES,
)
from fvsc.evaluation.relation_support_guard import source_affirms_relation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    rows = []
    for fixture in PUBLIC_RELATION_GUARD_ATTRIBUTION_FIXTURES:
        eligible = source_affirms_relation(fixture.text, fixture.relation)
        rows.append(
            {
                "case_id": fixture.case_id,
                "directly_eligible": eligible,
                "passed": eligible == fixture.should_be_directly_eligible,
                "relation": fixture.relation,
                "span_count": len(fixture.expression_spans),
            }
        )
    artifact = {
        "audit": "public-f1-s6-expression-boundaries-v1",
        "passed": all(row["passed"] for row in rows),
        "passed_cases": sum(row["passed"] for row in rows),
        "total_cases": len(rows),
        "cases": rows,
    }
    rendered = json.dumps(
        artifact, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
    )
    if args.output:
        output = args.output.resolve()
        if output.exists() or not output.parent.is_dir():
            raise ValueError("output must be new with an existing parent")
        output.write_text(rendered + "\n", encoding="utf-8")
        print(output)
    else:
        print(rendered)
    return 0 if artifact["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
