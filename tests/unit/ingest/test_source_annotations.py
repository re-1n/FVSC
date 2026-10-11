from __future__ import annotations

import hashlib
import json

import pytest

from fvsc.ingest import ExpressionSpan, SourceDocument, source_attribution
from fvsc.ingest.source_annotations import (
    OwnerAnnotationOverlay,
    OwnerExpressionAnnotation,
    apply_owner_annotation_overlay,
    load_owner_annotation_overlay,
)


def _document(text: str = "мой комментарий\nчужой фрагмент") -> SourceDocument:
    return SourceDocument.create(
        source_id="telegram/private-diary/messages/message-7.json",
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=1.0,
        text=text,
        adapter="telegram-export",
        source_kind="owner_reflection",
        raw_chars=len(text),
        metadata={
            "source_attribution": source_attribution(
                transport_author_role="owner",
                owner_adopted_expression=True,
            ).to_dict()
        },
    )


def test_overlay_is_content_addressed_body_free_and_round_trips(tmp_path) -> None:
    document = _document()
    start = document.text.index("чужой")
    annotation = OwnerExpressionAnnotation.create(
        document,
        start=start,
        end=len(document.text),
        kind="song_lyric",
        origin_status="external",
        owner_relation="adopted",
        owner_endorsement="endorsed",
    )
    overlay = OwnerAnnotationOverlay.create((annotation,))
    serialized = overlay.to_dict()

    assert "чужой фрагмент" not in json.dumps(serialized, ensure_ascii=False)
    assert OwnerAnnotationOverlay.from_dict(serialized) == overlay
    path = tmp_path / "annotations.json"
    path.write_text(json.dumps(serialized), encoding="utf-8")
    assert load_owner_annotation_overlay(path) == overlay

    tampered = json.loads(json.dumps(serialized))
    tampered["annotations"][0]["span"]["kind"] = "ai_output"
    with pytest.raises(ValueError, match="overlay_id"):
        OwnerAnnotationOverlay.from_dict(tampered)


def test_overlay_refines_metadata_without_changing_source_body_or_revision() -> None:
    document = _document()
    start = document.text.index("чужой")
    overlay = OwnerAnnotationOverlay.create(
        (
            OwnerExpressionAnnotation.create(
                document,
                start=start,
                end=len(document.text),
                kind="quotation",
                origin_status="external",
                owner_relation="selected",
                owner_endorsement="neutral",
            ),
        )
    )

    (refined,) = apply_owner_annotation_overlay((document,), overlay)

    assert refined.text == document.text
    assert refined.source_revision == document.source_revision
    assert refined.metadata["owner_annotation_overlay_id"] == overlay.overlay_id
    span = refined.metadata["source_attribution"]["expression_spans"][0]
    assert span["kind"] == "quotation"
    assert span["owner_relation"] == "selected"
    assert span["owner_endorsement"] == "neutral"


def test_owner_annotation_can_replace_exact_automatic_boundary() -> None:
    document = _document("песня целиком")
    automatic = ExpressionSpan.from_text(
        document.text,
        start=0,
        end=len(document.text),
        kind="quotation",
        owner_relation="adopted",
        derivation="telegram:text_entity:block_quote",
    )
    document = SourceDocument.create(
        source_id=document.source_id,
        source_revision=document.source_revision,
        observed_at=document.observed_at,
        text=document.text,
        adapter=document.adapter,
        source_kind=document.source_kind,
        raw_chars=document.raw_chars,
        metadata={
            "source_attribution": source_attribution(
                transport_author_role="owner",
                owner_adopted_expression=True,
                expression_spans=(automatic,),
            ).to_dict()
        },
    )
    annotation = OwnerExpressionAnnotation.create(
        document,
        start=0,
        end=len(document.text),
        kind="song_lyric",
        origin_status="external",
        owner_relation="adopted",
        owner_endorsement="endorsed",
    )

    (refined,) = apply_owner_annotation_overlay(
        (document,), OwnerAnnotationOverlay.create((annotation,))
    )

    spans = refined.metadata["source_attribution"]["expression_spans"]
    assert len(spans) == 1
    assert spans[0]["kind"] == "song_lyric"
    assert spans[0]["derivation"] == "owner-annotation:v1"


def test_overlay_fails_closed_on_revision_absence_overlap_and_raw_text_field() -> None:
    document = _document()
    annotation = OwnerExpressionAnnotation.create(
        document,
        start=0,
        end=5,
        kind="owner_commentary",
        origin_status="owner",
        owner_relation="authored",
    )
    value = annotation.to_dict()
    value["text"] = "must not enter the overlay"
    with pytest.raises(ValueError, match="unknown fields"):
        OwnerExpressionAnnotation.from_dict(value)

    changed = _document(document.text + "!")
    with pytest.raises(ValueError, match="revision changed"):
        apply_owner_annotation_overlay(
            (changed,), OwnerAnnotationOverlay.create((annotation,))
        )

    absent = SourceDocument.create(
        source_id="other.json",
        source_revision=document.source_revision,
        observed_at=1.0,
        text=document.text,
        adapter="test",
    )
    with pytest.raises(ValueError, match="absent"):
        apply_owner_annotation_overlay(
            (absent,), OwnerAnnotationOverlay.create((annotation,))
        )

    automatic = ExpressionSpan.from_text(
        document.text,
        start=2,
        end=10,
        kind="quotation",
        derivation="telegram:text_entity:block_quote",
    )
    with_automatic = SourceDocument.create(
        source_id=document.source_id,
        source_revision=document.source_revision,
        observed_at=document.observed_at,
        text=document.text,
        adapter=document.adapter,
        source_kind=document.source_kind,
        raw_chars=document.raw_chars,
        metadata={
            "source_attribution": source_attribution(
                transport_author_role="owner",
                owner_adopted_expression=True,
                expression_spans=(automatic,),
            ).to_dict()
        },
    )
    with pytest.raises(ValueError, match="partially overlaps"):
        apply_owner_annotation_overlay(
            (with_automatic,), OwnerAnnotationOverlay.create((annotation,))
        )
