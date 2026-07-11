"""Daily-use pilot runtime built on immutable evidence and semantic states.

The runtime is intentionally small and deterministic.  A source update retracts
its previously active evidence, appends the new assertions, and materializes a
fresh snapshot.  Query scores operate on normalized semantic shapes; evidence
mass is returned only as confidence metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

import numpy as np

from .evidence import EvidenceEvent
from .evidence_ledger import EvidenceLedger
from .materializer import (
    DeterministicEvidenceEncoder,
    EvidenceEncoder,
    MaterializedConcept,
    MaterializedSnapshot,
    materialize_ledger,
)
from .semantic_metrics import (
    inclusion_margin,
    operator_inclusion,
    relative_entropy_inclusion,
    shape_overlap,
)


RUNTIME_VERSION = "daily-pilot-v1"
_EPS = 1e-12


@dataclass(frozen=True)
class SourceUpdateResult:
    source_id: str
    source_revision: str
    retracted_events: int
    asserted_events: int
    active_events: int
    concept_count: int
    snapshot_id: str
    unchanged: bool = False


def source_revision(text: str) -> str:
    """Return a stable content revision for one source document."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _bounded(value: Any, *, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if not np.isfinite(number):
        number = default
    return float(np.clip(number, 0.0, 1.0))


def _statement_rows(semantic_input: Mapping[str, Mapping[str, Any]]) -> list[tuple[str, str, float, float]]:
    """Flatten parser output into deterministic directed containment rows."""
    rows: list[tuple[str, str, float, float]] = []
    for raw_subject, raw_spec in sorted(semantic_input.items(), key=lambda item: str(item[0])):
        subject = str(raw_subject).strip()
        if not subject or not isinstance(raw_spec, Mapping):
            continue
        subject_weight = _bounded(raw_spec.get("weight", 1.0), default=1.0)
        contains = raw_spec.get("contains", {})
        if not isinstance(contains, Mapping):
            continue
        for raw_object, raw_weight in sorted(contains.items(), key=lambda item: str(item[0])):
            object_ = str(raw_object).strip()
            if not object_ or object_ == subject:
                continue
            relation_weight = _bounded(raw_weight, default=0.5)
            if relation_weight <= _EPS:
                continue
            rows.append((subject, object_, relation_weight, subject_weight))
    return rows


