from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[3] / "scripts" / "run_synthesis_gate.py"
SCORE_SCRIPT = Path(__file__).parents[3] / "scripts" / "score_synthesis_gate.py"


def _module():
    spec = importlib.util.spec_from_file_location("run_synthesis_gate", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _score_module():
    spec = importlib.util.spec_from_file_location("score_synthesis_gate", SCORE_SCRIPT)
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
    assert args.host == "http://127.0.0.1:11434"
    assert args.seed == 42
    assert args.num_ctx == 8192


def test_score_cli_requires_run_review_and_output() -> None:
    parser = _score_module()._parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
    args = parser.parse_args(
        ["--run", "run.json", "--review", "review.json", "--output", "score.json"]
    )
    assert args.review == Path("review.json")
