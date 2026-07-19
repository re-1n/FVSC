from __future__ import annotations

import json

import pytest

from fvsc.ingest import ExpressionSpan, SourceAttribution, source_attribution


def test_expression_span_is_content_addressed_and_verifiable() -> None:
    text = "Авторский комментарий\nчужая цитата\nвывод"
    start = text.index("чужая")
    end = start + len("чужая цитата")
    span = ExpressionSpan.from_text(
        text,
        start=start,
        end=end,
        kind="quotation",
        owner_relation="adopted",
        derivation="test:v1",
    )

    span.verify(text)
    restored = ExpressionSpan.from_dict(json.loads(json.dumps(span.to_dict())))
    assert restored == span
    with pytest.raises(ValueError, match="does not match"):
        span.verify(text.replace("чужая", "другая"))


def test_source_attribution_keeps_transport_author_separate_from_text_origin() -> None:
    text = "Комментарий\nцитата"
    span = ExpressionSpan.from_text(
        text,
        start=text.index("цитата"),
        end=len(text),
        kind="quotation",
        owner_relation="adopted",
    )
    attribution = source_attribution(
        transport_author_role="owner",
        owner_adopted_expression=True,
        text_origin_status="unresolved",
        forwarded=True,
        forward_origin_role="owner",
        expression_spans=(span,),
    )

    attribution.verify(text)
    assert attribution.transport_author_role == "owner"
    assert attribution.text_origin_status == "unresolved"
    assert SourceAttribution.from_dict(attribution.to_dict()) == attribution
    assert "цитата" not in json.dumps(attribution.to_dict(), ensure_ascii=False)


def test_source_attribution_rejects_impossible_forward_and_overlapping_spans() -> None:
    with pytest.raises(ValueError, match="non-forwarded"):
        SourceAttribution(
            transport_author_role="owner",
            owner_adopted_expression=True,
            forwarded=False,
            forward_origin_role="owner",
        )

    text = "abcdefgh"
    first = ExpressionSpan.from_text(text, start=0, end=4, kind="quotation")
    second = ExpressionSpan.from_text(text, start=3, end=8, kind="quotation")
    with pytest.raises(ValueError, match="overlap"):
        SourceAttribution(
            transport_author_role="owner",
            owner_adopted_expression=True,
            expression_spans=(first, second),
        )


def test_legacy_metadata_is_read_conservatively() -> None:
    attribution = SourceAttribution.from_metadata(
        {
            "author_key": "actor-opaque",
            "forwarded": True,
            "owner_adopted_expression": True,
            "owner_authored": True,
        }
    )

    assert attribution.transport_author_role == "owner"
    assert attribution.text_origin_status == "unresolved"
    assert attribution.forward_origin_role == "unknown"
