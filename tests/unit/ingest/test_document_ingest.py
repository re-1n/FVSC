from __future__ import annotations

import hashlib

from fvsc.evidence import EvidenceEvent, EvidenceLedger
from fvsc.ingest import (
    OBSIDIAN_VAULT_ADAPTER,
    ParseConfig,
    SourceDocument,
)
from fvsc.ingest.document_ingest import (
    FVSC_CONTAINS_RELATION,
    FVSC_SELF_RELATION,
    build_evidence_batch,
    materialize_evidence_ledger,
    reconcile_evidence_batch,
)


def _document(
    source_id: str,
    text: str,
    *,
    observed_at: float,
    source_kind: str = "unknown",
) -> SourceDocument:
    return SourceDocument.create(
        source_id=source_id,
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=observed_at,
        text=text,
        adapter=OBSIDIAN_VAULT_ADAPTER,
        source_kind=source_kind,  # type: ignore[arg-type]
        raw_chars=len(text),
        metadata={"format": "test"},
    )


def _config() -> ParseConfig:
    return ParseConfig(
        min_freq=1,
        min_token_len=2,
        max_concepts=None,
        window=4,
        weight_threshold=0.0,
    )


def test_batch_builds_parser_events_with_relative_provenance_and_source_kinds() -> None:
    owner = _document(
        "notes/owner.md",
        "freedom requires responsibility.",
        observed_at=10.0,
        source_kind="owner_reflection",
    )
    external = _document(
        "references/book.md",
        "freedom requires context.",
        observed_at=20.0,
        source_kind="external_fact",
    )

    batch = build_evidence_batch([external, owner], config=_config())

    assert batch.source_count == 2
    assert batch.events
    assert {event.relation for event in batch.events} <= {
        FVSC_SELF_RELATION,
        FVSC_CONTAINS_RELATION,
    }
    assert {event.context["source_kind"] for event in batch.events} == {
        "owner_reflection",
        "external_fact",
    }
    for event in batch.events:
        assert event.interpretation_layer == 1
        assert event.provenance["source_id"] == event.source_id
        assert event.provenance["source_revision"] == event.source_revision
        assert 0.0 <= event.modality <= 1.0
        assert 0.0 <= event.intensity <= 1.0


def test_unchanged_reconciliation_is_idempotent() -> None:
    batch = build_evidence_batch(
        [_document("note.md", "alpha beta gamma.", observed_at=10.0)],
        config=_config(),
    )
    ledger = EvidenceLedger()

    first = reconcile_evidence_batch(ledger, batch, sync_time=30.0)
    digest = ledger.digest
    second = reconcile_evidence_batch(ledger, batch, sync_time=40.0)

    assert first.asserted_count == len(batch.events)
    assert first.retracted_count == 0
    assert second.asserted_count == 0
    assert second.retracted_count == 0
    assert second.unchanged_count == len(batch.events)
    assert ledger.digest == digest


def test_change_and_delete_append_retractions_without_erasing_history() -> None:
    first_a = _document("a.md", "alpha beta gamma.", observed_at=10.0)
    first_b = _document("b.md", "delta epsilon zeta.", observed_at=10.0)
    initial = build_evidence_batch([first_a, first_b], config=_config())
    ledger = EvidenceLedger()
    reconcile_evidence_batch(ledger, initial, sync_time=20.0)
    initial_active = {event.event_id: event for event in ledger.active_events}
    initial_count = ledger.event_count

    changed_a = _document("a.md", "alpha beta theta.", observed_at=30.0)
    replacement = build_evidence_batch([changed_a], config=_config())
    report = reconcile_evidence_batch(ledger, replacement, sync_time=40.0)

    assert report.retracted_count > 0
    assert report.asserted_count == len(replacement.events)
    assert report.deleted_sources == ("b.md",)
    assert "a.md" in report.changed_sources
    assert ledger.event_count > initial_count
    assert all(not ledger.is_active(event_id) for event_id in initial_active)
    assert {event.event_id for event in ledger.active_events} == {
        event.event_id for event in replacement.events
    }
    assert any(event.event_kind == "retraction" for event in ledger.events)


def test_reconciliation_does_not_touch_events_owned_by_other_adapters() -> None:
    manual = EvidenceEvent.assertion(
        source_id="note.md",
        observed_at=1.0,
        recorded_at=1.0,
        subject="owner",
        relation="confirmed",
        object="statement",
        extractor="manual-confirmation",
        extractor_version="1",
        provenance={"source_adapter": "manual"},
    )
    ledger = EvidenceLedger([manual])
    empty = build_evidence_batch((), config=_config(), adapter=OBSIDIAN_VAULT_ADAPTER)

    report = reconcile_evidence_batch(ledger, empty, sync_time=2.0)

    assert report.retracted_count == 0
    assert ledger.active_events == (manual,)


def test_deleted_source_can_return_to_an_identical_prior_revision() -> None:
    batch = build_evidence_batch(
        [_document("note.md", "alpha beta gamma.", observed_at=10.0)],
        config=_config(),
    )
    ledger = EvidenceLedger()
    reconcile_evidence_batch(ledger, batch, sync_time=20.0)

    empty = build_evidence_batch((), config=_config(), adapter=OBSIDIAN_VAULT_ADAPTER)
    reconcile_evidence_batch(ledger, empty, sync_time=30.0)
    restored = reconcile_evidence_batch(ledger, batch, sync_time=40.0)
    replay = reconcile_evidence_batch(ledger, batch, sync_time=50.0)

    assert restored.asserted_count == len(batch.events)
    assert restored.retracted_count == 0
    assert replay.asserted_count == 0
    assert replay.unchanged_count == len(batch.events)
    assert all(event.provenance.get("reactivates_event_id") for event in ledger.active_events)


def test_materialized_view_is_reproducible_and_hides_relation_pseudo_nodes() -> None:
    batch = build_evidence_batch(
        [_document("note.md", "alpha beta gamma.", observed_at=10.0)],
        config=_config(),
    )
    ledger = EvidenceLedger(batch.events)

    first = materialize_evidence_ledger(ledger, dim=16)
    second = materialize_evidence_ledger(ledger, dim=16)

    assert first.snapshot_id == second.snapshot_id
    assert first.state_digest == second.state_digest
    assert first.concept_count > 0
    assert first.get(FVSC_SELF_RELATION) is None
    assert first.get(FVSC_CONTAINS_RELATION) is None
