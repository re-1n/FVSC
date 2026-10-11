"""Public diagnostic fixtures; gold is never supplied to the S6 operation."""
from dataclasses import dataclass

from ..ingest.source_provenance import ExpressionSpan, SourceAttribution


@dataclass(frozen=True)
class AttributedSource:
    label: str
    text: str
    attribution: SourceAttribution


@dataclass(frozen=True)
class AttributionCase:
    case_id: str
    family: str
    relation: str
    source: AttributedSource
    expected_direct_owner_eligibility: bool


def cases() -> tuple[AttributionCase, ...]:
    result = []
    for relation, statement in (
        ("confirmed", "The cedar workshop is confirmed."),
        ("conditional", "The reserve hall opens only if authorized."),
        ("accepted", "The council accepted the linen cover."),
        ("declined", "The council declined the stone arch."),
        ("retained", "The copper badge was retained."),
        ("replaced", "A tram replaced the shuttle."),
    ):
        for family, text, role, origin, kind, adopted, endorsed, expected in (
            ("owner_direct", statement, "owner", "owner", None, False, "unresolved", True),
            ("annotated_quote", f'Mira wrote: "{statement}"', "owner", "mixed", "quotation", False, "unresolved", False),
            ("endorsed_quote", f'I agree with Mira: "{statement}"', "owner", "mixed", "quotation", True, "endorsed", False),
            ("owner_restatement", f'Mira wrote: "{statement}" My own statement: {statement}', "owner", "mixed", "quotation", False, "unresolved", True),
            ("indirect_report", f'Mira said that {statement[0].lower() + statement[1:]}', "owner", "mixed", None, False, "unresolved", False),
            ("unannotated_quote", f'Mira wrote: "{statement}"', "owner", "mixed", None, False, "unresolved", False),
            ("unknown_author", statement, "unknown", "unresolved", None, False, "unresolved", False),
            ("non_owner_author", statement, "non_owner", "external", None, False, "unresolved", False),
        ):
            spans = ()
            if kind:
                start = text.index(statement)
                spans = (ExpressionSpan.from_text(
                    text, start=start, end=start + len(statement), kind=kind,
                    origin_status="external",
                    owner_relation="adopted" if adopted else "selected",
                    owner_endorsement=endorsed,
                    derivation="public-reported-attribution-v1",
                ),)
            attribution = SourceAttribution(
                transport_author_role=role, owner_adopted_expression=adopted,
                text_origin_status=origin, expression_spans=spans,
            )
            result.append(AttributionCase(
                f"report-v1-{relation}-{family}", family, relation,
                AttributedSource("S1", text, attribution), expected,
            ))
    return tuple(result)
