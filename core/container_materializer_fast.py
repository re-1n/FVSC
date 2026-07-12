"""Fast deterministic materializer for explicit semantic containers.

The original ContainerCore v1 uses a QR decomposition for every evidence-backed
projection operator.  QR is unnecessary for the first falsification experiment: a
signed permutation matrix is also orthogonal, norm-preserving, generally
non-commutative and direction/context dependent, while taking linear time to build.

This module changes only the deterministic projection baseline.  The evidence ledger,
container contracts, local density states and query semantics remain unchanged.
"""
from __future__ import annotations

import hashlib
import json
from typing import Sequence

import numpy as np

from .container_core import (
    ContainerContribution,
    ContainerEmbedding,
    ContainerFacet,
    ContainerSnapshot,
    SemanticContainer,
    normalize_context_keys,
)
from .evidence_ledger import EvidenceLedger
from .materializer import DeterministicEvidenceEncoder, EvidenceEncoder
from .semantic_state import SemanticState


FAST_CONTAINER_VERSION = "explicit-container-core-signed-permutation-v1"
_EPS = 1e-12


def _digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _uncertainty(operator: np.ndarray) -> float:
    mass = float(np.trace(operator))
    if mass <= _EPS:
        return 1.0
    shape = operator / mass
    return float(np.clip(1.0 - np.trace(shape @ shape), 0.0, 1.0))


