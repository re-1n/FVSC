"""Deterministic evidence-to-state materialization for FVSC.

The default encoder is a reproducible baseline compatible with the current
prototype's role-rotation idea.  It is deliberately replaceable: learned
contextual encoders and calibrated relation channels can implement the same
``EvidenceEncoder`` protocol without changing ledger or snapshot contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
from typing import Protocol

import numpy as np

from ..evidence import EvidenceEvent, EvidenceLedger
from ..semantic import SemanticState


_EPS = 1e-12


@dataclass(frozen=True, eq=False)
class Contribution:
    """One event contribution to one concept operator."""

    term: str
    vector: np.ndarray
    weight: float
    event_id: str
    role: str

    def __post_init__(self) -> None:
        term = str(self.term).strip()
        role = str(self.role).strip()
        vector = np.asarray(self.vector, dtype=float)
        weight = float(self.weight)
        if not term:
            raise ValueError("contribution term must not be empty")
        if not role:
            raise ValueError("contribution role must not be empty")
        if vector.ndim != 1 or vector.size == 0:
            raise ValueError("contribution vector must be one-dimensional")
        if not np.all(np.isfinite(vector)):
            raise ValueError("contribution vector must be finite")
        norm = float(np.linalg.norm(vector))
        if norm <= _EPS:
            raise ValueError("contribution vector must be non-zero")
        if not np.isfinite(weight) or weight < 0.0:
            raise ValueError("contribution weight must be finite and non-negative")
        vector = np.array(vector / norm, dtype=float, copy=True)
        vector.setflags(write=False)
        object.__setattr__(self, "term", term)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "vector", vector)
        object.__setattr__(self, "weight", weight)


class EvidenceEncoder(Protocol):
    dim: int
    version: str

    def encode(self, event: EvidenceEvent) -> tuple[Contribution, ...]: ...


@lru_cache(maxsize=2048)
def _base_vector(term: str, dim: int) -> np.ndarray:
    digest = hashlib.sha256(f"term:{term}".encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "little", signed=False)
    rng = np.random.default_rng(seed)
    vector = rng.standard_normal(dim)
    vector /= np.linalg.norm(vector) + _EPS
    vector.setflags(write=False)
    return vector


@lru_cache(maxsize=256)
def _role_matrix(role: str, dim: int) -> np.ndarray:
    digest = hashlib.sha256(f"role:{role}".encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "little", signed=False)
    rng = np.random.default_rng(seed)
    matrix = rng.standard_normal((dim, dim))
    orthogonal, _ = np.linalg.qr(matrix)
    orthogonal.setflags(write=False)
    return orthogonal


@dataclass(frozen=True)
class DeterministicEvidenceEncoder:
    """Reproducible baseline encoder, not a claim of learned semantics."""

    dim: int = 64
    version: str = "deterministic-role-baseline-v1"
    subject_share: float = 1.0
    object_share: float = 0.5
    relation_share: float = 0.2
    excluded_terms: frozenset[str] = frozenset()
    excluded_relations: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if isinstance(self.dim, bool) or not isinstance(self.dim, int) or self.dim <= 0:
            raise ValueError("dim must be a positive integer")
        for name in ("subject_share", "object_share", "relation_share"):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
            object.__setattr__(self, name, value)
        object.__setattr__(
            self,
            "excluded_terms",
            frozenset(str(term).casefold() for term in self.excluded_terms),
        )
        object.__setattr__(
            self,
            "excluded_relations",
            frozenset(str(relation).casefold() for relation in self.excluded_relations),
        )

    def _rotate(self, term: str, role: str) -> np.ndarray:
        vector = _role_matrix(role, self.dim) @ _base_vector(term, self.dim)
        return vector / (np.linalg.norm(vector) + _EPS)

    def _combine(self, primary: np.ndarray, relation: np.ndarray, event: EvidenceEvent) -> np.ndarray:
        vector = primary + event.polarity * event.intensity * relation
        norm = float(np.linalg.norm(vector))
        if norm <= _EPS:
            return primary
        return vector / norm

    def encode(self, event: EvidenceEvent) -> tuple[Contribution, ...]:
        if event.event_kind not in {"assertion", "supersession"}:
            return ()
        if event.subject is None or event.relation is None or event.object is None:
            return ()
        if event.relation.casefold() in self.excluded_relations:
            return ()

        base_weight = event.modality * event.intensity * event.confidence
        if base_weight <= _EPS:
            return ()

        subject_relation = self._rotate(event.relation, "relation_in_subject")
        object_relation = self._rotate(event.relation, "relation_in_object")
        subject_vector = self._combine(
            self._rotate(event.object, "object_in_subject"),
            subject_relation,
            event,
        )
        object_vector = self._combine(
            self._rotate(event.subject, "subject_in_object"),
            object_relation,
            event,
        )
        relation_vector = _base_vector(event.relation, self.dim)

        candidates = (
            (event.subject, subject_vector, base_weight * self.subject_share, "subject"),
            (event.object, object_vector, base_weight * self.object_share, "object"),
            (event.relation, relation_vector, base_weight * self.relation_share, "relation"),
        )
        return tuple(
            Contribution(
                term=term,
                vector=vector,
                weight=weight,
                event_id=event.event_id,
                role=role,
            )
            for term, vector, weight, role in candidates
            if term.casefold() not in self.excluded_terms and weight > _EPS
        )


@dataclass(frozen=True, eq=False)
class MaterializedConcept:
    term: str
    state: SemanticState
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, eq=False)
class MaterializedSnapshot:
    """Immutable deterministic projection of one ledger state."""

    materializer_version: str
    ledger_digest: str
    state_digest: str
    snapshot_id: str
    concepts: tuple[MaterializedConcept, ...]

    def get(self, term: str) -> MaterializedConcept | None:
        return next((concept for concept in self.concepts if concept.term == term), None)

    @property
    def concept_count(self) -> int:
        return len(self.concepts)


def _state_digest(
    *,
    encoder: EvidenceEncoder,
    concepts: tuple[MaterializedConcept, ...],
) -> str:
    digest = hashlib.sha256()
    digest.update(encoder.version.encode("utf-8"))
    digest.update(str(encoder.dim).encode("ascii"))
    for concept in concepts:
        digest.update(concept.term.encode("utf-8"))
        digest.update(np.asarray(concept.state.mass, dtype="<f8").tobytes())
        digest.update(np.asarray(concept.state.shape, dtype="<f8").tobytes(order="C"))
        for event_id in concept.evidence_ids:
            digest.update(event_id.encode("ascii"))
    return digest.hexdigest()


def materialize_ledger(
    ledger: EvidenceLedger,
    *,
    encoder: EvidenceEncoder | None = None,
) -> MaterializedSnapshot:
    """Materialize active evidence into normalized concept states."""
    encoder = encoder or DeterministicEvidenceEncoder()
    operators: dict[str, np.ndarray] = {}
    evidence_refs: dict[str, set[str]] = {}

    for event in sorted(ledger.active_events, key=lambda item: item.event_id):
        for contribution in encoder.encode(event):
            if contribution.vector.shape != (encoder.dim,):
                raise ValueError(
                    f"encoder returned vector shape {contribution.vector.shape}; expected {(encoder.dim,)}"
                )
            operator = operators.setdefault(
                contribution.term,
                np.zeros((encoder.dim, encoder.dim), dtype=float),
            )
            vector = contribution.vector.reshape(-1, 1)
            operator += contribution.weight * (vector @ vector.T)
            evidence_refs.setdefault(contribution.term, set()).add(contribution.event_id)

    concepts = tuple(
        MaterializedConcept(
            term=term,
            state=SemanticState.from_operator(
                operators[term],
                evidence_count=len(evidence_refs[term]),
            ),
            evidence_ids=tuple(sorted(evidence_refs[term])),
        )
        for term in sorted(operators)
        if float(np.trace(operators[term])) > _EPS
    )
    state_digest = _state_digest(encoder=encoder, concepts=concepts)
    snapshot_id = hashlib.sha256(
        f"{ledger.digest}:{state_digest}".encode("ascii")
    ).hexdigest()
    return MaterializedSnapshot(
        materializer_version=encoder.version,
        ledger_digest=ledger.digest,
        state_digest=state_digest,
        snapshot_id=snapshot_id,
        concepts=concepts,
    )
