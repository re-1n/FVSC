"""Temporal and contradiction views over append-only judgment evidence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from .events import EvidenceEvent
from .feedback import FeedbackState
from .ledger import EvidenceLedger
from .policy import EvidencePolicy


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


@dataclass(frozen=True)
class JudgmentScope:
    """Logical envelope within which polarity can be compared safely."""

    modality_type: str = "FACTUAL"
    condition_id: str | int | None = None
    condition_role: str | None = None


@dataclass(frozen=True)
class TimelineJudgment:
    event_id: str
    source_id: str
    observed_at: float
    recorded_at: float
    subject: str
    relation: str
    object: str
    polarity: float
    modality: float
    intensity: float
    confidence: float
    interpretation_layer: int
    confirmation_status: str
    source_kind: str | None
    scope: JudgmentScope
    active: bool
    source_span: dict[str, Any] | None = None

    @property
    def core_key(self) -> tuple[str, str, str]:
        return (
            _normalized(self.subject),
            _normalized(self.relation),
            _normalized(self.object),
        )

    @property
    def scoped_key(self) -> tuple[str, str, str, JudgmentScope]:
        return (*self.core_key, self.scope)


@dataclass(frozen=True)
class Contradiction:
    subject: str
    relation: str
    object: str
    scope: JudgmentScope
    affirmative: tuple[TimelineJudgment, ...]
    negative: tuple[TimelineJudgment, ...]

    @property
    def first_observed_at(self) -> float:
        return min(item.observed_at for item in (*self.affirmative, *self.negative))

    @property
    def last_observed_at(self) -> float:
        return max(item.observed_at for item in (*self.affirmative, *self.negative))


@dataclass(frozen=True)
class JudgmentTimeline:
    judgments: tuple[TimelineJudgment, ...]
    digest: str

    def history_for(
        self,
        subject: str,
        relation: str,
        object_: str,
    ) -> tuple[TimelineJudgment, ...]:
        key = (_normalized(subject), _normalized(relation), _normalized(object_))
        return tuple(item for item in self.judgments if item.core_key == key)

    def contradictions(
        self,
        *,
        active_only: bool = False,
        include_rejected: bool = False,
    ) -> tuple[Contradiction, ...]:
        groups: dict[tuple[str, str, str, JudgmentScope], list[TimelineJudgment]] = {}
        for item in self.judgments:
            if active_only and not item.active:
                continue
            if not include_rejected and item.confirmation_status == "rejected":
                continue
            groups.setdefault(item.scoped_key, []).append(item)

        result: list[Contradiction] = []
        for key, values in groups.items():
            affirmative = tuple(item for item in values if item.polarity > 0.0)
            negative = tuple(item for item in values if item.polarity < 0.0)
            if not affirmative or not negative:
                continue
            first = values[0]
            result.append(
                Contradiction(
                    subject=first.subject,
                    relation=first.relation,
                    object=first.object,
                    scope=key[3],
                    affirmative=affirmative,
                    negative=negative,
                )
            )
        result.sort(
            key=lambda item: (
                item.first_observed_at,
                _normalized(item.subject),
                _normalized(item.relation),
                _normalized(item.object),
            )
        )
        return tuple(result)


def _timeline_judgment(
    event: EvidenceEvent,
    *,
    ledger: EvidenceLedger,
    feedback: FeedbackState,
) -> TimelineJudgment | None:
    if event.event_kind not in {"assertion", "supersession"}:
        return None
    if event.subject is None or event.relation is None or event.object is None:
        return None
    context = event.context
    if context.get("structural_role") is not None:
        return None
    raw_judgment = context.get("judgment")
    judgment = raw_judgment if isinstance(raw_judgment, dict) else {}
    raw_span = context.get("source_span")
    source_span = dict(raw_span) if isinstance(raw_span, dict) else None
    source_kind = context.get("source_kind")
    return TimelineJudgment(
        event_id=event.event_id,
        source_id=event.source_id,
        observed_at=event.observed_at,
        recorded_at=event.recorded_at,
        subject=event.subject,
        relation=event.relation,
        object=event.object,
        polarity=event.polarity,
        modality=event.modality,
        intensity=event.intensity,
        confidence=event.confidence,
        interpretation_layer=event.interpretation_layer,
        confirmation_status=feedback.confirmation_status_for(event.event_id),
        source_kind=source_kind if isinstance(source_kind, str) else None,
        scope=JudgmentScope(
            modality_type=str(judgment.get("modality_type", "FACTUAL")),
            condition_id=judgment.get("condition_id"),
            condition_role=(
                str(judgment["condition_role"])
                if judgment.get("condition_role") is not None
                else None
            ),
        ),
        active=ledger.is_active(event.event_id),
        source_span=source_span,
    )


def build_judgment_timeline(
    ledger: EvidenceLedger,
    *,
    policy: EvidencePolicy | None = None,
) -> JudgmentTimeline:
    """Build a source-cited history without collapsing changes or conflicts."""
    feedback = FeedbackState.from_ledger(ledger)
    judgments: list[TimelineJudgment] = []
    for event in ledger.events:
        status = feedback.confirmation_status_for(event.event_id)
        if policy is not None and not policy.allows(
            event,
            confirmation_status=status,
        ):
            continue
        item = _timeline_judgment(event, ledger=ledger, feedback=feedback)
        if item is not None:
            judgments.append(item)
    judgments.sort(key=lambda item: (item.observed_at, item.source_id, item.event_id))
    digest_payload = "\n".join(
        f"{item.event_id}:{int(item.active)}:{item.confirmation_status}"
        for item in judgments
    )
    return JudgmentTimeline(
        judgments=tuple(judgments),
        digest=hashlib.sha256(digest_payload.encode("ascii")).hexdigest(),
    )


__all__ = [
    "Contradiction",
    "JudgmentScope",
    "JudgmentTimeline",
    "TimelineJudgment",
    "build_judgment_timeline",
]
