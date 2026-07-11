"""Immutable semantic snapshots and auditable proposed state deltas."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

import numpy as np

from .materializer import MaterializedSnapshot
from .semantic_state import SemanticState


@dataclass(frozen=True, eq=False)
class SnapshotConcept:
    term: str
    state: SemanticState
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        term = str(self.term).strip()
        if not term:
            raise ValueError("snapshot concept term must not be empty")
        evidence_ids = tuple(sorted(set(self.evidence_ids)))
        object.__setattr__(self, "term", term)
        object.__setattr__(self, "evidence_ids", evidence_ids)


def _update_state_hash(digest: Any, concept: SnapshotConcept) -> None:
    digest.update(concept.term.encode("utf-8"))
    digest.update(np.asarray(concept.state.mass, dtype="<f8").tobytes())
    digest.update(np.asarray(concept.state.shape, dtype="<f8").tobytes(order="C"))
    digest.update(np.asarray(concept.state.uncertainty, dtype="<f8").tobytes())
    digest.update(str(concept.state.evidence_count).encode("ascii"))
    for event_id in concept.evidence_ids:
        digest.update(event_id.encode("ascii"))


def _metadata_json(metadata: Mapping[str, Any] | None) -> str:
    try:
        return json.dumps(
            dict(metadata or {}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("snapshot metadata must contain JSON values") from exc


@dataclass(frozen=True, eq=False)
class SemanticSnapshot:
    snapshot_id: str
    parent_snapshot_id: str | None
    origin: str
    concepts: tuple[SnapshotConcept, ...]
    metadata_json: str = "{}"

    @classmethod
    def create(
        cls,
        *,
        concepts: tuple[SnapshotConcept, ...] | list[SnapshotConcept],
        origin: str,
        parent_snapshot_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "SemanticSnapshot":
        origin_clean = str(origin).strip()
        if not origin_clean:
            raise ValueError("snapshot origin must not be empty")
        ordered = tuple(sorted(concepts, key=lambda item: item.term))
        terms = [concept.term for concept in ordered]
        if len(terms) != len(set(terms)):
            raise ValueError("snapshot concepts must have unique terms")
        metadata_json = _metadata_json(metadata)

        digest = hashlib.sha256()
        digest.update((parent_snapshot_id or "").encode("ascii"))
        digest.update(origin_clean.encode("utf-8"))
        digest.update(metadata_json.encode("utf-8"))
        for concept in ordered:
            _update_state_hash(digest, concept)
        snapshot_id = digest.hexdigest()
        return cls(
            snapshot_id=snapshot_id,
            parent_snapshot_id=parent_snapshot_id,
            origin=origin_clean,
            concepts=ordered,
            metadata_json=metadata_json,
        )

    @classmethod
    def from_materialized(cls, snapshot: MaterializedSnapshot) -> "SemanticSnapshot":
        return cls.create(
            concepts=[
                SnapshotConcept(
                    term=concept.term,
                    state=concept.state,
                    evidence_ids=concept.evidence_ids,
                )
                for concept in snapshot.concepts
            ],
            origin=f"materializer:{snapshot.materializer_version}",
            metadata={
                "ledger_digest": snapshot.ledger_digest,
                "materialized_snapshot_id": snapshot.snapshot_id,
                "state_digest": snapshot.state_digest,
            },
        )

    def get(self, term: str) -> SnapshotConcept | None:
        return next((concept for concept in self.concepts if concept.term == term), None)

    @property
    def metadata(self) -> dict[str, Any]:
        return json.loads(self.metadata_json)


@dataclass(frozen=True, eq=False)
class ConceptChange:
    term: str
    proposed_state: SemanticState | None
    evidence_ids: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        term = str(self.term).strip()
        reason = str(self.reason).strip()
        if not term:
            raise ValueError("change term must not be empty")
        object.__setattr__(self, "term", term)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))


@dataclass(frozen=True, eq=False)
class StateDelta:
    delta_id: str
    base_snapshot_id: str
    operator_id: str
    operator_version: str
    changes: tuple[ConceptChange, ...]
    confidence: float
    speculative: bool
    metadata_json: str = "{}"

    @classmethod
    def create(
        cls,
        *,
        base_snapshot_id: str,
        operator_id: str,
        operator_version: str,
        changes: tuple[ConceptChange, ...] | list[ConceptChange],
        confidence: float,
        speculative: bool,
        metadata: Mapping[str, Any] | None = None,
    ) -> "StateDelta":
        base_clean = str(base_snapshot_id).strip()
        operator_clean = str(operator_id).strip()
        version_clean = str(operator_version).strip()
        if not base_clean:
            raise ValueError("base_snapshot_id must not be empty")
        if not operator_clean or not version_clean:
            raise ValueError("operator id and version must not be empty")
        confidence_value = float(confidence)
        if not np.isfinite(confidence_value) or not 0.0 <= confidence_value <= 1.0:
            raise ValueError("confidence must be finite and in [0, 1]")
        if not isinstance(speculative, bool):
            raise ValueError("speculative must be a boolean")

        ordered = tuple(sorted(changes, key=lambda item: item.term))
        terms = [change.term for change in ordered]
        if len(terms) != len(set(terms)):
            raise ValueError("a delta cannot change the same term twice")
        metadata_json = _metadata_json(metadata)

        digest = hashlib.sha256()
        digest.update(base_clean.encode("ascii"))
        digest.update(operator_clean.encode("utf-8"))
        digest.update(version_clean.encode("utf-8"))
        digest.update(np.asarray(confidence_value, dtype="<f8").tobytes())
        digest.update(b"1" if speculative else b"0")
        digest.update(metadata_json.encode("utf-8"))
        for change in ordered:
            digest.update(change.term.encode("utf-8"))
            digest.update(change.reason.encode("utf-8"))
            if change.proposed_state is None:
                digest.update(b"DELETE")
            else:
                _update_state_hash(
                    digest,
                    SnapshotConcept(
                        term=change.term,
                        state=change.proposed_state,
                        evidence_ids=change.evidence_ids,
                    ),
                )
        return cls(
            delta_id=digest.hexdigest(),
            base_snapshot_id=base_clean,
            operator_id=operator_clean,
            operator_version=version_clean,
            changes=ordered,
            confidence=confidence_value,
            speculative=speculative,
            metadata_json=metadata_json,
        )

    @property
    def metadata(self) -> dict[str, Any]:
        return json.loads(self.metadata_json)


def apply_delta(base: SemanticSnapshot, delta: StateDelta) -> SemanticSnapshot:
    """Return a new snapshot; never mutate ``base`` or its state arrays."""
    if delta.base_snapshot_id != base.snapshot_id:
        raise ValueError("delta base_snapshot_id does not match the supplied snapshot")

    concepts = {concept.term: concept for concept in base.concepts}
    for change in delta.changes:
        if change.proposed_state is None:
            concepts.pop(change.term, None)
        else:
            concepts[change.term] = SnapshotConcept(
                term=change.term,
                state=change.proposed_state,
                evidence_ids=change.evidence_ids,
            )

    return SemanticSnapshot.create(
        concepts=list(concepts.values()),
        origin=f"operator:{delta.operator_id}@{delta.operator_version}",
        parent_snapshot_id=base.snapshot_id,
        metadata={
            "delta_id": delta.delta_id,
            "confidence": delta.confidence,
            "speculative": delta.speculative,
            "operator_metadata": delta.metadata,
        },
    )
