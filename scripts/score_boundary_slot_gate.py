"""Score a reviewed boundary-compiled planned-slot synthesis run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.boundary_slot_gate_fixtures import (
    PUBLIC_BOUNDARY_SLOT_GATE_FIXTURES,
)
from fvsc.evaluation.synthesis import (
    FacetObservation,
    score_synthesis_case,
    summarize_synthesis_arm,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    output = args.output.resolve()
    if output.exists() or not output.parent.is_dir():
        raise ValueError("score output must be new with an existing parent")
    run = _object(args.run)
    review = _object(args.review)
    generations = run.get("generations")
    observations = review.get("observations")
    if not isinstance(generations, list) or not isinstance(observations, list):
        raise ValueError("run and review schemas are incomplete")
    generation_by_case = {
        item.get("case_id"): item for item in generations if isinstance(item, dict)
    }
    observation_by_case = {
        item.get("case_id"): item for item in observations if isinstance(item, dict)
    }
    expected = {fixture.case_id for fixture in PUBLIC_BOUNDARY_SLOT_GATE_FIXTURES}
    if set(generation_by_case) != expected or set(observation_by_case) != expected:
        raise ValueError("run and review must contain each frozen case exactly once")

    scores = []
    for fixture in PUBLIC_BOUNDARY_SLOT_GATE_FIXTURES:
        raw = observation_by_case[fixture.case_id]
        telemetry = generation_by_case[fixture.case_id].get("telemetry") or {}
        observation = FacetObservation(
            expressed_facet_ids=tuple(raw.get("expressed_facet_ids", ())),
            citations_by_facet={
                facet_id: tuple(labels)
                for facet_id, labels in raw.get("citations_by_facet", {}).items()
            },
            promoted_role_facet_ids=tuple(
                raw.get("promoted_role_facet_ids", ())
            ),
            unsupported_facet_count=raw.get("unsupported_facet_count", 0),
            abstained=raw.get("abstained", False),
            prompt_tokens=telemetry.get("prompt_eval_count"),
            output_tokens=telemetry.get("eval_count"),
            latency_seconds=telemetry.get("wall_seconds"),
        )
        scores.append(score_synthesis_case(fixture, observation))

    summary = summarize_synthesis_arm("planned_slot", scores)
    schema_errors = sum(
        item.get("status") == "schema_error" for item in generation_by_case.values()
    )
    result = {
        "diagnostic_only": True,
        "review_id": review.get("review_id"),
        "run_prompt_version": run.get("prompt_version"),
        "schema_errors": schema_errors,
        "summary": summary.__dict__,
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
