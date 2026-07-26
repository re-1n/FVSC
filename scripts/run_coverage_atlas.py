"""Run frozen baseline/claim-first arms on the public coverage atlas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.claim_first_runner import run_claim_first_pair
from fvsc.evaluation.claim_first_synthesis import CLAIM_FIRST_PROMPT_VERSION
from fvsc.evaluation.coverage_atlas import atlas_fixtures
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
        raise ValueError("refusing to overwrite an existing coverage-atlas artifact")
    if not output.parent.is_dir():
        raise ValueError("coverage-atlas artifact parent directory does not exist")
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
    if identity is None:
        raise RuntimeError("configured Ollama model is not installed or not reachable")
    if identity.digest != args.model_digest:
        raise RuntimeError("installed Ollama model digest does not match preregistration")

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
            prompt_version=f"coverage-atlas-v1-{prompt_version}",
        )

    fixtures = atlas_fixtures()
    generations = run_claim_first_pair(fixtures, backend_factory=backend_factory)
    artifact = {
        "fixture_ids": [item.case_id for item in fixtures],
        "generations": [item.to_dict() for item in generations],
        "model_identity": identity.to_dict(),
        "num_ctx": args.num_ctx,
        "num_predict": args.num_predict,
        "prompt_version": f"coverage-atlas-v1-{CLAIM_FIRST_PROMPT_VERSION}",
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
