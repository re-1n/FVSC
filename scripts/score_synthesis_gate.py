"""Score a completed public synthesis run from an explicit facet review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.synthesis import (
    FacetObservation,
    evaluate_synthesis_gate,
    score_synthesis_case,
    summarize_synthesis_arm,
)
from fvsc.evaluation.synthesis_fixtures import PUBLIC_SYNTHESIS_FIXTURES


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _read_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise ValueError("refusing to overwrite an existing synthesis score")
    if not output.parent.is_dir():
        raise ValueError("synthesis score parent directory does not exist")
    run = _read_object(args.run)
    review = _read_object(args.review)
    raw_generations = run.get("generations")
    raw_observations = review.get("observations")
    if not isinstance(raw_generations, list) or not isinstance(raw_observations, list):
        raise ValueError("run and review schemas are incomplete")

    generation_by_key = {
        (item.get("case_id"), item.get("arm")): item
        for item in raw_generations
        if isinstance(item, dict)
    }
    observation_by_key = {
        (item.get("case_id"), item.get("arm")): item
        for item in raw_observations
        if isinstance(item, dict)
    }
    expected = {
        (fixture.case_id, arm)
        for fixture in PUBLIC_SYNTHESIS_FIXTURES
        for arm in ("baseline", "coverage")
    }
    if set(generation_by_key) != expected or set(observation_by_key) != expected:
        raise ValueError("run and review must contain every expected case-arm exactly once")

    scores_by_arm = {"baseline": [], "coverage": []}
    for fixture in PUBLIC_SYNTHESIS_FIXTURES:
        for arm in ("baseline", "coverage"):
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
            scores_by_arm[arm].append(score_synthesis_case(fixture, observation))

    baseline = summarize_synthesis_arm("baseline", scores_by_arm["baseline"])
    coverage = summarize_synthesis_arm("coverage", scores_by_arm["coverage"])
    decision = evaluate_synthesis_gate(baseline, coverage)
    result = {
        "baseline": baseline.__dict__,
        "coverage": coverage.__dict__,
        "gate": {"passed": decision.passed, "reasons": list(decision.reasons)},
        "review_id": review.get("review_id"),
        "run_prompt_version": run.get("prompt_version"),
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
