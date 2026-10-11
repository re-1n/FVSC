"""Owner feedback as append-only evidence overlays.

Feedback never mutates an extractor event in place. It is recorded as a separate
structural assertion over the target event id, so source replay and owner review
remain independent histories.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Literal, Mapping

from .events import EvidenceEvent
from .ledger import EvidenceLedger


FeedbackAction = Literal["confirm", "reject", "contextualize"]
FEEDBACK_ACTIONS = frozenset({"confirm", "reject", "contextualize"})
FVSC_OWNER_FEEDBACK_RELATION = "fvsc:owner-feedback"
OWNER_FEEDBACK_EXTRACTOR = "fvsc.owner-feedback"
OWNER_FEEDBACK_EXTRACTOR_VERSION = "1"


def create_owner_feedback(
    ledger: EvidenceLedger,
    *,
    target_event_id: str,
    action: FeedbackAction,
    observed_at: float,
    recorded_at: float | None = None,
    context_tags: tuple[str, ...] | list[str] = (),
    prompt_event_id: str | None = None,
) -> EvidenceEvent:
    """Create, but do not append, an owner review of one ledger assertion."""
    target = ledger.get(target_event_id)
    if target is None:
        raise ValueError(f"feedback target does not exist: {target_event_id}")
    if target.event_kind not in {"assertion", "supersession"}:
        raise ValueError("feedback target must be an assertion-like event")
    if action not in FEEDBACK_ACTIONS:
        raise ValueError(f"unknown feedback action: {action!r}")
    tags = tuple(sorted({str(tag).strip() for tag in context_tags if str(tag).strip()}))
    if action != "contextualize" and tags:
        raise ValueError("context tags are accepted only for contextualize feedback")
    if action == "contextualize" and not tags:
        raise ValueError("contextualize feedback requires at least one context tag")
    prompt = str(prompt_event_id).strip() if prompt_event_id is not None else None
    if prompt == "":
        prompt = None
    if prompt is not None and ledger.get(prompt) is None:
        raise ValueError(f"feedback prompt event does not exist: {prompt}")

    target_ref = f"fvsc:event:{target_event_id}"
    return EvidenceEvent.assertion(
        source_id=f"fvsc/feedback/{target_event_id}",
        source_revision=target_event_id,
        observed_at=observed_at,
        recorded_at=recorded_at,
        subject="fvsc:owner",
        relation=FVSC_OWNER_FEEDBACK_RELATION,
        object=target_ref,
        polarity=1.0,
        modality=1.0,
        intensity=1.0,
        confidence=1.0,
        interpretation_layer=0,
        extractor=OWNER_FEEDBACK_EXTRACTOR,
        extractor_version=OWNER_FEEDBACK_EXTRACTOR_VERSION,
        context={
            "derivation": "owner-feedback",
            "feedback": {
                "action": action,
                "context_tags": list(tags),
                "prompt_event_id": prompt,
                "target_event_id": target_event_id,
            },
            "structural_role": "owner_feedback",
        },
        provenance={
            "actor_role": "owner",
            "prompt_event_id": prompt,
            "target_event_id": target_event_id,
        },
    )


@dataclass(frozen=True)
class FeedbackDecision:
    target_event_id: str
    action: FeedbackAction
    context_tags: tuple[str, ...]
    feedback_event_id: str
    observed_at: float

    @property
    def confirmation_status(self) -> str:
        return {
            "confirm": "confirmed",
            "reject": "rejected",
            "contextualize": "contextualized",
        }[self.action]


@dataclass(frozen=True)
class FeedbackState:
    """Latest active owner decision for each target event."""

    decisions: Mapping[str, FeedbackDecision]
    digest: str

    @classmethod
    def from_ledger(cls, ledger: EvidenceLedger) -> "FeedbackState":
        candidates: dict[str, list[tuple[EvidenceEvent, FeedbackDecision]]] = {}
        active_feedback_ids: list[str] = []
        for event in ledger.active_events:
            if (
                event.relation != FVSC_OWNER_FEEDBACK_RELATION
                or event.extractor != OWNER_FEEDBACK_EXTRACTOR
            ):
                continue
            raw = event.context.get("feedback")
            if not isinstance(raw, dict):
                continue
            target_id = raw.get("target_event_id")
            action = raw.get("action")
            if not isinstance(target_id, str) or action not in FEEDBACK_ACTIONS:
                continue
            tags_value = raw.get("context_tags", [])
            tags = (
                tuple(sorted(str(tag) for tag in tags_value))
                if isinstance(tags_value, list)
                else ()
            )
            decision = FeedbackDecision(
                target_event_id=target_id,
                action=action,
                context_tags=tags,
                feedback_event_id=event.event_id,
                observed_at=event.observed_at,
            )
            candidates.setdefault(target_id, []).append((event, decision))
            active_feedback_ids.append(event.event_id)

        decisions = {
            target_id: max(
                values,
                key=lambda item: (item[0].observed_at, item[0].event_id),
            )[1]
            for target_id, values in candidates.items()
        }
        digest = hashlib.sha256(
            "\n".join(sorted(active_feedback_ids)).encode("ascii")
        ).hexdigest()
        return cls(decisions=decisions, digest=digest)

    def decision_for(self, event_id: str) -> FeedbackDecision | None:
        return self.decisions.get(event_id)

    def confirmation_status_for(self, event_id: str) -> str:
        decision = self.decision_for(event_id)
        return "unreviewed" if decision is None else decision.confirmation_status

    def context_tags_for(self, event_id: str) -> tuple[str, ...]:
        decision = self.decision_for(event_id)
        return () if decision is None else decision.context_tags


__all__ = [
    "FEEDBACK_ACTIONS",
    "FVSC_OWNER_FEEDBACK_RELATION",
    "FeedbackAction",
    "FeedbackDecision",
    "FeedbackState",
    "OWNER_FEEDBACK_EXTRACTOR",
    "OWNER_FEEDBACK_EXTRACTOR_VERSION",
    "create_owner_feedback",
]
