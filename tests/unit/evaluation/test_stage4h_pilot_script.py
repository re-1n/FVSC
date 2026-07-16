from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from scripts.stage4h_pilot import _load_reviews, _parser, _review_template


def _pack():
    claim = SimpleNamespace(claim_id="c" * 64, citation_ids=("d" * 64,))
    item = SimpleNamespace(
        blind_item_id="a" * 64,
        proposal_id="b" * 64,
        claims=(claim,),
    )
    return SimpleNamespace(pack_id="e" * 64, items=(item,))


def test_review_template_can_be_filled_without_computing_content_ids(tmp_path) -> None:
    value = _review_template(_pack())
    review = value["reviews"][0]
    review["meaning_fidelity"] = 3
    review["usefulness"] = 4
    review["false_owner_attribution"] = False
    review["forbidden_composite"] = False
    review["missed_context"] = False
    review["unsupported_referent_assumption"] = False
    review["abstention_preferable"] = False
    review["claim_reviews"][0]["verdict"] = "accepted"
    review["claim_reviews"][0]["citations"][0]["verdict"] = "supports"
    path = tmp_path / "reviews.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    loaded = _load_reviews(path, expected_pack_id=_pack().pack_id)

    assert len(loaded) == 1
    assert loaded[0].meaning_fidelity == 3
    assert loaded[0].claim_reviews[0].citations[0].verdict == "supports"
    assert len(loaded[0].review_id) == 64


def test_unfilled_review_template_fails_closed(tmp_path) -> None:
    value = _review_template(_pack())
    path = tmp_path / "reviews.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError):
        _load_reviews(path, expected_pack_id=_pack().pack_id)

    value["pack_id"] = "f" * 64
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        _load_reviews(path, expected_pack_id=_pack().pack_id)


def test_pilot_cli_allows_slow_cpu_generation_timeout() -> None:
    args = _parser().parse_args(
        [
            "run",
            "--telegram",
            "result.json",
            "--owner-id",
            "owner",
            "--model",
            "qwen:test",
        ]
    )

    assert args.ollama_timeout == 900.0
    assert args.num_predict == 768
