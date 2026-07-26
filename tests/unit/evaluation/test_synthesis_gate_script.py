from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[3] / "scripts" / "run_synthesis_gate.py"


def _module():
    spec = importlib.util.spec_from_file_location("run_synthesis_gate", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_requires_model_identity_and_output() -> None:
    parser = _module()._parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
    args = parser.parse_args(
        [
            "--model",
            "model:tag",
            "--model-digest",
            "a" * 64,
            "--output",
            "result.json",
        ]
    )
    assert args.model == "model:tag"
    assert args.seed == 42
    assert args.num_ctx == 8192