class PilotRuntime:
    """Mutable coordinator around an append-only ledger and immutable snapshots."""

    def __init__(
        self,
        ledger: EvidenceLedger | None = None,
        *,
        encoder: EvidenceEncoder | None = None,
    ) -> None:
        self.ledger = ledger or EvidenceLedger()
        self.encoder = encoder or DeterministicEvidenceEncoder()
        self.snapshot = materialize_ledger(self.ledger, encoder=self.encoder)

    @classmethod
    def from_records(
        cls,
        records: list[Mapping[str, Any]],
        *,
        encoder: EvidenceEncoder | None = None,
    ) -> "PilotRuntime":
        return cls(EvidenceLedger.from_records(records), encoder=encoder)

    def to_records(self) -> list[dict[str, Any]]:
        return self.ledger.to_records()

    def _refresh(self) -> None:
        self.snapshot = materialize_ledger(self.ledger, encoder=self.encoder)

    def replace_source(
        self,
        *,
        source_id: str,
        semantic_input: Mapping[str, Mapping[str, Any]],
        source_revision: str,
        observed_at: float,
        recorded_at: float | None = None,
    ) -> SourceUpdateResult:
        """Replace the active semantic evidence produced by one source revision."""
        source = str(source_id).strip()
        revision = str(source_revision).strip()
        if not source:
            raise ValueError("source_id must not be empty")
        if not revision:
            raise ValueError("source_revision must not be empty")

        active = self.ledger.active_for_source(source)
        if active and all(event.source_revision == revision for event in active):
            return SourceUpdateResult(
                source_id=source,
                source_revision=revision,
                retracted_events=0,
                asserted_events=0,
                active_events=self.ledger.active_count,
                concept_count=self.snapshot.concept_count,
                snapshot_id=self.snapshot.snapshot_id,
                unchanged=True,
            )

        lifecycle_events = [
            EvidenceEvent.retraction(
                source_id=source,
                source_revision=revision,
                observed_at=observed_at,
                recorded_at=recorded_at,
                extractor="fvsc-pilot-source-lifecycle",
                extractor_version=RUNTIME_VERSION,
                target_event_id=event.event_id,
                context={"reason": "source_replaced"},
                provenance={"source_id": source},
            )
            for event in sorted(active, key=lambda item: item.event_id)
        ]

        assertions = []
        for subject, object_, relation_weight, subject_weight in _statement_rows(semantic_input):
            assertions.append(
                EvidenceEvent.assertion(
                    source_id=source,
                    source_revision=revision,
                    observed_at=observed_at,
                    recorded_at=recorded_at,
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
                    provenance={"source_id": source},
                )
            )

        self.ledger.append_many([*lifecycle_events, *assertions])
        self._refresh()
        return SourceUpdateResult(
            source_id=source,
            source_revision=revision,
            retracted_events=len(lifecycle_events),
            asserted_events=len(assertions),
            active_events=self.ledger.active_count,
            concept_count=self.snapshot.concept_count,
            snapshot_id=self.snapshot.snapshot_id,
        )

    def delete_source(
        self,
        *,
        source_id: str,
        observed_at: float,
        recorded_at: float | None = None,
    ) -> SourceUpdateResult:
        source = str(source_id).strip()
        if not source:
            raise ValueError("source_id must not be empty")
        active = self.ledger.active_for_source(source)
        revision = hashlib.sha256(f"deleted:{source}:{observed_at}".encode("utf-8")).hexdigest()
        retractions = [
            EvidenceEvent.retraction(
                source_id=source,
                source_revision=revision,
                observed_at=observed_at,
                recorded_at=recorded_at,
                extractor="fvsc-pilot-source-lifecycle",
                extractor_version=RUNTIME_VERSION,
                target_event_id=event.event_id,
                context={"reason": "source_deleted"},
                provenance={"source_id": source},
            )
            for event in sorted(active, key=lambda item: item.event_id)
        ]
        self.ledger.append_many(retractions)
        self._refresh()
        return SourceUpdateResult(
            source_id=source,
            source_revision=revision,
            retracted_events=len(retractions),
            asserted_events=0,
            active_events=self.ledger.active_count,
            concept_count=self.snapshot.concept_count,
            snapshot_id=self.snapshot.snapshot_id,
            unchanged=not retractions,
        )

    def get(self, term: str) -> MaterializedConcept | None:
        return self.snapshot.get(str(term).strip())

    def related(self, term: str, *, top_k: int = 10) -> list[dict[str, Any]]:
        """Rank concepts by mass-invariant shape affinity."""
        if top_k < 1:
            raise ValueError("top_k must be positive")
        source = self.get(term)
        if source is None:
            return []
        rows: list[dict[str, Any]] = []
        for candidate in self.snapshot.concepts:
            if candidate.term == source.term:
                continue
            overlap = shape_overlap(source.state, candidate.state)
            source_contains = operator_inclusion(candidate.state, source.state)
            candidate_contains = operator_inclusion(source.state, candidate.state)
            score = 0.6 * overlap + 0.2 * source_contains + 0.2 * candidate_contains
            rows.append({
                "term": candidate.term,
                "score": float(score),
                "shape_overlap": float(overlap),
                "source_contains_candidate": float(source_contains),
                "candidate_contains_source": float(candidate_contains),
                "mass": candidate.state.mass,
                "evidence_count": candidate.state.evidence_count,
            })
        rows.sort(key=lambda row: (-row["score"], row["term"]))
        return rows[:top_k]

    def trace(self, source_term: str, target_term: str) -> dict[str, Any]:
        """Explain the current shape relation and its evidence provenance."""
        source = self.get(source_term)
        target = self.get(target_term)
        if source is None or target is None:
            missing = [
                term
                for term, concept in ((source_term, source), (target_term, target))
                if concept is None
            ]
            return {"found": False, "missing": missing}

        shared = tuple(sorted(set(source.evidence_ids) & set(target.evidence_ids)))
        source_contains = operator_inclusion(target.state, source.state)
        target_contains = operator_inclusion(source.state, target.state)
        return {
            "found": True,
            "source": source.term,
            "target": target.term,
            "snapshot_id": self.snapshot.snapshot_id,
            "shape_overlap": shape_overlap(source.state, target.state),
            "source_contains_target": source_contains,
            "target_contains_source": target_contains,
            "inclusion_margin": inclusion_margin(source.state, target.state),
            "target_in_source_relative_entropy": relative_entropy_inclusion(
                target.state, source.state
            ),
            "source_mass": source.state.mass,
            "target_mass": target.state.mass,
            "source_evidence_count": source.state.evidence_count,
            "target_evidence_count": target.state.evidence_count,
            "shared_evidence_ids": shared,
        }

    def status(self) -> dict[str, Any]:
        return {
            "runtime_version": RUNTIME_VERSION,
            "encoder_version": self.encoder.version,
            "dimension": self.encoder.dim,
            "event_count": self.ledger.event_count,
            "active_event_count": self.ledger.active_count,
            "concept_count": self.snapshot.concept_count,
            "ledger_digest": self.snapshot.ledger_digest,
            "state_digest": self.snapshot.state_digest,
            "snapshot_id": self.snapshot.snapshot_id,
        }
