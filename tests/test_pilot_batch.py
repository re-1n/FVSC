from __future__ import annotations

from core.pilot_batch import PilotSourceDocument, build_runtime_from_sources
from core.pilot_runtime import PilotRuntime


def _documents() -> list[PilotSourceDocument]:
    return [
        PilotSourceDocument(
            source_id="b.md",
            semantic_input={
                "доверие": {"weight": 0.9, "contains": {"отношения": 0.7}},
                "отношения": {"weight": 0.8, "contains": {}},
            },
            source_revision="b" * 64,
            observed_at=2.0,
        ),
        PilotSourceDocument(
            source_id="a.md",
            semantic_input={
                "свобода": {"weight": 0.9, "contains": {"выбор": 0.8}},
                "выбор": {"weight": 0.8, "contains": {}},
            },
            source_revision="a" * 64,
            observed_at=1.0,
        ),
    ]


def test_batch_rebuild_matches_sequential_materialization() -> None:
    documents = _documents()
    batch = build_runtime_from_sources(list(reversed(documents)))

    sequential = PilotRuntime()
    for document in sorted(documents, key=lambda item: item.source_id):
        sequential.replace_source(
            source_id=document.source_id,
            semantic_input=document.semantic_input,
            source_revision=document.source_revision,
            observed_at=document.observed_at,
            recorded_at=document.observed_at,
        )

    assert batch.snapshot.state_digest == sequential.snapshot.state_digest
    assert batch.snapshot.concept_count == sequential.snapshot.concept_count
    assert batch.ledger.active_count == sequential.ledger.active_count


def test_batch_rebuild_is_input_order_independent() -> None:
    documents = _documents()
    first = build_runtime_from_sources(documents)
    second = build_runtime_from_sources(list(reversed(documents)))

    assert first.status() == second.status()
