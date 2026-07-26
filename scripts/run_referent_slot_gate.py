"""Run paired v1/referent-aware planned-slot arms on frozen public fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.planned_slot_runner import run_planned_slots
from fvsc.evaluation.planned_slot_synthesis import (
    PLANNED_SLOT_INSTRUCTION,
    PLANNED_SLOT_PROMPT_VERSION,
    REFERENT_AWARE_SLOT_INSTRUCTION,
    REFERENT_AWARE_SLOT_PROMPT_VERSION,
)
from fvsc.evaluation.referent_slot_gate_fixtures import (
    PUBLIC_REFERENT_SLOT_GATE_FIXTURES,
    REFERENT_PLAN_BY_CASE,
)
from fvsc.integrations.ollama import OllamaInterpretationBackend


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-digest", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout", type=float, default=900.0)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    output = args.output.resolve()
    if output.exists() or not output.parent.is_dir():
        raise ValueError("referent-slot output must be new with an existing parent")
    probe = OllamaInterpretationBackend(
        model=args.model,
        model_digest=args.model_digest,
        host=args.host,
    )
    identity = probe.model_identity()
    if identity is None or identity.digest != args.model_digest:
        raise RuntimeError("frozen Ollama model identity is unavailable")

    def factory(prompt, version):
        return OllamaInterpretationBackend(
            model=args.model,
            model_digest=args.model_digest,
            host=args.host,
            temperature=0.0,
            seed=args.seed,
            num_ctx=8192,
            num_predict=768,
            timeout=args.timeout,
            system_prompt=prompt,
            prompt_version=version,
        )

    arms = {
        "v1": (PLANNED_SLOT_INSTRUCTION, PLANNED_SLOT_PROMPT_VERSION),
        "referent": (
            REFERENT_AWARE_SLOT_INSTRUCTION,
            REFERENT_AWARE_SLOT_PROMPT_VERSION,
        ),
    }
    generations = []
    for index, fixture in enumerate(PUBLIC_REFERENT_SLOT_GATE_FIXTURES):
        order = ("v1", "referent") if index % 2 == 0 else ("referent", "v1")
        plan = {fixture.case_id: REFERENT_PLAN_BY_CASE[fixture.case_id]}
        for arm in order:
            instruction, version = arms[arm]
            generated = run_planned_slots(
                (fixture,),
                backend_factory=factory,
                plans_by_case=plan,
                instruction=instruction,
                prompt_version=version,
            )[0]
            row = generated.to_dict()
            row["arm"] = arm
            generations.append(row)
    artifact = {
        "fixture_ids": [
            fixture.case_id for fixture in PUBLIC_REFERENT_SLOT_GATE_FIXTURES
        ],
        "generations": generations,
        "model_identity": identity.to_dict(),
        "prompt_versions": {
            arm: version for arm, (_, version) in arms.items()
        },
        "seed": args.seed,
        "temperature": 0.0,
    }
    output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
