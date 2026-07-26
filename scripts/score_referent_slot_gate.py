"""Score the paired public referent-aware planned-slot gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.referent_slot_gate_fixtures import (
    PUBLIC_REFERENT_SLOT_GATE_FIXTURES,
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
        for fixture in PUBLIC_REFERENT_SLOT_GATE_FIXTURES
        for arm in ("v1", "referent")
    }
    if set(generation_by_key) != expected or set(observation_by_key) != expected:
        raise ValueError("run and review must contain every case-arm exactly once")

    scores_by_arm = {"v1": [], "referent": []}
    schema_errors = {"v1": 0, "referent": 0}
    for fixture in PUBLIC_REFERENT_SLOT_GATE_FIXTURES:
        for arm in ("v1", "referent"):
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
                promoted_role_facet_ids=tuple(
                    raw.get("promoted_role_facet_ids", ())
                ),
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
    candidate = summaries["referent"]
    baseline = summaries["v1"]
    safety_passed = (
        schema_errors["referent"] == 0
        and candidate.mean_citation_correctness == 1.0
        and candidate.abstention_accuracy == 1.0
        and candidate.mean_unsupported_facet_rate == 0.0
        and candidate.prohibited_violations == 0
        and candidate.role_violations == 0
    )
    recall_passed = (
        candidate.macro_required_recall is not None
        and baseline.macro_required_recall is not None
        and candidate.macro_required_recall >= baseline.macro_required_recall
        and candidate.macro_required_recall >= 0.917
    )
    repaired_v1_miss = any(
        old.required_recall is not None
        and new.required_recall is not None
        and new.required_recall > old.required_recall
        for old, new in zip(scores_by_arm["v1"], scores_by_arm["referent"])
    )
    result = {
        "arms": {arm: summary.__dict__ for arm, summary in summaries.items()},
        "decision": {
            "passed": safety_passed and recall_passed and repaired_v1_miss,
            "recall_passed": recall_passed,
            "repaired_v1_miss": repaired_v1_miss,
            "safety_passed": safety_passed,
        },
        "review_id": review.get("review_id"),
        "schema_errors": schema_errors,
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
