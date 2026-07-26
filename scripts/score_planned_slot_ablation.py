"""Score the controlled planned-slot replay, including safe sentinel tolerance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.planned_slot_synthesis import normalize_empty_claim_sentinel
from fvsc.evaluation.requirement_gate_fixtures import PUBLIC_REQUIREMENT_GATE_FIXTURES
from fvsc.evaluation.synthesis import (
    FacetObservation,
    score_synthesis_case,
    summarize_synthesis_arm,
)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    output = args.output.resolve()
    if output.exists() or not output.parent.is_dir():
        raise ValueError("planned-slot score path must be new with an existing parent")
    run = json.loads(args.run.read_text(encoding="utf-8"))
    review = json.loads(args.review.read_text(encoding="utf-8"))
    generations = {item["case_id"]: item for item in run["generations"]}
    observations = {item["case_id"]: item for item in review["observations"]}
    expected = {item.case_id for item in PUBLIC_REQUIREMENT_GATE_FIXTURES}
    if set(generations) != expected or set(observations) != expected:
        raise ValueError("planned-slot run and review must cover every case")
    scores = []
    strict_schema_errors = 0
    tolerant_schema_errors = 0
    for fixture in PUBLIC_REQUIREMENT_GATE_FIXTURES:
        generation = generations[fixture.case_id]
        strict_schema_errors += generation["status"] == "schema_error"
        if generation["status"] == "schema_error":
            slots = generation.get("slots", [])
            safely_unsupported = bool(slots) and all(
                slot.get("status") == "unsupported"
                and normalize_empty_claim_sentinel(
                    slot.get("status"), slot.get("claim")
                )
                is None
                for slot in slots
            )
            tolerant_schema_errors += not safely_unsupported
        raw = observations[fixture.case_id]
        telemetry = generation.get("telemetry") or {}
        scores.append(
            score_synthesis_case(
                fixture,
                FacetObservation(
                    tuple(raw.get("expressed_facet_ids", ())),
                    {
                        key: tuple(value)
                        for key, value in raw.get("citations_by_facet", {}).items()
                    },
                    unsupported_facet_count=raw.get("unsupported_facet_count", 0),
                    abstained=raw.get("abstained", False),
                    prompt_tokens=telemetry.get("prompt_eval_count"),
                    output_tokens=telemetry.get("eval_count"),
                    latency_seconds=telemetry.get("wall_seconds"),
                ),
            )
        )
    summary = summarize_synthesis_arm("planned_slot", scores)
    result = {
        "review_id": review.get("review_id"),
        "strict_schema_errors": strict_schema_errors,
        "summary_after_safe_empty_sentinel_normalization": summary.__dict__,
        "tolerant_schema_errors": tolerant_schema_errors,
    }
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
