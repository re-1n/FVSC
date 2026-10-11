"""Run the held-out boundary-compiled planned-slot synthesis gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.boundary_slot_gate_fixtures import (
    BOUNDARY_PLAN_BY_CASE,
    PUBLIC_BOUNDARY_SLOT_GATE_FIXTURES,
)
from fvsc.evaluation.planned_slot_runner import run_planned_slots
from fvsc.evaluation.planned_slot_synthesis import PLANNED_SLOT_PROMPT_VERSION
from fvsc.integrations.ollama import OllamaInterpretationBackend


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-digest", required=True)
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout", type=float, default=900.0)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    output = args.output.resolve()
    if output.exists() or not output.parent.is_dir():
        raise ValueError("boundary-slot output path must be new with an existing parent")
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

    generations = run_planned_slots(
        PUBLIC_BOUNDARY_SLOT_GATE_FIXTURES,
        backend_factory=factory,
        plans_by_case=BOUNDARY_PLAN_BY_CASE,
    )
    artifact = {
        "fixture_ids": [
            fixture.case_id for fixture in PUBLIC_BOUNDARY_SLOT_GATE_FIXTURES
        ],
        "generations": [item.to_dict() for item in generations],
        "model_identity": identity.to_dict(),
        "prompt_version": PLANNED_SLOT_PROMPT_VERSION,
        "review_template": [
            {
                "abstained": None,
                "case_id": item.case_id,
                "citations_by_facet": {},
                "expressed_facet_ids": [],
                "promoted_role_facet_ids": [],
                "unsupported_facet_count": None,
            }
            for item in generations
        ],
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
