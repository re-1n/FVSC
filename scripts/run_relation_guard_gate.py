"""Run v1 generation and derive its typed relation-guarded paired arm."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.planned_slot_runner import (
    guard_planned_slot_generation,
    run_planned_slots,
)
from fvsc.evaluation.planned_slot_synthesis import PLANNED_SLOT_PROMPT_VERSION
from fvsc.evaluation.relation_guard_gate_fixtures import (
    PUBLIC_RELATION_GUARD_GATE_FIXTURES,
    RELATION_ELIGIBLE_LABELS_BY_CASE,
    RELATION_GUARD_PLAN_BY_CASE,
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
        raise ValueError("relation-guard output must be new with an existing parent")
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

    raw_generations = run_planned_slots(
        PUBLIC_RELATION_GUARD_GATE_FIXTURES,
        backend_factory=factory,
        plans_by_case=RELATION_GUARD_PLAN_BY_CASE,
    )
    generations = []
    for raw in raw_generations:
        raw_row = raw.to_dict()
        raw_row["arm"] = "v1"
        generations.append(raw_row)
        guarded = guard_planned_slot_generation(
            raw,
            RELATION_GUARD_PLAN_BY_CASE[raw.case_id],
            RELATION_ELIGIBLE_LABELS_BY_CASE[raw.case_id],
        )
        guarded_row = guarded.to_dict()
        guarded_row["arm"] = "relation_guard"
        generations.append(guarded_row)
    artifact = {
        "fixture_ids": [
            fixture.case_id for fixture in PUBLIC_RELATION_GUARD_GATE_FIXTURES
        ],
        "generation_count": len(raw_generations),
        "generations": generations,
        "guard": "public-english-explicit-relation-cues-v1",
        "model_identity": identity.to_dict(),
        "prompt_version": PLANNED_SLOT_PROMPT_VERSION,
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
