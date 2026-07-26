"""Score the held-out requirement-coverage gate from explicit facet review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.requirement_gate_fixtures import PUBLIC_REQUIREMENT_GATE_FIXTURES
from fvsc.evaluation.requirement_synthesis import evaluate_requirement_gate
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
        raise ValueError("refusing to overwrite an existing requirement score")
    if not output.parent.is_dir():
        raise ValueError("requirement score parent directory does not exist")
    run = _object(args.run)
    review = _object(args.review)
    generations = run.get("generations")
    observations = review.get("observations")
    if not isinstance(generations, list) or not isinstance(observations, list):
        raise ValueError("requirement run and review schemas are incomplete")
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
        for fixture in PUBLIC_REQUIREMENT_GATE_FIXTURES
        for arm in ("baseline", "requirement_coverage")
    }
    if set(generation_by_key) != expected or set(observation_by_key) != expected:
        raise ValueError("run and review must contain every held-out case-arm")
    scores = {"baseline": [], "requirement_coverage": []}
    for fixture in PUBLIC_REQUIREMENT_GATE_FIXTURES:
        for arm in ("baseline", "requirement_coverage"):
            key = (fixture.case_id, arm)
            raw = observation_by_key[key]
            telemetry = generation_by_key[key].get("telemetry") or {}
            observation = FacetObservation(
                expressed_facet_ids=tuple(raw.get("expressed_facet_ids", ())),
                citations_by_facet={
                    facet_id: tuple(labels)
                    for facet_id, labels in raw.get("citations_by_facet", {}).items()
                },
                unsupported_facet_count=raw.get("unsupported_facet_count", 0),
                abstained=raw.get("abstained", False),
                prompt_tokens=telemetry.get("prompt_eval_count"),
                output_tokens=telemetry.get("eval_count"),
                latency_seconds=telemetry.get("wall_seconds"),
            )
            scores[arm].append(score_synthesis_case(fixture, observation))
    baseline = summarize_synthesis_arm("baseline", scores["baseline"])
    requirement = summarize_synthesis_arm(
        "requirement_coverage", scores["requirement_coverage"]
    )
    schema_errors = sum(
        generation_by_key[(fixture.case_id, "requirement_coverage")].get("status")
        == "schema_error"
        for fixture in PUBLIC_REQUIREMENT_GATE_FIXTURES
    )
    status_errors = sum(
        generation_by_key[(fixture.case_id, "requirement_coverage")].get("status")
        != ("insufficient" if fixture.should_abstain else "answered")
        for fixture in PUBLIC_REQUIREMENT_GATE_FIXTURES
    )
    decision = evaluate_requirement_gate(
        baseline,
        requirement,
        schema_error_count=schema_errors,
        status_error_count=status_errors,
    )
    result = {
        "baseline": baseline.__dict__,
        "gate": {"passed": decision.passed, "reasons": list(decision.reasons)},
        "requirement_coverage": requirement.__dict__,
        "review_id": review.get("review_id"),
        "run_prompt_version": run.get("prompt_version"),
        "schema_errors": schema_errors,
        "status_errors": status_errors,
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
