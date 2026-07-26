"""Frozen F1/S6 expression-boundary fixtures for direct relation support."""

from __future__ import annotations

from dataclasses import dataclass

from ..ingest.source_provenance import ExpressionSpan
from .relation_support_guard import GuardedRelation


@dataclass(frozen=True)
class RelationGuardAttributionFixture:
    case_id: str
    relation: GuardedRelation
    text: str
    expression_spans: tuple[ExpressionSpan, ...]
    should_be_directly_eligible: bool


def _external_span(text: str, quoted: str) -> ExpressionSpan:
    start = text.index(quoted)
    return ExpressionSpan.from_text(
        text,
        start=start,
        end=start + len(quoted),
        kind="quotation",
        origin_status="external",
        owner_relation="selected",
        owner_endorsement="unresolved",
        derivation="public-attribution-audit-v1",
    )


def _pair(prefix: str, relation: GuardedRelation, statement: str):
    direct_text = f"The record states directly: {statement}"
    quoted_text = f'The record embeds an external quotation: "{statement}"'
    return (
        RelationGuardAttributionFixture(
            f"attribution-{prefix}-direct",
            relation,
            direct_text,
            (),
            True,
        ),
        RelationGuardAttributionFixture(
            f"attribution-{prefix}-quotation",
            relation,
            quoted_text,
            (_external_span(quoted_text, statement),),
            False,
        ),
    )


PUBLIC_RELATION_GUARD_ATTRIBUTION_FIXTURES = tuple(
    item
    for pair in (
        _pair("confirmed", "confirmed", "The west room is confirmed."),
        _pair("conditional", "conditional", "The terrace opens only if approved."),
        _pair("accepted", "accepted", "The panel accepted the oak finish."),
        _pair("declined", "declined", "The panel declined the glass canopy."),
        _pair("retained", "retained", "The paper receipt was retained."),
        _pair("replaced", "replaced", "A kiosk replaced the staffed desk."),
    )
    for item in pair
)


__all__ = [
    "PUBLIC_RELATION_GUARD_ATTRIBUTION_FIXTURES",
    "RelationGuardAttributionFixture",
]
