"""Score the paired raw/typed-relation-guard public gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.relation_guard_gate_fixtures import (
    PUBLIC_RELATION_GUARD_GATE_FIXTURES,
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
    expected = {
        (fixture.case_id, arm)
        for fixture in PUBLIC_RELATION_GUARD_GATE_FIXTURES
        for arm in ("v1", "relation_guard")
    }
    if set(generation_by_key) != expected or set(observation_by_key) != expected:
        raise ValueError("run and review must contain every case-arm exactly once")

    scores_by_arm = {"v1": [], "relation_guard": []}
    schema_errors = {"v1": 0, "relation_guard": 0}
    for fixture in PUBLIC_RELATION_GUARD_GATE_FIXTURES:
        for arm in ("v1", "relation_guard"):
            key = (fixture.case_id, arm)
            raw = observation_by_key[key]
            generation = generation_by_key[key]
            telemetry = generation.get("telemetry") or {}
            observation = FacetObservation(
                expressed_facet_ids=tuple(raw.get("expressed_facet_ids", ())),
                citations_by_facet={
                    facet_id: tuple(labels)
                    for facet_id, labels in raw.get("citations_by_facet", {}).items()
                },
                promoted_role_facet_ids=(),
                unsupported_facet_count=raw.get("unsupported_facet_count", 0),
                abstained=raw.get("abstained", False),
                prompt_tokens=telemetry.get("prompt_eval_count"),
                output_tokens=telemetry.get("eval_count"),
                latency_seconds=telemetry.get("wall_seconds"),
            )
            scores_by_arm[arm].append(score_synthesis_case(fixture, observation))
            schema_errors[arm] += generation.get("status") == "schema_error"
    summaries = {
        arm: summarize_synthesis_arm("planned_slot", scores)
        for arm, scores in scores_by_arm.items()
    }
    raw = summaries["v1"]
    guarded = summaries["relation_guard"]
    corrected_safety_error = any(
        (not old.abstention_correct and new.abstention_correct)
        or old.prohibited_violations > new.prohibited_violations
        or old.unsupported_facet_rate > new.unsupported_facet_rate
        for old, new in zip(scores_by_arm["v1"], scores_by_arm["relation_guard"])
    )
    passed = (
        schema_errors == {"v1": 0, "relation_guard": 0}
        and guarded.macro_required_recall == raw.macro_required_recall == 1.0
        and guarded.mean_citation_correctness == 1.0
        and guarded.abstention_accuracy == 1.0
        and guarded.mean_unsupported_facet_rate == 0.0
        and guarded.prohibited_violations == 0
        and guarded.role_violations == 0
        and corrected_safety_error
    )
    result = {
        "arms": {arm: summary.__dict__ for arm, summary in summaries.items()},
        "decision": {
            "corrected_safety_error": corrected_safety_error,
            "passed": passed,
        },
        "review_id": review.get("review_id"),
        "schema_errors": schema_errors,
        "shared_generation_count": run.get("generation_count"),
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
