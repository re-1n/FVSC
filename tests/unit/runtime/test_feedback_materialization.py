from __future__ import annotations

from fvsc.evidence import (
    EvidenceEvent,
    EvidenceLedger,
    EvidencePolicy,
    create_owner_feedback,
)
from fvsc.ingest.document_ingest import (
    JUDGMENT_EVENT_EXTRACTOR,
    materialize_evidence_ledger,
)


def _target(subject: str, object_: str) -> EvidenceEvent:
    return EvidenceEvent.assertion(
        source_id=f"{subject}.md",
        source_revision="b" * 64,
        observed_at=1.0,
        recorded_at=1.0,
        subject=subject,
        relation="связывать",
        object=object_,
        interpretation_layer=1,
        extractor=JUDGMENT_EVENT_EXTRACTOR,
        extractor_version="1",
        context={
            "derivation": "linguistic-judgment",
            "source_kind": "owner_reflection",
            "judgment": {"confirmation_status": "unreviewed"},
        },
    )


def test_confirmed_policy_uses_feedback_overlay_and_hides_feedback_nodes() -> None:
    accepted = _target("океан", "пустота")
    rejected = _target("сеть", "принуждение")
    ledger = EvidenceLedger([accepted, rejected])
    ledger.append(
        create_owner_feedback(
            ledger,
            target_event_id=accepted.event_id,
            action="confirm",
            observed_at=2.0,
            recorded_at=2.0,
        )
    )
    ledger.append(
        create_owner_feedback(
            ledger,
            target_event_id=rejected.event_id,
            action="reject",
            observed_at=2.0,
            recorded_at=2.0,
        )
    )
    policy = EvidencePolicy(
        source_kinds=frozenset({"owner_reflection"}),
        extractors=frozenset({JUDGMENT_EVENT_EXTRACTOR}),
        confirmation_statuses=frozenset({"confirmed"}),
        max_interpretation_layer=1,
    )

    snapshot = materialize_evidence_ledger(ledger, dim=16, policy=policy)

    assert snapshot.get("океан") is not None
    assert snapshot.get("пустота") is not None
    assert snapshot.get("сеть") is None
    assert snapshot.get("принуждение") is None
    assert snapshot.get("fvsc:owner") is None