def signed_permutation_operator(
    parent_id: str,
    child_id: str,
    role: str,
    context_keys: Sequence[str],
    dim: int,
) -> np.ndarray:
    """Return a deterministic orthogonal operator without QR decomposition."""
    if isinstance(dim, bool) or not isinstance(dim, int) or dim <= 0:
        raise ValueError("dim must be a positive integer")
    identity = json.dumps(
        {
            "version": FAST_CONTAINER_VERSION,
            "parent": str(parent_id),
            "child": str(child_id),
            "role": str(role),
            "context": list(context_keys),
            "dim": dim,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    seed = int.from_bytes(hashlib.sha256(identity.encode("utf-8")).digest()[:8], "little")
    rng = np.random.default_rng(seed)
    permutation = rng.permutation(dim)
    signs = rng.integers(0, 2, size=dim, dtype=np.int8).astype(float)
    signs = 2.0 * signs - 1.0
    operator = np.zeros((dim, dim), dtype=float)
    operator[np.arange(dim), permutation] = signs
    operator.setflags(write=False)
    return operator


def _snapshot_id(
    *,
    ledger_digest: str,
    dim: int,
    containers: Sequence[SemanticContainer],
    embeddings: Sequence[ContainerEmbedding],
) -> str:
    payload = {
        "version": FAST_CONTAINER_VERSION,
        "ledger_digest": ledger_digest,
        "dim": dim,
        "containers": [
            {
                "id": item.container_id,
                "contributions": [part.contribution_id for part in item.contributions],
                "facets": [facet.facet_id for facet in item.facets],
            }
            for item in sorted(containers, key=lambda value: value.container_id)
        ],
        "embeddings": [
            item.embedding_id
            for item in sorted(embeddings, key=lambda value: value.embedding_id)
        ],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def materialize_fast_container_ledger(
    ledger: EvidenceLedger,
    *,
    encoder: EvidenceEncoder | None = None,
) -> ContainerSnapshot:
    """Materialize active evidence using signed-permutation projection operators."""
    if not isinstance(ledger, EvidenceLedger):
        raise TypeError("ledger must be an EvidenceLedger")
    encoder = encoder or DeterministicEvidenceEncoder()
    dim = int(encoder.dim)
    if dim <= 0:
        raise ValueError("encoder dimension must be positive")

    contributions_by_container: dict[str, list[ContainerContribution]] = {}
    embeddings: list[ContainerEmbedding] = []
    known_container_ids: set[str] = set()

    for event in sorted(ledger.active_events, key=lambda item: item.event_id):
        if event.event_kind not in {"assertion", "supersession"}:
            continue
        for contribution in encoder.encode(event):
            vector = np.asarray(contribution.vector, dtype=float)
            if vector.shape != (dim,):
                raise ValueError("encoder contribution dimension does not match encoder.dim")
            contribution_id = _digest(
                FAST_CONTAINER_VERSION,
                event.event_id,
                contribution.term,
                contribution.role,
            )
            item = ContainerContribution(
                contribution_id=contribution_id,
                container_id=contribution.term,
                event_id=event.event_id,
                role=contribution.role,
                weight=float(contribution.weight),
                operator=np.outer(vector, vector),
            )
            contributions_by_container.setdefault(item.container_id, []).append(item)
            known_container_ids.add(item.container_id)

        if event.subject is None or event.object is None or event.relation is None:
            continue
        if event.subject == event.object:
            continue
        context_keys = normalize_context_keys((
            event.context,
            event.provenance,
            event.relation,
            event.source_id,
        ))
        weight = float(event.modality * event.intensity * event.confidence)
        embedding_id = _digest(
            FAST_CONTAINER_VERSION,
            event.event_id,
            event.subject,
            event.object,
            event.relation,
            json.dumps(context_keys, ensure_ascii=False),
        )
        embeddings.append(ContainerEmbedding(
            embedding_id=embedding_id,
            parent_id=event.subject,
            child_id=event.object,
            role=event.relation,
            context_keys=context_keys,
            weight=weight,
            polarity=event.polarity,
            operator=signed_permutation_operator(
                event.subject,
                event.object,
                event.relation,
                context_keys,
                dim,
            ),
            evidence_ids=(event.event_id,),
        ))
        known_container_ids.update((event.subject, event.object, event.relation))

    outgoing_groups: dict[str, dict[tuple[str, str], list[ContainerEmbedding]]] = {}
    for embedding in embeddings:
        outgoing_groups.setdefault(embedding.parent_id, {}).setdefault(
            (embedding.child_id, embedding.role),
            [],
        ).append(embedding)

    containers: list[SemanticContainer] = []
    for container_id in sorted(known_container_ids):
        contributions = tuple(sorted(
            contributions_by_container.get(container_id, ()),
            key=lambda item: item.contribution_id,
        ))
        operator = np.zeros((dim, dim), dtype=float)
        evidence_ids: set[str] = set()
        for contribution in contributions:
            operator += contribution.weight * contribution.operator
            evidence_ids.add(contribution.event_id)

        facets: list[ContainerFacet] = []
        for (child_id, role), members in sorted(
            outgoing_groups.get(container_id, {}).items(),
            key=lambda pair: pair[0],
        ):
            facet_evidence = tuple(sorted({
                evidence_id
                for item in members
                for evidence_id in item.evidence_ids
            }))
            facet_id = _digest(
                FAST_CONTAINER_VERSION,
                container_id,
                child_id,
                role,
                *facet_evidence,
            )
            facets.append(ContainerFacet(
                facet_id=facet_id,
                child_id=child_id,
                role=role,
                weight=sum(item.positive_weight for item in members),
                evidence_ids=facet_evidence,
            ))
            evidence_ids.update(facet_evidence)

        containers.append(SemanticContainer(
            container_id=container_id,
            local_state=SemanticState.from_operator(
                operator,
                uncertainty=_uncertainty(operator),
                evidence_count=len({item.event_id for item in contributions}),
            ),
            contributions=contributions,
            facets=tuple(facets),
            evidence_ids=tuple(sorted(evidence_ids)),
        ))

    snapshot_id = _snapshot_id(
        ledger_digest=ledger.digest,
        dim=dim,
        containers=containers,
        embeddings=embeddings,
    )
    return ContainerSnapshot(
        version=FAST_CONTAINER_VERSION,
        ledger_digest=ledger.digest,
        snapshot_id=snapshot_id,
        dim=dim,
        containers=tuple(containers),
        embeddings=tuple(embeddings),
    )
