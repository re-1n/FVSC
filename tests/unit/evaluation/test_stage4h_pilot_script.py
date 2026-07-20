from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import scripts.stage4h_pilot as pilot
from fvsc.ingest import load_telegram_export
from fvsc.ingest.source_annotations import (
    OwnerAnnotationOverlay,
    OwnerExpressionAnnotation,
)
from scripts.stage4h_pilot import (
    _atomic_private_write,
    _load_reviews,
    _parser,
    _review_template,
)


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
    assert args.annotations is None

    annotated = _parser().parse_args(
        [
            "run",
            "--telegram",
            "result.json",
            "--annotations",
            "annotations.json",
            "--owner-id",
            "owner",
            "--model",
            "qwen:test",
        ]
    )
    assert annotated.annotations.name == "annotations.json"


def test_validate_annotations_checks_overlay_without_loading_model(
    tmp_path,
    capsys,
) -> None:
    telegram = tmp_path / "result.json"
    telegram.write_text(
        json.dumps(
            {
                "name": "private",
                "messages": [
                    {
                        "date": "2026-01-01T00:00:00Z",
                        "from_id": "owner",
                        "id": 1,
                        "text": "цитируемый текст",
                        "type": "message",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    export = load_telegram_export(
        telegram,
        owner_author_ids=("owner",),
        source_namespace="test",
    )
    document = export.documents[0]
    annotation = OwnerExpressionAnnotation.create(
        document,
        start=0,
        end=len(document.text),
        kind="quotation",
        origin_status="external",
        owner_relation="selected",
    )
    overlay = OwnerAnnotationOverlay.create((annotation,))
    annotations = tmp_path / "annotations.json"
    annotations.write_text(
        json.dumps(overlay.to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )

    exit_code = pilot.main(
        [
            "validate-annotations",
            "--telegram",
            str(telegram),
            "--annotations",
            str(annotations),
            "--owner-id",
            "owner",
            "--namespace",
            "test",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {
        "annotation_count": 1,
        "annotated_source_count": 1,
        "corpus_document_count": 1,
        "overlay_id": overlay.overlay_id,
        "status": "valid",
    }


def test_atomic_private_write_works_without_posix_fchmod(tmp_path, monkeypatch) -> None:
    monkeypatch.delattr(pilot.os, "fchmod", raising=False)
    destination = tmp_path / "manifest.json"

    _atomic_private_write(destination, '{"run": "windows"}\n')

    assert destination.read_text(encoding="utf-8") == '{"run": "windows"}\n'
    assert tuple(tmp_path.iterdir()) == (destination,)


def test_atomic_private_write_closes_descriptor_when_permissions_fail(
    tmp_path,
    monkeypatch,
) -> None:
    real_close = pilot.os.close
    closed: list[int] = []

    def close_and_record(descriptor: int) -> None:
        closed.append(descriptor)
        real_close(descriptor)

    def fail_permissions(descriptor: int, mode: int) -> None:
        raise PermissionError("simulated permission failure")

    monkeypatch.setattr(pilot.os, "close", close_and_record)
    monkeypatch.setattr(pilot.os, "fchmod", fail_permissions, raising=False)

    with pytest.raises(PermissionError, match="simulated permission failure"):
        _atomic_private_write(tmp_path / "manifest.json", "{}\n")

    assert len(closed) == 1
    assert tuple(tmp_path.iterdir()) == ()
