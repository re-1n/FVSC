"""Narrow deterministic relation support guard for public English slot gates."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal, Mapping, Sequence

from ..ingest.source_provenance import ExpressionSpan
from .planned_slot_synthesis import FrozenQuestionPlan
from .synthesis import SyntheticSource


GuardedRelation = Literal[
    "accepted",
    "conditional",
    "confirmed",
    "declined",
    "replaced",
    "retained",
]
RELATION_SUPPORT_GUARD_OPERATION_ID = "S6"

_DESCRIPTION_RELATIONS: tuple[tuple[re.Pattern[str], GuardedRelation], ...] = (
    (re.compile(r"\bconfirmed\b", re.IGNORECASE), "confirmed"),
    (re.compile(r"\bconditional\b|\bcondition for\b", re.IGNORECASE), "conditional"),
    (re.compile(r"\baccepted\b", re.IGNORECASE), "accepted"),
    (re.compile(r"\bdeclined\b", re.IGNORECASE), "declined"),
    (re.compile(r"\breplaced\b", re.IGNORECASE), "replaced"),
    (re.compile(r"\bretained\b", re.IGNORECASE), "retained"),
)

_SOURCE_CUES: Mapping[GuardedRelation, tuple[re.Pattern[str], ...]] = {
    "confirmed": (
        re.compile(r"\bconfirmed\b", re.IGNORECASE),
        re.compile(r"\bhas been fixed\b", re.IGNORECASE),
    ),
    "conditional": (
        re.compile(r"\bonly (?:if|when|once|after|upon)\b", re.IGNORECASE),
        re.compile(r"\bsubject to\b", re.IGNORECASE),
        re.compile(r"\bconditional upon\b", re.IGNORECASE),
        re.compile(r"\bdepends on\b", re.IGNORECASE),
    ),
    "accepted": (
        re.compile(r"\baccepted\b", re.IGNORECASE),
        re.compile(r"\badopted\b", re.IGNORECASE),
    ),
    "declined": (
        re.compile(r"\bdeclined\b", re.IGNORECASE),
        re.compile(r"\brejected\b", re.IGNORECASE),
    ),
    "retained": (
        re.compile(r"\bretained\b", re.IGNORECASE),
        re.compile(r"\bremains? (?:in|part of)\b", re.IGNORECASE),
        re.compile(r"\bkept\b", re.IGNORECASE),
    ),
    "replaced": (
        re.compile(r"\breplaced\b", re.IGNORECASE),
        re.compile(r"\bsuperseded\b", re.IGNORECASE),
        re.compile(r"\bsubstituted for\b", re.IGNORECASE),
    ),
}
_CLAUSE_BOUNDARY = re.compile(r"[.;:!?\n]")
_LOCAL_NEGATIONS = frozenset({"no", "not", "never"})
_LOCAL_MODALS = frozenset({"could", "may", "might", "possibly", "would"})


@dataclass(frozen=True)
class RelationSupportCandidate:
    requirement_id: str
    relation: GuardedRelation
    eligible_source_labels: tuple[str, ...]


@dataclass(frozen=True)
class RelationSupportGuardOperation:
    operation_id: str = RELATION_SUPPORT_GUARD_OPERATION_ID
    registered_relations: tuple[GuardedRelation, ...] = (
        "accepted",
        "conditional",
        "confirmed",
        "declined",
        "replaced",
        "retained",
    )

    def __post_init__(self) -> None:
        if self.operation_id != RELATION_SUPPORT_GUARD_OPERATION_ID:
            raise ValueError("relation guard operation id must remain S6")
        if set(self.registered_relations) != set(_SOURCE_CUES):
            raise ValueError("relation guard registration must match frozen cue types")

    def compile(
        self,
        plan: FrozenQuestionPlan,
        sources: Sequence[SyntheticSource],
    ) -> tuple[RelationSupportCandidate, ...]:
        candidates = compile_relation_support_candidates(plan, sources)
        if any(item.relation not in self.registered_relations for item in candidates):
            raise ValueError("plan requests an unregistered guarded relation")
        return candidates


PUBLIC_RELATION_SUPPORT_GUARD = RelationSupportGuardOperation()


def relation_for_requirement(description: str) -> GuardedRelation:
    matches = tuple(
        relation
        for pattern, relation in _DESCRIPTION_RELATIONS
        if pattern.search(description)
    )
    if len(matches) != 1:
        raise ValueError("requirement does not identify exactly one guarded relation")
    return matches[0]


def source_affirms_relation(
    text: str,
    relation: GuardedRelation,
    *,
    expression_spans: Sequence[ExpressionSpan] = (),
) -> bool:
    """Return true when a cue survives the frozen local polarity/modal filter."""

    for span in expression_spans:
        span.verify(text)
    for pattern in _SOURCE_CUES[relation]:
        for match in pattern.finditer(text):
            clause_start = max(
                (
                    boundary.end()
                    for boundary in _CLAUSE_BOUNDARY.finditer(text, 0, match.start())
                ),
                default=0,
            )
            prefix_tokens = re.findall(
                r"[A-Za-z']+",
                text[clause_start : match.start()].lower(),
            )
            if _LOCAL_NEGATIONS & set(prefix_tokens):
                continue
            if _LOCAL_MODALS & set(prefix_tokens[-4:]):
                continue
            if any(
                span.kind != "owner_commentary"
                and match.start() < span.end
                and match.end() > span.start
                for span in expression_spans
            ):
                continue
            return True
    return False


def _source_expression_spans(source: object) -> tuple[ExpressionSpan, ...]:
    attribution = getattr(source, "attribution", None)
    spans = (
        getattr(attribution, "expression_spans", ())
        if attribution is not None
        else getattr(source, "expression_spans", ())
    )
    return tuple(spans)


def compile_relation_support_candidates(
    plan: FrozenQuestionPlan,
    sources: Sequence[SyntheticSource],
) -> tuple[RelationSupportCandidate, ...]:
    result = []
    for requirement in plan.requirements:
        relation = relation_for_requirement(requirement.description)
        labels = tuple(
            source.label
            for source in sources
            if source_affirms_relation(
                source.text,
                relation,
                expression_spans=_source_expression_spans(source),
            )
        )
        result.append(
            RelationSupportCandidate(requirement.requirement_id, relation, labels)
        )
    return tuple(result)


__all__ = [
    "GuardedRelation",
    "PUBLIC_RELATION_SUPPORT_GUARD",
    "RELATION_SUPPORT_GUARD_OPERATION_ID",
    "RelationSupportCandidate",
    "RelationSupportGuardOperation",
    "compile_relation_support_candidates",
    "relation_for_requirement",
    "source_affirms_relation",
]
