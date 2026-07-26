"""Score the public coverage atlas from explicit synthetic facet review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.coverage_atlas import (
    atlas_fixtures,
    summarize_coverage_atlas,
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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise ValueError("refusing to overwrite an existing atlas score")
    if not output.parent.is_dir():
        raise ValueError("atlas score parent directory does not exist")
    run = _object(args.run)
    review = _object(args.review)
    generations = run.get("generations")
    observations = review.get("observations")
    if not isinstance(generations, list) or not isinstance(observations, list):
        raise ValueError("atlas run and review schemas are incomplete")
    generation_by_key = {
        (item.get("case_id"), item.get("arm")): item
        for item in generations
        if isinstance(item, dict)
    }
    observation_by_key = {
        (item.get("case_id"), item.get("arm")): item
        for item in observations
        if isinstance(item, dict)
    }
    fixtures = atlas_fixtures()
    expected = {
        (fixture.case_id, arm)
        for fixture in fixtures
        for arm in ("baseline", "claim_first")
    }
    if set(generation_by_key) != expected or set(observation_by_key) != expected:
        raise ValueError("atlas run and review must contain each case-arm once")

    scores_by_arm = {"baseline": {}, "claim_first": {}}
    for fixture in fixtures:
        for arm in ("baseline", "claim_first"):
            key = (fixture.case_id, arm)
            raw = observation_by_key[key]
            telemetry = generation_by_key[key].get("telemetry") or {}
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
            scores_by_arm[arm][fixture.case_id] = score_synthesis_case(
                fixture, observation
            )
    arm_summaries = {
        arm: summarize_synthesis_arm(arm, tuple(scores.values()))
        for arm, scores in scores_by_arm.items()
    }
    atlas_summaries = {
        arm: summarize_coverage_atlas(scores)
        for arm, scores in scores_by_arm.items()
    }
    result = {
        "arms": {arm: summary.__dict__ for arm, summary in arm_summaries.items()},
        "atlas": {
            arm: {
                "phenomena": [item.__dict__ for item in summary.phenomena],
                "selected_phenomenon": summary.selected_phenomenon,
                "selection_reason": summary.selection_reason,
            }
            for arm, summary in atlas_summaries.items()
        },
        "review_id": review.get("review_id"),
        "run_prompt_version": run.get("prompt_version"),
        "schema_errors": {
            arm: sum(
                generation_by_key[(fixture.case_id, arm)].get("status")
                == "schema_error"
                for fixture in fixtures
            )
            for arm in ("baseline", "claim_first")
        },
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
