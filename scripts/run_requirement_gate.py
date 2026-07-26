"""Run the held-out baseline/requirement-coverage synthesis gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.requirement_gate_fixtures import (
    PUBLIC_REQUIREMENT_GATE_FIXTURES,
)
from fvsc.evaluation.requirement_runner import run_requirement_pair
from fvsc.evaluation.requirement_synthesis import REQUIREMENT_PROMPT_VERSION
from fvsc.integrations.ollama import OllamaInterpretationBackend


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-digest", required=True)
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-ctx", type=int, default=8192)
    parser.add_argument("--num-predict", type=int, default=768)
    parser.add_argument("--timeout", type=float, default=900.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise ValueError("refusing to overwrite an existing requirement-gate artifact")
    if not output.parent.is_dir():
        raise ValueError("requirement-gate artifact parent directory does not exist")
    probe = OllamaInterpretationBackend(
        model=args.model,
        model_digest=args.model_digest,
        host=args.host,
        seed=args.seed,
        temperature=0.0,
        num_ctx=args.num_ctx,
        num_predict=args.num_predict,
        timeout=args.timeout,
    )
    identity = probe.model_identity()
    if identity is None or identity.digest != args.model_digest:
        raise RuntimeError("frozen Ollama model identity is unavailable")

    def backend_factory(arm, system_prompt, prompt_version):
        return OllamaInterpretationBackend(
            model=args.model,
            model_digest=args.model_digest,
            host=args.host,
            seed=args.seed,
            temperature=0.0,
            num_ctx=args.num_ctx,
            num_predict=args.num_predict,
            timeout=args.timeout,
            system_prompt=system_prompt,
            prompt_version=prompt_version,
        )

    generations = run_requirement_pair(
        PUBLIC_REQUIREMENT_GATE_FIXTURES,
        backend_factory=backend_factory,
    )
    artifact = {
        "fixture_ids": [item.case_id for item in PUBLIC_REQUIREMENT_GATE_FIXTURES],
        "generations": [item.to_dict() for item in generations],
        "model_identity": identity.to_dict(),
        "num_ctx": args.num_ctx,
        "num_predict": args.num_predict,
        "prompt_version": REQUIREMENT_PROMPT_VERSION,
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
