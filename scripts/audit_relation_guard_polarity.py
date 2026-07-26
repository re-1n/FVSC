"""Audit S6 source-cue eligibility on frozen polarity/modality minimal pairs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.planned_slot_synthesis import (
    FrozenQuestionPlan,
    PlannedRequirement,
)
from fvsc.evaluation.relation_guard_polarity_fixtures import (
    PUBLIC_RELATION_GUARD_POLARITY_FIXTURES,
)
from fvsc.evaluation.relation_support_guard import PUBLIC_RELATION_SUPPORT_GUARD
from fvsc.evaluation.synthesis import SyntheticSource


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    rows = []
    for fixture in PUBLIC_RELATION_GUARD_POLARITY_FIXTURES:
        plan = FrozenQuestionPlan(
            fixture.case_id,
            (PlannedRequirement("R1", fixture.requirement),),
        )
        candidate = PUBLIC_RELATION_SUPPORT_GUARD.compile(
            plan,
            (SyntheticSource("S1", fixture.source_text),),
        )[0]
        eligible = candidate.eligible_source_labels == ("S1",)
        rows.append(
            {
                "case_id": fixture.case_id,
                "contrast": fixture.contrast,
                "eligible": eligible,
                "passed": eligible == fixture.should_be_eligible,
                "relation": fixture.relation,
            }
        )
    artifact = {
        "audit": "public-s6-polarity-modality-v1",
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
