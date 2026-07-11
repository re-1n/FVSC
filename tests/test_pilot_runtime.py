from __future__ import annotations

from core.pilot_runtime import PilotRuntime, source_revision


def _semantic_input(weight: float = 0.8) -> dict:
    return {
        "свобода": {
            "weight": 0.9,
            "contains": {"выбор": weight, "ответственность": 0.6},
        },
        "выбор": {"weight": 0.7, "contains": {}},
        "ответственность": {"weight": 0.7, "contains": {}},
    }


def test_source_replace_is_idempotent_for_same_revision() -> None:
    runtime = PilotRuntime()
    text = "Свобода включает выбор и ответственность."
    revision = source_revision(text)

    first = runtime.replace_source(
        source_id="daily/2026-07-11.md",
        semantic_input=_semantic_input(),
        source_revision=revision,
        observed_at=1.0,
        recorded_at=2.0,
    )
    second = runtime.replace_source(
        source_id="daily/2026-07-11.md",
        semantic_input=_semantic_input(),
        source_revision=revision,
        observed_at=3.0,
        recorded_at=4.0,
    )

    assert first.asserted_events == 2
    assert first.retracted_events == 0
    assert second.unchanged is True
    assert second.asserted_events == 0
    assert runtime.ledger.event_count == 2
    assert runtime.ledger.active_count == 2


def test_source_update_retracts_old_evidence_before_materializing() -> None:
    runtime = PilotRuntime()
    runtime.replace_source(
        source_id="note.md",
        semantic_input=_semantic_input(),
        source_revision="a" * 64,
        observed_at=1.0,
        recorded_at=2.0,
    )

    result = runtime.replace_source(
        source_id="note.md",
        semantic_input={
            "свобода": {"weight": 1.0, "contains": {"дисциплина": 0.75}},
            "дисциплина": {"weight": 0.8, "contains": {}},
        },
        source_revision="b" * 64,
        observed_at=5.0,
        recorded_at=6.0,
    )

    assert result.retracted_events == 2
    assert result.asserted_events == 1
    assert runtime.ledger.event_count == 5
    assert runtime.ledger.active_count == 1
    assert runtime.get("выбор") is None
    assert runtime.get("дисциплина") is not None


def test_delete_source_removes_active_projection_but_preserves_history() -> None:
    runtime = PilotRuntime()
    runtime.replace_source(
        source_id="note.md",
        semantic_input=_semantic_input(),
        source_revision="c" * 64,
        observed_at=1.0,
        recorded_at=2.0,
    )

    result = runtime.delete_source(
        source_id="note.md",
        observed_at=7.0,
        recorded_at=8.0,
    )

    assert result.retracted_events == 2
    assert runtime.ledger.active_count == 0
    assert runtime.ledger.event_count == 4
    assert runtime.snapshot.concept_count == 0


def test_trace_and_related_use_materialized_shape_and_provenance() -> None:
    runtime = PilotRuntime()
    runtime.replace_source(
        source_id="note.md",
        semantic_input=_semantic_input(),
        source_revision="d" * 64,
        observed_at=1.0,
        recorded_at=2.0,
    )

    trace = runtime.trace("свобода", "выбор")
    related = runtime.related("свобода", top_k=5)

    assert trace["found"] is True
    assert 0.0 <= trace["shape_overlap"] <= 1.0
    assert 0.0 <= trace["source_contains_target"] <= 1.0
    assert trace["shared_evidence_ids"]
    assert related
    assert {row["term"] for row in related} >= {"выбор", "ответственность"}
    assert all(0.0 <= row["score"] <= 1.0 for row in related)


def test_runtime_round_trips_ledger_records() -> None:
    runtime = PilotRuntime()
    runtime.replace_source(
        source_id="note.md",
        semantic_input=_semantic_input(),
        source_revision="e" * 64,
        observed_at=1.0,
        recorded_at=2.0,
    )

    restored = PilotRuntime.from_records(runtime.to_records())

    assert restored.status() == runtime.status()
    assert restored.trace("свобода", "ответственность") == runtime.trace(
        "свобода", "ответственность"
    )
