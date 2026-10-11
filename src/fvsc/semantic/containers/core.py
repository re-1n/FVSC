"""Explicit asymmetric recursive container semantics for FVSC.

The evidence ledger remains the canonical source of truth. This module derives a
versioned container snapshot in which each concept owns local evidence contributions
and directed embeddings into child containers. Reverse embeddings are never inferred:
``A <- B`` and ``B <- A`` are independent evidence-backed structures.

The implementation is intentionally conservative:

* embeddings store references and projection operators, not copied child states;
* recursive activation is depth-bounded and path-cycle-safe;
* contribution identifiers prevent one local contribution from being counted twice;
* every container, facet and embedding retains evidence identifiers;
* density matrices are local container state, not the canonical memory format.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from ...evidence import EvidenceEvent
from ...evidence import EvidenceLedger
from ...runtime import DeterministicEvidenceEncoder, EvidenceEncoder
from ..metrics import operator_inclusion
from ..state import SemanticState


CONTAINER_CORE_VERSION = "explicit-container-core-v1"
_EPS = 1e-12
_TOKEN_RE = re.compile(r"[\w'-]+", flags=re.UNICODE)


def _stable_digest(*parts: str) -> str:
    payload = "\0".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clean_identifier(value: str, *, field_name: str) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _bounded(value: float, *, lower: float = 0.0, upper: float = 1.0) -> float:
    number = float(value)
    if not math.isfinite(number) or not lower <= number <= upper:
        raise ValueError(f"value must be finite and in [{lower:g}, {upper:g}]")
    return number


def _read_only_matrix(value: np.ndarray, *, dim: int, name: str) -> np.ndarray:
    matrix = np.asarray(value, dtype=float)
    if matrix.shape != (dim, dim):
        raise ValueError(f"{name} must have shape {(dim, dim)}")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain finite values")
    result = np.array(matrix, dtype=float, copy=True)
    result.setflags(write=False)
    return result


def _read_only_psd(value: np.ndarray, *, dim: int, name: str) -> np.ndarray:
    matrix = _read_only_matrix(value, dim=dim, name=name)
    symmetric = 0.5 * (matrix + matrix.T)
    if not np.allclose(matrix, symmetric, atol=1e-8, rtol=0.0):
        raise ValueError(f"{name} must be symmetric")
    eigenvalues = np.linalg.eigvalsh(symmetric)
    if float(eigenvalues[0]) < -1e-8:
        raise ValueError(f"{name} must be positive semidefinite")
    result = np.array(symmetric, dtype=float, copy=True)
    result.setflags(write=False)
    return result


def _json_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
            yield str(key)
            yield from _json_strings(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            yield from _json_strings(item)


def normalize_context_keys(values: Iterable[Any], *, limit: int = 64) -> tuple[str, ...]:
    """Return deterministic bounded context tokens for gates and operator identity."""
    if limit < 1:
        raise ValueError("limit must be positive")
    keys: set[str] = set()
    for value in values:
        for text in _json_strings(value):
            for token in _TOKEN_RE.findall(text.casefold()):
                if 1 < len(token) <= 64:
                    keys.add(token)
                    if len(keys) >= limit:
                        return tuple(sorted(keys))
    return tuple(sorted(keys))


def _orthogonal_operator(
    parent_id: str,
    child_id: str,
    role: str,
    context_keys: Sequence[str],
    dim: int,
) -> np.ndarray:
    identity = json.dumps(
        {
            "parent": parent_id,
            "child": child_id,
            "role": role,
            "context": list(context_keys),
            "dim": dim,
            "version": CONTAINER_CORE_VERSION,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    seed = int.from_bytes(hashlib.sha256(identity.encode("utf-8")).digest()[:8], "little")
    rng = np.random.default_rng(seed)
    matrix = rng.standard_normal((dim, dim))
    orthogonal, upper = np.linalg.qr(matrix)
    signs = np.sign(np.diag(upper))
    signs[signs == 0.0] = 1.0
    orthogonal = orthogonal * signs
    orthogonal = np.array(orthogonal, dtype=float, copy=True)
    orthogonal.setflags(write=False)
    return orthogonal


def _uncertainty(operator: np.ndarray) -> float:
    mass = float(np.trace(operator))
    if mass <= _EPS:
        return 1.0
    shape = operator / mass
    purity = float(np.trace(shape @ shape))
    return float(np.clip(1.0 - purity, 0.0, 1.0))


@dataclass(frozen=True, eq=False)
class ContainerContribution:
    """One local evidence contribution to one semantic container."""

    contribution_id: str
    container_id: str
    event_id: str
    role: str
    weight: float
    operator: np.ndarray

    def __post_init__(self) -> None:
        contribution_id = _clean_identifier(self.contribution_id, field_name="contribution_id")
        container_id = _clean_identifier(self.container_id, field_name="container_id")
        event_id = _clean_identifier(self.event_id, field_name="event_id")
        role = _clean_identifier(self.role, field_name="role")
        weight = float(self.weight)
        if not math.isfinite(weight) or weight < 0.0:
            raise ValueError("contribution weight must be finite and non-negative")
        matrix = np.asarray(self.operator, dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or matrix.shape[0] == 0:
            raise ValueError("contribution operator must be a non-empty square matrix")
        operator = _read_only_psd(matrix, dim=matrix.shape[0], name="contribution operator")
        trace = float(np.trace(operator))
        if weight > _EPS and trace <= _EPS:
            raise ValueError("positive contribution weight requires a non-empty operator")
        if trace > _EPS:
            operator = np.array(operator / trace, dtype=float, copy=True)
            operator.setflags(write=False)
        object.__setattr__(self, "contribution_id", contribution_id)
        object.__setattr__(self, "container_id", container_id)
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "weight", weight)
        object.__setattr__(self, "operator", operator)

    @property
    def dim(self) -> int:
        return int(self.operator.shape[0])


@dataclass(frozen=True)
class ContainerFacet:
    """Evidence-backed outgoing facet exposed by a container."""

    facet_id: str
    child_id: str
    role: str
    weight: float
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "facet_id", _clean_identifier(self.facet_id, field_name="facet_id"))
        object.__setattr__(self, "child_id", _clean_identifier(self.child_id, field_name="child_id"))
        object.__setattr__(self, "role", _clean_identifier(self.role, field_name="role"))
        weight = float(self.weight)
        if not math.isfinite(weight) or weight < 0.0:
            raise ValueError("facet weight must be finite and non-negative")
        object.__setattr__(self, "weight", weight)
        evidence_ids = tuple(sorted({_clean_identifier(item, field_name="evidence_id") for item in self.evidence_ids}))
        object.__setattr__(self, "evidence_ids", evidence_ids)


@dataclass(frozen=True, eq=False)
class ContainerEmbedding:
    """A directed child-to-parent projection backed by one evidence event."""

    embedding_id: str
    parent_id: str
    child_id: str
    role: str
    context_keys: tuple[str, ...]
    weight: float
    polarity: float
    operator: np.ndarray
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        embedding_id = _clean_identifier(self.embedding_id, field_name="embedding_id")
        parent_id = _clean_identifier(self.parent_id, field_name="parent_id")
        child_id = _clean_identifier(self.child_id, field_name="child_id")
        role = _clean_identifier(self.role, field_name="role")
        if parent_id == child_id:
            raise ValueError("container embedding cannot be a self-loop")
        context_keys = normalize_context_keys(self.context_keys)
        weight = _bounded(self.weight)
        polarity = _bounded(self.polarity, lower=-1.0, upper=1.0)
        matrix = np.asarray(self.operator, dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or matrix.shape[0] == 0:
            raise ValueError("embedding operator must be a non-empty square matrix")
        operator = _read_only_matrix(matrix, dim=matrix.shape[0], name="embedding operator")
        evidence_ids = tuple(sorted({_clean_identifier(item, field_name="evidence_id") for item in self.evidence_ids}))
        if not evidence_ids:
            raise ValueError("embedding requires at least one evidence id")
        object.__setattr__(self, "embedding_id", embedding_id)
        object.__setattr__(self, "parent_id", parent_id)
        object.__setattr__(self, "child_id", child_id)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "context_keys", context_keys)
        object.__setattr__(self, "weight", weight)
        object.__setattr__(self, "polarity", polarity)
        object.__setattr__(self, "operator", operator)
        object.__setattr__(self, "evidence_ids", evidence_ids)

    @property
    def dim(self) -> int:
        return int(self.operator.shape[0])

    @property
    def positive_weight(self) -> float:
        """Containment strength contributed by positive evidence only."""
        return self.weight * max(0.0, self.polarity)

    def context_affinity(self, query_context: Sequence[str], *, floor: float = 0.1) -> float:
        floor = _bounded(floor)
        query = frozenset(normalize_context_keys(query_context))
        if not query:
            return 1.0
        available = frozenset(
            normalize_context_keys(
                (*self.context_keys, self.parent_id, self.child_id, self.role)
            )
        )
        overlap = len(query & available) / len(query)
        return float(floor + (1.0 - floor) * overlap)


@dataclass(frozen=True, eq=False)
class SemanticContainer:
    """One explicit container with local state and evidence-backed facets."""

    container_id: str
    local_state: SemanticState
    contributions: tuple[ContainerContribution, ...]
    facets: tuple[ContainerFacet, ...]
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        container_id = _clean_identifier(self.container_id, field_name="container_id")
        contributions = tuple(sorted(self.contributions, key=lambda item: item.contribution_id))
        facets = tuple(sorted(self.facets, key=lambda item: item.facet_id))
        for contribution in contributions:
            if contribution.container_id != container_id:
                raise ValueError("contribution belongs to another container")
            if contribution.dim != self.local_state.dim:
                raise ValueError("contribution dimension does not match local state")
        evidence_ids = tuple(sorted({_clean_identifier(item, field_name="evidence_id") for item in self.evidence_ids}))
        object.__setattr__(self, "container_id", container_id)
        object.__setattr__(self, "contributions", contributions)
        object.__setattr__(self, "facets", facets)
        object.__setattr__(self, "evidence_ids", evidence_ids)


@dataclass(frozen=True, eq=False)
class ContainerActivation:
    root_id: str
    context_keys: tuple[str, ...]
    state: SemanticState
    activated_container_ids: tuple[str, ...]
    traversed_embedding_ids: tuple[str, ...]
    contribution_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    path_count: int
    max_depth: int


@dataclass(frozen=True, eq=False)
class ContainerProjection:
    parent_id: str
    child_id: str
    context_keys: tuple[str, ...]
    state: SemanticState
    path_strength: float
    path_count: int
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, eq=False)
class ContainerSnapshot:
    """Immutable explicit-container projection of one active ledger state."""

    version: str
    ledger_digest: str
    snapshot_id: str
    dim: int
    containers: tuple[SemanticContainer, ...]
    embeddings: tuple[ContainerEmbedding, ...]
    _container_by_id: Mapping[str, SemanticContainer] = field(init=False, repr=False, compare=False)
    _outgoing_by_id: Mapping[str, tuple[ContainerEmbedding, ...]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if isinstance(self.dim, bool) or not isinstance(self.dim, int) or self.dim <= 0:
            raise ValueError("dim must be a positive integer")
        containers = tuple(sorted(self.containers, key=lambda item: item.container_id))
        embeddings = tuple(sorted(self.embeddings, key=lambda item: item.embedding_id))
        by_id: dict[str, SemanticContainer] = {}
        for container in containers:
            if container.container_id in by_id:
                raise ValueError(f"duplicate container: {container.container_id}")
            if container.local_state.dim != self.dim:
                raise ValueError("container dimension does not match snapshot")
            by_id[container.container_id] = container
        outgoing: dict[str, list[ContainerEmbedding]] = {key: [] for key in by_id}
        for embedding in embeddings:
            if embedding.dim != self.dim:
                raise ValueError("embedding dimension does not match snapshot")
            if embedding.parent_id not in by_id or embedding.child_id not in by_id:
                raise ValueError("embedding references an unknown container")
            outgoing[embedding.parent_id].append(embedding)
        object.__setattr__(self, "containers", containers)
        object.__setattr__(self, "embeddings", embeddings)
        object.__setattr__(self, "_container_by_id", MappingProxyType(by_id))
        object.__setattr__(
            self,
            "_outgoing_by_id",
            MappingProxyType({key: tuple(sorted(value, key=lambda item: item.embedding_id)) for key, value in outgoing.items()}),
        )

    @property
    def container_count(self) -> int:
        return len(self.containers)

    @property
    def embedding_count(self) -> int:
        return len(self.embeddings)

    def get(self, container_id: str) -> SemanticContainer | None:
        return self._container_by_id.get(str(container_id).strip())

    def outgoing(self, container_id: str) -> tuple[ContainerEmbedding, ...]:
        return self._outgoing_by_id.get(str(container_id).strip(), ())

    def direct_embeddings(self, parent_id: str, child_id: str) -> tuple[ContainerEmbedding, ...]:
        child = str(child_id).strip()
        return tuple(item for item in self.outgoing(parent_id) if item.child_id == child)

    def _paths(
        self,
        parent_id: str,
        child_id: str,
        *,
        context_keys: Sequence[str],
        max_depth: int,
        decay: float,
        context_floor: float,
        min_strength: float,
    ) -> list[tuple[float, np.ndarray, tuple[str, ...], tuple[str, ...]]]:
        if max_depth < 1:
            return []
        parent = _clean_identifier(parent_id, field_name="parent_id")
        child = _clean_identifier(child_id, field_name="child_id")
        if parent not in self._container_by_id or child not in self._container_by_id:
            return []
        if parent == child:
            return [(1.0, np.eye(self.dim), (), ())]
        decay = _bounded(decay)
        context_floor = _bounded(context_floor)
        if not math.isfinite(min_strength) or min_strength < 0.0:
            raise ValueError("min_strength must be finite and non-negative")
        query = normalize_context_keys(context_keys)
        results: list[tuple[float, np.ndarray, tuple[str, ...], tuple[str, ...]]] = []

        def visit(
            current: str,
            transform: np.ndarray,
            strength: float,
            depth: int,
            path: tuple[str, ...],
            embedding_ids: tuple[str, ...],
            evidence_ids: tuple[str, ...],
        ) -> None:
            if depth >= max_depth:
                return
            for embedding in self.outgoing(current):
                if embedding.child_id in path:
                    continue
                affinity = embedding.context_affinity(query, floor=context_floor)
                edge_strength = strength * decay * embedding.positive_weight * affinity
                if edge_strength <= min_strength:
                    continue
                next_transform = transform @ embedding.operator
                next_embedding_ids = (*embedding_ids, embedding.embedding_id)
                next_evidence = tuple(sorted({*evidence_ids, *embedding.evidence_ids}))
                if embedding.child_id == child:
                    results.append((edge_strength, next_transform, next_embedding_ids, next_evidence))
                visit(
                    embedding.child_id,
                    next_transform,
                    edge_strength,
                    depth + 1,
                    (*path, embedding.child_id),
                    next_embedding_ids,
                    next_evidence,
                )

        visit(parent, np.eye(self.dim), 1.0, 0, (parent,), (), ())
        return sorted(results, key=lambda item: (-item[0], item[2]))

    def structure_score(
        self,
        parent_id: str,
        child_id: str,
        *,
        context: Sequence[str] = (),
        max_depth: int = 3,
        decay: float = 0.75,
        context_floor: float = 0.1,
    ) -> float:
        """Return the strongest bounded directed containment path."""
        paths = self._paths(
            parent_id,
            child_id,
            context_keys=context,
            max_depth=max_depth,
            decay=decay,
            context_floor=context_floor,
            min_strength=_EPS,
        )
        return float(np.clip(paths[0][0] if paths else 0.0, 0.0, 1.0))

    def activate(
        self,
        root_id: str,
        *,
        context: Sequence[str] = (),
        max_depth: int = 3,
        decay: float = 0.75,
        context_floor: float = 0.1,
        min_strength: float = 1e-8,
    ) -> ContainerActivation:
        """Activate a bounded recursive neighbourhood without double-counting contributions."""
        root = _clean_identifier(root_id, field_name="root_id")
        if root not in self._container_by_id:
            return ContainerActivation(
                root_id=root,
                context_keys=normalize_context_keys(context),
                state=SemanticState.empty(self.dim),
                activated_container_ids=(),
                traversed_embedding_ids=(),
                contribution_ids=(),
                evidence_ids=(),
                path_count=0,
                max_depth=max_depth,
            )
        if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 0:
            raise ValueError("max_depth must be a non-negative integer")
        decay = _bounded(decay)
        context_floor = _bounded(context_floor)
        if not math.isfinite(min_strength) or min_strength < 0.0:
            raise ValueError("min_strength must be finite and non-negative")
        query = normalize_context_keys(context)
        operator = np.zeros((self.dim, self.dim), dtype=float)
        selected_contributions: dict[str, tuple[float, np.ndarray, str]] = {}
        evidence_ids: set[str] = set()
        activated: set[str] = set()
        traversed: set[str] = set()
        path_count = 0

        def visit(
            current: str,
            transform: np.ndarray,
            strength: float,
            depth: int,
            path: tuple[str, ...],
        ) -> None:
            nonlocal path_count
            activated.add(current)
            container = self._container_by_id[current]
            for contribution in container.contributions:
                effective = strength * contribution.weight
                if effective <= min_strength:
                    continue
                previous = selected_contributions.get(contribution.contribution_id)
                if previous is None or effective > previous[0] + _EPS:
                    projected = transform @ contribution.operator @ transform.T
                    selected_contributions[contribution.contribution_id] = (
                        effective,
                        projected,
                        contribution.event_id,
                    )
            if depth >= max_depth:
                return
            for embedding in self.outgoing(current):
                if embedding.child_id in path:
                    continue
                affinity = embedding.context_affinity(query, floor=context_floor)
                edge_strength = strength * decay * embedding.positive_weight * affinity
                if edge_strength <= min_strength:
                    continue
                traversed.add(embedding.embedding_id)
                evidence_ids.update(embedding.evidence_ids)
                path_count += 1
                visit(
                    embedding.child_id,
                    transform @ embedding.operator,
                    edge_strength,
                    depth + 1,
                    (*path, embedding.child_id),
                )

        visit(root, np.eye(self.dim), 1.0, 0, (root,))
        for effective, projected, event_id in selected_contributions.values():
            operator += effective * projected
            evidence_ids.add(event_id)
        state = SemanticState.from_operator(
            operator,
            uncertainty=_uncertainty(operator),
            evidence_count=len(evidence_ids),
        )
        return ContainerActivation(
            root_id=root,
            context_keys=query,
            state=state,
            activated_container_ids=tuple(sorted(activated)),
            traversed_embedding_ids=tuple(sorted(traversed)),
            contribution_ids=tuple(sorted(selected_contributions)),
            evidence_ids=tuple(sorted(evidence_ids)),
            path_count=path_count,
            max_depth=max_depth,
        )

    def project(
        self,
        parent_id: str,
        child_id: str,
        *,
        context: Sequence[str] = (),
        max_depth: int = 3,
        decay: float = 0.75,
        context_floor: float = 0.1,
    ) -> ContainerProjection:
        """Project one child's local state through its strongest evidence-backed paths."""
        parent = _clean_identifier(parent_id, field_name="parent_id")
        child = _clean_identifier(child_id, field_name="child_id")
        query = normalize_context_keys(context)
        child_container = self.get(child)
        if child_container is None:
            return ContainerProjection(
                parent_id=parent,
                child_id=child,
                context_keys=query,
                state=SemanticState.empty(self.dim),
                path_strength=0.0,
                path_count=0,
                evidence_ids=(),
            )
        paths = self._paths(
            parent,
            child,
            context_keys=query,
            max_depth=max_depth,
            decay=decay,
            context_floor=context_floor,
            min_strength=_EPS,
        )
        if not paths:
            return ContainerProjection(
                parent_id=parent,
                child_id=child,
                context_keys=query,
                state=SemanticState.empty(self.dim),
                path_strength=0.0,
                path_count=0,
                evidence_ids=(),
            )

        selected: dict[str, tuple[float, np.ndarray, str]] = {}
        evidence_ids: set[str] = set()
        for path_strength, transform, _embedding_ids, path_evidence in paths:
            evidence_ids.update(path_evidence)
            for contribution in child_container.contributions:
                effective = path_strength * contribution.weight
                previous = selected.get(contribution.contribution_id)
                if previous is None or effective > previous[0] + _EPS:
                    projected = transform @ contribution.operator @ transform.T
                    selected[contribution.contribution_id] = (
                        effective,
                        projected,
                        contribution.event_id,
                    )

        operator = np.zeros((self.dim, self.dim), dtype=float)
        for effective, projected, event_id in selected.values():
            operator += effective * projected
            evidence_ids.add(event_id)
        state = SemanticState.from_operator(
            operator,
            uncertainty=_uncertainty(operator),
            evidence_count=len(evidence_ids),
        )
        return ContainerProjection(
            parent_id=parent,
            child_id=child,
            context_keys=query,
            state=state,
            path_strength=float(np.clip(paths[0][0], 0.0, 1.0)),
            path_count=len(paths),
            evidence_ids=tuple(sorted(evidence_ids)),
        )

    def density_score(
        self,
        parent_id: str,
        child_id: str,
        *,
        context: Sequence[str] = (),
        max_depth: int = 3,
        decay: float = 0.75,
        context_floor: float = 0.1,
    ) -> float:
        """Score projected child inclusion in the context-activated parent container."""
        projection = self.project(
            parent_id,
            child_id,
            context=context,
            max_depth=max_depth,
            decay=decay,
            context_floor=context_floor,
        )
        if projection.state.is_empty:
            return 0.0
        activation = self.activate(
            parent_id,
            context=context,
            max_depth=max_depth,
            decay=decay,
            context_floor=context_floor,
        )
        if activation.state.is_empty:
            return 0.0
        inclusion = operator_inclusion(projection.state, activation.state)
        return float(np.clip(projection.path_strength * inclusion, 0.0, 1.0))

    def hybrid_score(
        self,
        parent_id: str,
        child_id: str,
        *,
        context: Sequence[str] = (),
        max_depth: int = 3,
        decay: float = 0.75,
        context_floor: float = 0.1,
    ) -> float:
        structure = self.structure_score(
            parent_id,
            child_id,
            context=context,
            max_depth=max_depth,
            decay=decay,
            context_floor=context_floor,
        )
        density = self.density_score(
            parent_id,
            child_id,
            context=context,
            max_depth=max_depth,
            decay=decay,
            context_floor=context_floor,
        )
        return float(np.clip(0.5 * structure + 0.5 * density, 0.0, 1.0))


