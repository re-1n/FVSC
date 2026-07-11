"""One-pass construction of a pilot runtime from a vault snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .evidence import EvidenceEvent
from .evidence_ledger import EvidenceLedger
from .materializer import EvidenceEncoder
from .pilot_runtime import PilotRuntime, RUNTIME_VERSION, _statement_rows


@dataclass(frozen=True)
class PilotSourceDocument:
    source_id: str
    semantic_input: Mapping[str, Mapping[str, Any]]
    source_revision: str
    observed_at: float


def build_runtime_from_sources(
    sources: Sequence[PilotSourceDocument],
    *,
    encoder: EvidenceEncoder | None = None,
) -> PilotRuntime:
    """Build one ledger and materialize once, independent of input ordering."""
    events: list[EvidenceEvent] = []
    for source in sorted(sources, key=lambda item: item.source_id):
        source_id = str(source.source_id).strip()
        revision = str(source.source_revision).strip()
        if not source_id or not revision:
            raise ValueError("source_id and source_revision must not be empty")
        for subject, object_, relation_weight, subject_weight in _statement_rows(
            source.semantic_input
        ):
            events.append(
                EvidenceEvent.assertion(
                    source_id=source_id,
                    source_revision=revision,
                    observed_at=source.observed_at,
                    extractor="fvsc-semantic-input",
                    extractor_version=RUNTIME_VERSION,
                    subject=subject,
                    relation="contains",
                    object=object_,
                    intensity=relation_weight,
                    confidence=subject_weight,
                    context={
                        "relation_weight": relation_weight,
                        "subject_weight": subject_weight,
                    },
                    provenance={"source_id": source_id},
                )
            )
    ledger = EvidenceLedger(events)
    return PilotRuntime(ledger, encoder=encoder)
