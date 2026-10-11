"""Run the deterministic public answer-slot boundary gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.answer_slot_boundaries import compile_answer_slot_boundaries
from fvsc.evaluation.answer_slot_gate_fixtures import (
    PUBLIC_ANSWER_SLOT_GATE_FIXTURES,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    rows = []
    passed = True
    for fixture in PUBLIC_ANSWER_SLOT_GATE_FIXTURES:
        plan = compile_answer_slot_boundaries(fixture.question)
        actual_roles = tuple(slot.role for slot in plan.slots)
        case_passed = (
            plan.boundary_kind == fixture.boundary_kind
            and actual_roles == fixture.expected_roles
        )
        passed = passed and case_passed
        rows.append(
            {
                "case_id": fixture.case_id,
                "question": fixture.question,
                "boundary_kind": plan.boundary_kind,
                "roles": list(actual_roles),
                "passed": case_passed,
            }
        )
    artifact = {
        "gate": "public-answer-slot-boundaries-v1",
        "passed": passed,
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
            raise ValueError("output path must be new with an existing parent")
        output.write_text(rendered + "\n", encoding="utf-8")
        print(output)
    else:
        print(rendered)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
