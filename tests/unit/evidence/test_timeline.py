from __future__ import annotations

from fvsc.evidence import (
    EvidenceEvent,
    EvidenceLedger,
    EvidencePolicy,
    build_judgment_timeline,
    create_owner_feedback,
)


def _judgment(
    *,
    source: str,
    observed_at: float,
    polarity: float,
    modality_type: str = "FACTUAL",
    condition_id: str | None = None,
    source_kind: str = "owner_reflection",
) -> EvidenceEvent:
    return EvidenceEvent.assertion(
        source_id=source,
        source_revision=(source[0] if source[0] in "abcdef" else "a") * 64,
        observed_at=observed_at,
        recorded_at=observed_at,
        subject="личность",
        relation="содержать",
        object="другие",
        polarity=polarity,
        interpretation_layer=1,
        extractor="fvsc.ingest.judgment",
        extractor_version="1",
        context={
            "derivation": "linguistic-judgment",
            "source_kind": source_kind,
            "judgment": {
                "modality_type": modality_type,
                "condition_id": condition_id,
                "condition_role": "ANTECEDENT" if condition_id else None,
            },
        },
    )


def test_timeline_preserves_conflict_and_source_history() -> None:
    affirmative = _judgment(source="a.md", observed_at=1.0, polarity=1.0)
    negative = _judgment(source="b.md", observed_at=2.0, polarity=-1.0)
    ledger = EvidenceLedger([affirmative, negative])
    ledger.append(
        EvidenceEvent.retraction(
            source_id="a.md",
            source_revision="c" * 64,
            observed_at=3.0,
            recorded_at=3.0,
            target_event_id=affirmative.event_id,
            extractor="test-lifecycle",
            extractor_version="1",
        )
    )

    timeline = build_judgment_timeline(ledger)
    history = timeline.history_for("Личность", "содержать", "другие")

    assert len(history) == 2
    assert [item.active for item in history] == [False, True]
    assert len(timeline.contradictions()) == 1
    assert timeline.contradictions(active_only=True) == ()


def test_conditional_and_factual_polarities_are_not_false_contradictions() -> None:
    factual = _judgment(source="a.md", observed_at=1.0, polarity=1.0)
    conditional = _judgment(
        source="b.md",
        observed_at=2.0,
        polarity=-1.0,
        modality_type="CONDITIONAL",
        condition_id="condition-1",
    )
    timeline = build_judgment_timeline(EvidenceLedger([factual, conditional]))

    assert timeline.contradictions() == ()


def test_policy_and_feedback_filter_timeline_without_erasing_rejected_event() -> None:
    owner = _judgment(source="a.md", observed_at=1.0, polarity=1.0)
    participant = _judgment(
        source="b.md",
        observed_at=2.0,
        polarity=-1.0,
        source_kind="unknown",
    )
    ledger = EvidenceLedger([owner, participant])
    ledger.append(
        create_owner_feedback(
            ledger,
            target_event_id=owner.event_id,
            action="reject",
            observed_at=3.0,
            recorded_at=3.0,
        )
    )
    owner_policy = EvidencePolicy(
        source_kinds=frozenset({"owner_reflection"}),
        extractors=frozenset({"fvsc.ingest.judgment"}),
        max_interpretation_layer=1,
    )
    accepted_policy = EvidencePolicy(
        source_kinds=frozenset({"owner_reflection"}),
        extractors=frozenset({"fvsc.ingest.judgment"}),
        confirmation_statuses=frozenset({"confirmed", "unreviewed"}),
        max_interpretation_layer=1,
    )

    owner_timeline = build_judgment_timeline(ledger, policy=owner_policy)
    accepted_timeline = build_judgment_timeline(ledger, policy=accepted_policy)

    assert len(owner_timeline.judgments) == 1
    assert owner_timeline.judgments[0].confirmation_status == "rejected"
    assert accepted_timeline.judgments == ()
