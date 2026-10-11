from __future__ import annotations

import hashlib

from fvsc.evidence import EvidenceEvent, EvidenceLedger, EvidencePolicy
from fvsc.ingest import (
    JUDGMENT_EVENT_EXTRACTOR,
    OBSIDIAN_VAULT_ADAPTER,
    ParseConfig,
    RussianJudgmentExtractor,
    SourceDocument,
    TELEGRAM_EXPORT_ADAPTER,
)
from fvsc.ingest.document_ingest import (
    FVSC_AUTHORED_BY_RELATION,
    FVSC_CONTAINS_RELATION,
    FVSC_DEFERRED_MEDIA_RELATION,
    FVSC_FORWARDED_FROM_RELATION,
    FVSC_LOCATOR_RELATION,
    FVSC_REPLY_TO_RELATION,
    FVSC_SELF_RELATION,
    FVSC_TEMPORAL_CONTEXT_RELATION,
    SOURCE_METADATA_EXTRACTOR,
    STRUCTURAL_RELATIONS,
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


def _telegram_document(
    source_id: str,
    text: str,
    *,
    observed_at: float,
    metadata: dict,
    source_kind: str = "owner_reflection",
) -> SourceDocument:
    return SourceDocument.create(
        source_id=source_id,
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=observed_at,
        text=text,
        adapter=TELEGRAM_EXPORT_ADAPTER,
        source_kind=source_kind,  # type: ignore[arg-type]
        raw_chars=len(text),
        metadata={"format": "telegram-json", **metadata},
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


def test_optional_judgment_extractor_adds_exact_relations_beside_fallback() -> None:
    document = _document(
        "note.md",
        "Свобода не требует подчинения.",
        observed_at=10.0,
        source_kind="owner_reflection",
    )

    batch = build_evidence_batch(
        [document],
        config=_config(),
        judgment_extractor=RussianJudgmentExtractor(),
    )
    exact = [
        event for event in batch.events if event.extractor == JUDGMENT_EVENT_EXTRACTOR
    ]

    assert exact
    assert any(
        (event.subject, event.relation, event.object)
        == ("свобода", "требовать", "подчинение")
        for event in exact
    )
    relation = next(event for event in exact if event.relation == "требовать")
    assert relation.polarity == -1.0
    assert relation.context["judgment"]["defeasible"] is True
    assert relation.context["source_span"]["start"] == 0
    assert relation.provenance["managed_by"] == "fvsc-document-ingest-v1"
    assert relation.provenance["source_assertion_key"]
    assert any(event.relation == FVSC_CONTAINS_RELATION for event in batch.events)


def test_policy_materializes_owner_exact_view_without_participant_contamination() -> None:
    owner = _document(
        "owner.md",
        "Свобода требует ответственности.",
        observed_at=10.0,
        source_kind="owner_reflection",
    )
    participant = _document(
        "participant.md",
        "Тьма поглощает свет.",
        observed_at=20.0,
        source_kind="unknown",
    )
    batch = build_evidence_batch(
        [owner, participant],
        config=_config(),
        judgment_extractor=RussianJudgmentExtractor(),
    )
    ledger = EvidenceLedger(batch.events)
    policy = EvidencePolicy(
        source_kinds=frozenset({"owner_reflection"}),
        extractors=frozenset({JUDGMENT_EVENT_EXTRACTOR}),
        derivations=frozenset({"linguistic-judgment"}),
        max_interpretation_layer=1,
    )

    snapshot = materialize_evidence_ledger(ledger, dim=16, policy=policy)
    syntax_only = materialize_evidence_ledger(
        ledger,
        dim=16,
        policy=EvidencePolicy(
            source_kinds=frozenset({"owner_reflection"}),
            extractors=frozenset({JUDGMENT_EVENT_EXTRACTOR}),
            max_interpretation_layer=0,
        ),
    )

    assert snapshot.get("свобода") is not None
    assert snapshot.get("требовать") is not None
    assert snapshot.get("ответственность") is not None
    assert snapshot.get("тьма") is None
    assert snapshot.get("поглощать") is None
    assert syntax_only.concept_count == 0


def test_exact_channel_can_be_isolated_without_changing_default_batch() -> None:
    document = _document(
        "note.md",
        "Внимание сканирует реальность.",
        observed_at=10.0,
        source_kind="owner_reflection",
    )
    extractor = RussianJudgmentExtractor()

    default = build_evidence_batch(
        [document],
        config=_config(),
        judgment_extractor=extractor,
    )
    exact_only = build_evidence_batch(
        [document],
        config=_config(),
        judgment_extractor=extractor,
        include_cooccurrence=False,
    )

    assert default.semantic_input
    assert any(event.extractor != JUDGMENT_EVENT_EXTRACTOR for event in default.events)
    assert exact_only.semantic_input == {}
    assert exact_only.events
    assert all(
        event.extractor in {JUDGMENT_EVENT_EXTRACTOR, SOURCE_METADATA_EXTRACTOR}
        for event in exact_only.events
    )


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


def test_telegram_metadata_becomes_structural_evidence_not_semantic_concepts() -> None:
    first_id = "telegram/export/messages/message-1.json"
    second_id = "telegram/export/messages/message-2.json"
    media_id = "telegram/export/messages/message-3.json"
    first = _telegram_document(
        first_id,
        "parasite metaphor",
        observed_at=10.0,
        metadata={
            "author_key": "actor-owner",
            "forwarded": True,
            "forward_source_key": "actor-origin",
            "locators": ["https://example.test/source"],
            "media_deferred": False,
            "owner_adopted_expression": True,
            "owner_authored": True,
            "reply_to_source_id": None,
            "temporal_context": None,
        },
    )
    second = _telegram_document(
        second_id,
        "accepted monster",
        observed_at=20.0,
        metadata={
            "author_key": "actor-owner",
            "forwarded": False,
            "forward_source_key": None,
            "locators": [],
            "media_deferred": False,
            "owner_adopted_expression": True,
            "owner_authored": True,
            "reply_to_source_id": first_id,
            "temporal_context": {
                "gap_seconds": 10.0,
                "heuristic": True,
                "previous_source_id": first_id,
                "threshold_seconds": 1800,
            },
        },
    )
    media = _telegram_document(
        media_id,
        "",
        observed_at=30.0,
        source_kind="unknown",
        metadata={
            "author_key": "actor-participant",
            "forwarded": False,
            "forward_source_key": None,
            "locators": [],
            "media_deferred": True,
            "media_kind": "photo",
            "owner_adopted_expression": False,
            "owner_authored": False,
            "reply_to_source_id": None,
            "temporal_context": None,
        },
    )

    batch = build_evidence_batch([first, second, media], config=_config())
    structural = [event for event in batch.events if event.extractor == SOURCE_METADATA_EXTRACTOR]

    assert {event.relation for event in structural} == {
        FVSC_AUTHORED_BY_RELATION,
        FVSC_DEFERRED_MEDIA_RELATION,
        FVSC_FORWARDED_FROM_RELATION,
        FVSC_LOCATOR_RELATION,
        FVSC_REPLY_TO_RELATION,
        FVSC_TEMPORAL_CONTEXT_RELATION,
    }
    assert all(event.interpretation_layer == 0 for event in structural)
    authored = [event for event in structural if event.relation == FVSC_AUTHORED_BY_RELATION]
    assert len(authored) == 3
    assert {event.context["owner_authored"] for event in authored} == {True, False}
    assert next(
        event for event in structural if event.relation == FVSC_REPLY_TO_RELATION
    ).object == f"fvsc:source:{first_id}"

    snapshot = materialize_evidence_ledger(EvidenceLedger(batch.events), dim=16)
    assert snapshot.get("parasite") is not None
    assert snapshot.get("accepted") is not None
    assert all(snapshot.get(relation) is None for relation in STRUCTURAL_RELATIONS)
    assert snapshot.get(f"fvsc:source:{first_id}") is None
    assert snapshot.get("fvsc:actor:actor-owner") is None
    assert snapshot.get("https://example.test/source") is None
    assert snapshot.get("fvsc:media:photo") is None


def test_structural_metadata_change_retracts_only_changed_relation() -> None:
    source_id = "telegram/export/messages/message-2.json"
    common = {
        "author_key": "actor-owner",
        "forwarded": False,
        "forward_source_key": None,
        "locators": [],
        "media_deferred": False,
        "owner_adopted_expression": True,
        "owner_authored": True,
        "temporal_context": None,
    }
    first = _telegram_document(
        source_id,
        "alpha beta",
        observed_at=20.0,
        metadata={**common, "reply_to_source_id": "telegram/export/messages/message-1.json"},
    )
    changed = _telegram_document(
        source_id,
        "alpha beta",
        observed_at=20.0,
        metadata={**common, "reply_to_source_id": "telegram/export/messages/message-3.json"},
    )
    ledger = EvidenceLedger()
    initial = build_evidence_batch([first], config=_config())
    reconcile_evidence_batch(ledger, initial, sync_time=30.0)

    replacement = build_evidence_batch([changed], config=_config())
    report = reconcile_evidence_batch(ledger, replacement, sync_time=40.0)

    assert report.asserted_count == 1
    assert report.retracted_count == 1
    assert report.unchanged_count == len(initial.events) - 1
    assert report.changed_sources == (source_id,)