def _snapshot_id(
    *,
    ledger_digest: str,
    dim: int,
    containers: Sequence[SemanticContainer],
    embeddings: Sequence[ContainerEmbedding],
) -> str:
    payload = {
        "version": CONTAINER_CORE_VERSION,
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
        "embeddings": [item.embedding_id for item in sorted(embeddings, key=lambda value: value.embedding_id)],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def materialize_container_ledger(
    ledger: EvidenceLedger,
    *,
    encoder: EvidenceEncoder | None = None,
) -> ContainerSnapshot:
    """Materialize active evidence into explicit asymmetric semantic containers."""
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
            operator = np.outer(vector, vector)
            contribution_id = _stable_digest(
                CONTAINER_CORE_VERSION,
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
                operator=operator,
            )
            contributions_by_container.setdefault(item.container_id, []).append(item)
            known_container_ids.add(item.container_id)

        if event.subject is None or event.object is None or event.relation is None:
            continue
        if event.subject == event.object:
            continue
        weight = float(event.modality * event.intensity * event.confidence)
        context_keys = normalize_context_keys((
            event.context,
            event.provenance,
            event.relation,
            event.source_id,
        ))
        operator = _orthogonal_operator(
            event.subject,
            event.object,
            event.relation,
            context_keys,
            dim,
        )
        embedding_id = _stable_digest(
            CONTAINER_CORE_VERSION,
            event.event_id,
            event.subject,
            event.object,
            event.relation,
            json.dumps(context_keys, ensure_ascii=False),
        )
        embeddings.append(
            ContainerEmbedding(
                embedding_id=embedding_id,
                parent_id=event.subject,
                child_id=event.object,
                role=event.relation,
                context_keys=context_keys,
                weight=weight,
                polarity=event.polarity,
                operator=operator,
                evidence_ids=(event.event_id,),
            )
        )
        known_container_ids.update((event.subject, event.object, event.relation))

    outgoing_groups: dict[str, dict[tuple[str, str], list[ContainerEmbedding]]] = {}
    for embedding in embeddings:
        outgoing_groups.setdefault(embedding.parent_id, {}).setdefault(
            (embedding.child_id, embedding.role), []
        ).append(embedding)

    containers: list[SemanticContainer] = []
    for container_id in sorted(known_container_ids):
        contributions = tuple(contributions_by_container.get(container_id, ()))
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
            facet_evidence = tuple(sorted({event_id for item in members for event_id in item.evidence_ids}))
            positive_weight = sum(item.positive_weight for item in members)
            facet_id = _stable_digest(
                CONTAINER_CORE_VERSION,
                container_id,
                child_id,
                role,
                *facet_evidence,
            )
            facets.append(
                ContainerFacet(
                    facet_id=facet_id,
                    child_id=child_id,
                    role=role,
                    weight=positive_weight,
                    evidence_ids=facet_evidence,
                )
            )
            evidence_ids.update(facet_evidence)
        local_state = SemanticState.from_operator(
            operator,
            uncertainty=_uncertainty(operator),
            evidence_count=len({item.event_id for item in contributions}),
        )
        containers.append(
            SemanticContainer(
                container_id=container_id,
                local_state=local_state,
                contributions=contributions,
                facets=tuple(facets),
                evidence_ids=tuple(sorted(evidence_ids)),
            )
        )

    snapshot_id = _snapshot_id(
        ledger_digest=ledger.digest,
        dim=dim,
        containers=containers,
        embeddings=embeddings,
    )
    return ContainerSnapshot(
        version=CONTAINER_CORE_VERSION,
        ledger_digest=ledger.digest,
        snapshot_id=snapshot_id,
        dim=dim,
        containers=tuple(containers),
        embeddings=tuple(embeddings),
    )
