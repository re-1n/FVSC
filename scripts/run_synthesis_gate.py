"""Run the preregistered public synthesis pair against one local Ollama model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from fvsc.evaluation.synthesis import SynthesisArm
from fvsc.evaluation.synthesis_fixtures import PUBLIC_SYNTHESIS_FIXTURES
from fvsc.evaluation.synthesis_runner import run_synthesis_pair
from fvsc.integrations.ollama import OllamaInterpretationBackend


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="exact installed Ollama model tag")
    parser.add_argument("--model-digest", required=True, help="SHA-256 reported by Ollama")
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
        raise ValueError("refusing to overwrite an existing synthesis artifact")
    if not output.parent.is_dir():
        raise ValueError("synthesis artifact parent directory does not exist")

    probe = OllamaInterpretationBackend(
        model=args.model,
        host=args.host,
        model_digest=args.model_digest,
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

    def backend_factory(
        arm: SynthesisArm,
        system_prompt: str,
        prompt_version: str,
    ) -> OllamaInterpretationBackend:
        return OllamaInterpretationBackend(
            model=args.model,
            host=args.host,
            model_digest=args.model_digest,
            seed=args.seed,
            temperature=0.0,
            num_ctx=args.num_ctx,
            num_predict=args.num_predict,
            timeout=args.timeout,
            system_prompt=system_prompt,
            prompt_version=prompt_version,
        )

    bundle = run_synthesis_pair(
        PUBLIC_SYNTHESIS_FIXTURES,
        backend_factory=backend_factory,
    )
    artifact = {
        "model_identity": identity.to_dict(),
        "num_ctx": args.num_ctx,
        "num_predict": args.num_predict,
        "seed": args.seed,
        "temperature": 0.0,
        **bundle.to_dict(),
    }
    output.write_text(
        json.dumps(
            artifact,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
