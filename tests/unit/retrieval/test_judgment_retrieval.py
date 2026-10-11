from __future__ import annotations

"""Tests for source-cited judgment retrieval."""

import pytest

from fvsc.evidence import (
    EvidenceEvent,
    EvidenceLedger,
    EvidencePolicy,
    create_owner_feedback,
)
from fvsc.retrieval import JudgmentSearchIndex, search_judgment_evidence


def _event(
    *,
    source_id: str,
    subject: str,
    relation: str,
    object_: str,
    source_kind: str = "owner_reflection",
) -> EvidenceEvent:
    return EvidenceEvent.assertion(
        source_id=source_id,
        source_revision="d" * 64,
        observed_at=1.0,
        recorded_at=1.0,
        subject=subject,
        relation=relation,
        object=object_,
        interpretation_layer=1,
        extractor="fvsc.ingest.judgment",
        extractor_version="1",
        context={
            "derivation": "linguistic-judgment",
            "source_kind": source_kind,
            "judgment": {"confirmation_status": "unreviewed"},
        },
    )


def _policy(*, statuses=None) -> EvidencePolicy:
    return EvidencePolicy(
        source_kinds=frozenset({"owner_reflection"}),
        extractors=frozenset({"fvsc.ingest.judgment"}),
        derivations=frozenset({"linguistic-judgment"}),
        confirmation_statuses=statuses,
        max_interpretation_layer=1,
    )


def test_judgment_retrieval_handles_inflection_and_preserves_event_citations() -> None:
    target = _event(
        source_id="message-1",
        subject="паразит",
        relation="символизировать",
        object_="нарушение граница",
    )
    other = _event(
        source_id="message-2",
        subject="океан",
        relation="содержать",
        object_="маяк",
    )
    ledger = EvidenceLedger([target, other])

    hits = search_judgment_evidence(
        ledger,
        "роль паразитов в метафорах и границах",
        policy=_policy(),
    )

    assert hits
    assert hits[0].source_id == "message-1"
    assert hits[0].evidence_event_ids == (target.event_id,)
    assert hits[0].score > 0.0


def test_owner_and_feedback_policy_excludes_participant_and_rejected_events() -> None:
    owner = _event(
        source_id="owner",
        subject="внимание",
        relation="сканировать",
        object_="реальность",
    )
    participant = _event(
        source_id="participant",
        subject="внимание",
        relation="сканировать",
        object_="реальность",
        source_kind="unknown",
    )
    ledger = EvidenceLedger([owner, participant])
    ledger.append(
        create_owner_feedback(
            ledger,
            target_event_id=owner.event_id,
            action="reject",
            observed_at=2.0,
            recorded_at=2.0,
        )
    )

    exploratory = search_judgment_evidence(
        ledger,
        "внимание сканирует реальность",
        policy=_policy(),
    )
    accepted = search_judgment_evidence(
        ledger,
        "внимание сканирует реальность",
        policy=_policy(statuses=frozenset({"confirmed", "unreviewed"})),
    )

    assert [hit.source_id for hit in exploratory] == ["owner"]
    assert accepted == ()


def test_empty_query_and_invalid_limit() -> None:
    assert search_judgment_evidence(EvidenceLedger(), "") == ()
    with pytest.raises(ValueError, match="top_k"):
        search_judgment_evidence(EvidenceLedger(), "test", top_k=0)


def test_reusable_judgment_index_matches_one_off_search() -> None:
    target = _event(
        source_id="message-1",
        subject="океан",
        relation="содержать",
        object_="маяк",
    )
    ledger = EvidenceLedger([target])
    policy = _policy()
    index = JudgmentSearchIndex(ledger, policy=policy)

    first = index.search("океан и маяки")
    replay = index.search("океан и маяки")
    one_off = search_judgment_evidence(ledger, "океан и маяки", policy=policy)

    assert first == replay == one_off
