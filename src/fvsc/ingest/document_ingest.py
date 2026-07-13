"""Convert source documents to canonical evidence and reconcile source life cycles."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import time
from typing import Iterable, Mapping

from ..evidence.events import EvidenceEvent
from ..evidence.ledger import EvidenceLedger
from ..evidence.provenance import SilentPool, build_provenance_and_silent
from ..runtime.materializer import (
    DeterministicEvidenceEncoder,
    MaterializedSnapshot,
    materialize_ledger,
)
from .parser import ParseConfig, text_to_semantic_input
from .vault_ingest import SourceDocument, SourceKind


DOCUMENT_INGEST_MANAGER = "fvsc-document-ingest-v1"
DOCUMENT_EXTRACTOR = "fvsc.ingest.cooccurrence"
DOCUMENT_EXTRACTOR_VERSION = "1"
SOURCE_METADATA_EXTRACTOR = "fvsc.ingest.source-metadata"
SOURCE_METADATA_EXTRACTOR_VERSION = "1"
LIFECYCLE_EXTRACTOR = "fvsc.ingest.source-lifecycle"
LIFECYCLE_EXTRACTOR_VERSION = "1"
FVSC_SELF_RELATION = "fvsc:self"
FVSC_CONTAINS_RELATION = "fvsc:contains"
FVSC_AUTHORED_BY_RELATION = "fvsc:authored-by"
FVSC_FORWARDED_FROM_RELATION = "fvsc:forwarded-from"
FVSC_REPLY_TO_RELATION = "fvsc:replies-to"
FVSC_TEMPORAL_CONTEXT_RELATION = "fvsc:temporal-context"
FVSC_LOCATOR_RELATION = "fvsc:references-locator"
FVSC_DEFERRED_MEDIA_RELATION = "fvsc:deferred-media"
STRUCTURAL_RELATIONS = frozenset(
    {
        FVSC_AUTHORED_BY_RELATION,
        FVSC_FORWARDED_FROM_RELATION,
        FVSC_REPLY_TO_RELATION,
        FVSC_TEMPORAL_CONTEXT_RELATION,
        FVSC_LOCATOR_RELATION,
        FVSC_DEFERRED_MEDIA_RELATION,
    }
)


@dataclass(frozen=True)
class EvidenceBatch:
    """Deterministic parser output for one source adapter scan."""

    adapter: str
    events: tuple[EvidenceEvent, ...]
    semantic_input: Mapping[str, Mapping]
    silent_pool: SilentPool
    source_revisions: Mapping[str, str]
    source_observed_at: Mapping[str, float]
    source_kinds: Mapping[str, SourceKind]
    raw_chars: int = 0
    cleaned_chars: int = 0

    def __post_init__(self) -> None:
        adapter = str(self.adapter).strip()
        if not adapter:
            raise ValueError("evidence batch adapter must not be empty")
        event_ids = tuple(event.event_id for event in self.events)
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("evidence batch contains duplicate event ids")
        if event_ids != tuple(
            event.event_id
            for event in sorted(self.events, key=_event_sort_key)
        ):
            raise ValueError("evidence batch events must be deterministically sorted")
        source_ids = set(self.source_revisions)
        if source_ids != set(self.source_observed_at) or source_ids != set(self.source_kinds):
            raise ValueError("evidence batch source metadata keys must match")
        for event in self.events:
            provenance = event.provenance
            if provenance.get("managed_by") != DOCUMENT_INGEST_MANAGER:
                raise ValueError("evidence batch event is missing its manager provenance")
            if provenance.get("source_adapter") != adapter:
                raise ValueError("evidence batch event adapter does not match the batch")
        source_keys = tuple(_source_key(event) for event in self.events)
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("evidence batch contains duplicate source assertion keys")
        object.__setattr__(self, "adapter", adapter)

    @property
    def source_count(self) -> int:
        return len(self.source_revisions)


@dataclass(frozen=True)
class SourceLifecycleReport:
    """Append-only changes applied by one reconciliation pass."""

    asserted_count: int
    retracted_count: int
    unchanged_count: int
    changed_sources: tuple[str, ...]
    deleted_sources: tuple[str, ...]
    ledger_digest: str


def _bounded_weight(value: float) -> float:
    weight = float(value)
    if not math.isfinite(weight) or weight < 0.0:
        raise ValueError("parser weights must be finite and non-negative")
    return min(weight, 1.0)


def _event_sort_key(event: EvidenceEvent) -> tuple[str, str, str, str, str]:
    return (
        event.source_id,
        event.subject or "",
        event.relation or "",
        event.object or "",
        event.event_id,
    )


def _assertion_for_source(
    *,
    document: SourceDocument,
    subject: str,
    relation: str,
    object_: str,
    semantic_role: str,
    parser_weight: float,
    source_fraction: float,
) -> EvidenceEvent:
    bounded_weight = _bounded_weight(parser_weight)
    fraction = float(source_fraction)
    if not math.isfinite(fraction) or not 0.0 < fraction <= 1.0:
        raise ValueError("source provenance fractions must be in (0, 1]")
    modality = bounded_weight * fraction
    assertion_key_payload = {
        "adapter": document.adapter,
        "confidence": 1.0,
        "extractor": DOCUMENT_EXTRACTOR,
        "extractor_version": DOCUMENT_EXTRACTOR_VERSION,
        "intensity": bounded_weight,
        "interpretation_layer": 1,
        "modality": modality,
        "object": object_,
        "parser_weight": float(parser_weight),
        "polarity": 1.0,
        "relation": relation,
        "semantic_role": semantic_role,
        "source_id": document.source_id,
        "source_kind": document.source_kind,
        "source_revision": document.source_revision,
        "subject": subject,
    }
    source_assertion_key = hashlib.sha256(
        json.dumps(
            assertion_key_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return EvidenceEvent.assertion(
        source_id=document.source_id,
        source_revision=document.source_revision,
        observed_at=document.observed_at,
        # Keep deterministic replay equality as well as a stable event id.
        recorded_at=document.observed_at,
        subject=subject,
        relation=relation,
        object=object_,
        polarity=1.0,
        modality=modality,
        intensity=bounded_weight,
        confidence=1.0,
        interpretation_layer=1,
        extractor=DOCUMENT_EXTRACTOR,
        extractor_version=DOCUMENT_EXTRACTOR_VERSION,
        context={
            "derivation": "directed-token-cooccurrence",
            "semantic_role": semantic_role,
            "source_kind": document.source_kind,
        },
        provenance={
            "managed_by": DOCUMENT_INGEST_MANAGER,
            "parser_weight": float(parser_weight),
            "source_adapter": document.adapter,
            "source_assertion_key": source_assertion_key,
            "source_fraction": fraction,
            "source_id": document.source_id,
            "source_revision": document.source_revision,
        },
    )


def _source_entity(source_id: str) -> str:
    return f"fvsc:source:{source_id}"


def _structural_assertion_for_source(
    *,
    document: SourceDocument,
    relation: str,
    object_: str,
    structural_role: str,
    context: Mapping | None = None,
) -> EvidenceEvent:
    event_context = {
        "derivation": "source-metadata",
        "source_kind": document.source_kind,
        "structural_role": structural_role,
        **dict(context or {}),
    }
    assertion_key_payload = {
        "adapter": document.adapter,
        "context": event_context,
        "extractor": SOURCE_METADATA_EXTRACTOR,
        "extractor_version": SOURCE_METADATA_EXTRACTOR_VERSION,
        "interpretation_layer": 0,
        "object": object_,
        "relation": relation,
        "source_id": document.source_id,
        "source_revision": document.source_revision,
        "subject": _source_entity(document.source_id),
    }
    source_assertion_key = hashlib.sha256(
        json.dumps(
            assertion_key_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return EvidenceEvent.assertion(
        source_id=document.source_id,
        source_revision=document.source_revision,
        observed_at=document.observed_at,
        recorded_at=document.observed_at,
        subject=_source_entity(document.source_id),
        relation=relation,
        object=object_,
        polarity=1.0,
        modality=1.0,
        intensity=1.0,
        confidence=1.0,
        interpretation_layer=0,
        extractor=SOURCE_METADATA_EXTRACTOR,
        extractor_version=SOURCE_METADATA_EXTRACTOR_VERSION,
        context=event_context,
        provenance={
            "managed_by": DOCUMENT_INGEST_MANAGER,
            "source_adapter": document.adapter,
            "source_assertion_key": source_assertion_key,
            "source_id": document.source_id,
            "source_revision": document.source_revision,
        },
    )


def _structural_events_for_document(document: SourceDocument) -> list[EvidenceEvent]:
    metadata = document.metadata
    if metadata.get("format") != "telegram-json":
        return []

    events: list[EvidenceEvent] = []
    author_key = metadata.get("author_key")
    if isinstance(author_key, str) and author_key.strip():
        events.append(
            _structural_assertion_for_source(
                document=document,
                relation=FVSC_AUTHORED_BY_RELATION,
                object_=f"fvsc:actor:{author_key.strip()}",
                structural_role="authorship",
                context={
                    "owner_adopted_expression": bool(
                        metadata.get("owner_adopted_expression", False)
                    ),
                    "owner_authored": bool(metadata.get("owner_authored", False)),
                },
            )
        )

    forward_source_key = metadata.get("forward_source_key")
    if (
        metadata.get("forwarded") is True
        and isinstance(forward_source_key, str)
        and forward_source_key.strip()
    ):
        events.append(
            _structural_assertion_for_source(
                document=document,
                relation=FVSC_FORWARDED_FROM_RELATION,
                object_=f"fvsc:actor:{forward_source_key.strip()}",
                structural_role="forward_origin",
            )
        )

    reply_to_source_id = metadata.get("reply_to_source_id")
    if isinstance(reply_to_source_id, str) and reply_to_source_id.strip():
        events.append(
            _structural_assertion_for_source(
                document=document,
                relation=FVSC_REPLY_TO_RELATION,
                object_=_source_entity(reply_to_source_id.strip()),
                structural_role="reply_context",
            )
        )

    temporal_context = metadata.get("temporal_context")
    if isinstance(temporal_context, Mapping):
        previous_source_id = temporal_context.get("previous_source_id")
        gap_seconds = temporal_context.get("gap_seconds")
        threshold_seconds = temporal_context.get("threshold_seconds")
        if isinstance(previous_source_id, str) and previous_source_id.strip():
            try:
                gap = float(gap_seconds)
                threshold = float(threshold_seconds)
            except (TypeError, ValueError):
                gap = math.nan
                threshold = math.nan
            if math.isfinite(gap) and math.isfinite(threshold) and 0.0 <= gap <= threshold:
                events.append(
                    _structural_assertion_for_source(
                        document=document,
                        relation=FVSC_TEMPORAL_CONTEXT_RELATION,
                        object_=_source_entity(previous_source_id.strip()),
                        structural_role="temporal_context",
                        context={
                            "gap_seconds": gap,
                            "heuristic": True,
                            "threshold_seconds": threshold,
                        },
                    )
                )

    locators = metadata.get("locators", [])
    if isinstance(locators, list):
        for locator in sorted(
            {
                value.strip()
                for value in locators
                if isinstance(value, str) and value.strip()
            }
        ):
            events.append(
                _structural_assertion_for_source(
                    document=document,
                    relation=FVSC_LOCATOR_RELATION,
                    object_=locator,
                    structural_role="source_locator",
                )
            )

    media_kind = metadata.get("media_kind")
    if (
        metadata.get("media_deferred") is True
        and isinstance(media_kind, str)
        and media_kind.strip()
    ):
        events.append(
            _structural_assertion_for_source(
                document=document,
                relation=FVSC_DEFERRED_MEDIA_RELATION,
                object_=f"fvsc:media:{media_kind.strip()}",
                structural_role="deferred_media",
            )
        )
    return events


def build_evidence_batch(
    documents: Iterable[SourceDocument],
    *,
    config: ParseConfig | None = None,
    adapter: str | None = None,
) -> EvidenceBatch:
    """Build parser-derived assertions with per-document provenance.

    Parsing remains a global corpus pass so vocabulary and containment weights
    match the research pipeline. A second per-file provenance pass partitions
    every assertion back to relative source ids.
    """
    ordered = tuple(sorted(documents, key=lambda document: document.source_id))
    source_ids = tuple(document.source_id for document in ordered)
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("source documents must have unique source ids")
    adapters = {document.adapter for document in ordered}
    if adapter is None:
        if len(adapters) != 1:
            raise ValueError("adapter is required for an empty or mixed document batch")
        adapter_value = next(iter(adapters))
    else:
        adapter_value = str(adapter).strip()
        if not adapter_value:
            raise ValueError("adapter must not be empty")
        if adapters and adapters != {adapter_value}:
            raise ValueError("all source documents must match the requested adapter")

    parser_config = config or ParseConfig()
    files_by_path = {document.source_id: document.text for document in ordered}
    corpus = "\n\n".join(document.text for document in ordered if document.text)
    semantic_input = text_to_semantic_input(corpus, config=parser_config) if corpus else {}
    provenance, silent_pool = build_provenance_and_silent(
        semantic_input,
        files_by_path,
        parser_config,
    )
    documents_by_id = {document.source_id: document for document in ordered}

    events: list[EvidenceEvent] = []
    for document in ordered:
        events.extend(_structural_events_for_document(document))
    for concept in sorted(semantic_input):
        specification = semantic_input[concept]
        parser_weight = float(specification.get("weight", 1.0))
        concept_provenance = provenance.get(concept, {})
        self_sources = concept_provenance.get("self", {})
        for source_id, fraction in sorted(self_sources.items()):
            document = documents_by_id.get(source_id)
            if document is None:
                raise ValueError(f"provenance references an unknown source: {source_id}")
            events.append(
                _assertion_for_source(
                    document=document,
                    subject=concept,
                    relation=FVSC_SELF_RELATION,
                    object_=concept,
                    semantic_role="self",
                    parser_weight=parser_weight,
                    source_fraction=float(fraction),
                )
            )

        contains_sources = concept_provenance.get("contains", {})
        for child, child_weight in sorted(specification.get("contains", {}).items()):
            child_sources = contains_sources.get(child, {})
            for source_id, fraction in sorted(child_sources.items()):
                document = documents_by_id.get(source_id)
                if document is None:
                    raise ValueError(f"provenance references an unknown source: {source_id}")
                events.append(
                    _assertion_for_source(
                        document=document,
                        subject=concept,
                        relation=FVSC_CONTAINS_RELATION,
                        object_=child,
                        semantic_role="contains",
                        parser_weight=float(child_weight),
                        source_fraction=float(fraction),
                    )
                )

    events.sort(key=_event_sort_key)
    return EvidenceBatch(
        adapter=adapter_value,
        events=tuple(events),
        semantic_input=semantic_input,
        silent_pool=silent_pool,
        source_revisions={document.source_id: document.source_revision for document in ordered},
        source_observed_at={document.source_id: document.observed_at for document in ordered},
        source_kinds={document.source_id: document.source_kind for document in ordered},
        raw_chars=sum(document.raw_chars for document in ordered),
        cleaned_chars=sum(len(document.text) for document in ordered),
    )


def _is_managed_event(event: EvidenceEvent, *, adapter: str) -> bool:
    provenance = event.provenance
    return (
        provenance.get("managed_by") == DOCUMENT_INGEST_MANAGER
        and provenance.get("source_adapter") == adapter
    )


def _source_key(event: EvidenceEvent) -> str:
    value = event.provenance.get("source_assertion_key")
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError("managed parser event is missing a source assertion key")
    return value


def _reactivated_assertion(
    event: EvidenceEvent,
    *,
    prior_event_id: str,
    recorded_at: float,
) -> EvidenceEvent:
    """Create a new append-only assertion for a previously retracted source state."""
    if event.subject is None or event.relation is None or event.object is None:
        raise ValueError("parser assertion is missing its statement")
    provenance = event.provenance
    provenance["reactivates_event_id"] = prior_event_id
    return EvidenceEvent.assertion(
        source_id=event.source_id,
        source_revision=event.source_revision,
        observed_at=event.observed_at,
        recorded_at=recorded_at,
        subject=event.subject,
        relation=event.relation,
        object=event.object,
        polarity=event.polarity,
        modality=event.modality,
        intensity=event.intensity,
        confidence=event.confidence,
        interpretation_layer=event.interpretation_layer,
        extractor=event.extractor,
        extractor_version=event.extractor_version,
        context=event.context,
        provenance=provenance,
    )


def reconcile_evidence_batch(
    ledger: EvidenceLedger,
    batch: EvidenceBatch,
    *,
    sync_time: float | None = None,
) -> SourceLifecycleReport:
    """Atomically append retractions and new assertions for one adapter scan."""
    if not isinstance(ledger, EvidenceLedger):
        raise TypeError("ledger must be an EvidenceLedger")
    reconciled_at = time.time() if sync_time is None else float(sync_time)
    if not math.isfinite(reconciled_at):
        raise ValueError("sync_time must be finite")

    active_managed = {
        _source_key(event): event
        for event in ledger.active_events
        if _is_managed_event(event, adapter=batch.adapter)
    }
    desired = {_source_key(event): event for event in batch.events}
    unchanged_keys = set(active_managed) & set(desired)
    obsolete = [active_managed[key] for key in sorted(set(active_managed) - set(desired))]
    additions = [desired[key] for key in sorted(set(desired) - set(active_managed))]

    appendable_additions: list[EvidenceEvent] = []
    for event in additions:
        existing = ledger.get(event.event_id)
        if existing is not None and not ledger.is_active(event.event_id):
            event = _reactivated_assertion(
                event,
                prior_event_id=existing.event_id,
                recorded_at=reconciled_at,
            )
        appendable_additions.append(event)

    deleted_sources = sorted(
        {event.source_id for event in obsolete if event.source_id not in batch.source_revisions}
    )
    changed_sources = sorted(
        ({event.source_id for event in obsolete} | {event.source_id for event in additions})
        - set(deleted_sources)
    )

    retractions: list[EvidenceEvent] = []
    for target in obsolete:
        deleted = target.source_id not in batch.source_revisions
        observed_at = batch.source_observed_at.get(target.source_id, reconciled_at)
        replacement_revision = batch.source_revisions.get(target.source_id)
        source_kind = batch.source_kinds.get(
            target.source_id,
            target.context.get("source_kind", "unknown"),
        )
        retractions.append(
            EvidenceEvent.retraction(
                source_id=target.source_id,
                source_revision=replacement_revision,
                observed_at=observed_at,
                recorded_at=reconciled_at,
                target_event_id=target.event_id,
                interpretation_layer=1,
                extractor=LIFECYCLE_EXTRACTOR,
                extractor_version=LIFECYCLE_EXTRACTOR_VERSION,
                context={
                    "lifecycle_reason": "source_deleted" if deleted else "source_replaced",
                    "source_kind": source_kind,
                },
                provenance={
                    "managed_by": DOCUMENT_INGEST_MANAGER,
                    "previous_revision": target.source_revision,
                    "replacement_revision": replacement_revision,
                    "source_adapter": batch.adapter,
                    "source_id": target.source_id,
                },
            )
        )

    # Retractions precede assertions so active state never contains two source
    # revisions during validation. append_many keeps the whole transition atomic.
    ledger.append_many([*retractions, *appendable_additions])
    return SourceLifecycleReport(
        asserted_count=len(additions),
        retracted_count=len(retractions),
        unchanged_count=len(unchanged_keys),
        changed_sources=tuple(changed_sources),
        deleted_sources=tuple(deleted_sources),
        ledger_digest=ledger.digest,
    )


def materialize_evidence_ledger(
    ledger: EvidenceLedger,
    *,
    dim: int = 64,
) -> MaterializedSnapshot:
    """Build the deterministic semantic-space view without relation pseudo-nodes."""
    encoder = DeterministicEvidenceEncoder(
        dim=dim,
        excluded_terms=frozenset({FVSC_SELF_RELATION, FVSC_CONTAINS_RELATION}),
        excluded_relations=STRUCTURAL_RELATIONS,
    )
    return materialize_ledger(ledger, encoder=encoder)


__all__ = [
    "DOCUMENT_INGEST_MANAGER",
    "FVSC_AUTHORED_BY_RELATION",
    "EvidenceBatch",
    "FVSC_CONTAINS_RELATION",
    "FVSC_DEFERRED_MEDIA_RELATION",
    "FVSC_FORWARDED_FROM_RELATION",
    "FVSC_LOCATOR_RELATION",
    "FVSC_REPLY_TO_RELATION",
    "FVSC_SELF_RELATION",
    "FVSC_TEMPORAL_CONTEXT_RELATION",
    "SOURCE_METADATA_EXTRACTOR",
    "STRUCTURAL_RELATIONS",
    "SourceLifecycleReport",
    "build_evidence_batch",
    "materialize_evidence_ledger",
    "reconcile_evidence_batch",
]
