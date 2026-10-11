"""Cached, context-preserving queries over explicit semantic containers.

The raw :mod:`core.container_core` snapshot intentionally keeps one directed embedding
per active evidence event.  This module builds a bounded query index that:

* aggregates only embeddings with the same parent, child, role *and context keys*;
* preserves all source embedding and evidence identifiers;
* caches bounded path expansion per root and query context;
* exposes the exact container/edge/evidence path behind every containment score;
* projects each reached container at most once through its strongest path.

The evidence ledger remains canonical.  This index is a disposable derived view.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np

from .core import ContainerSnapshot, normalize_context_keys
from ..metrics import operator_inclusion
from ..state import SemanticState


_EPS = 1e-12


def _uncertainty(operator: np.ndarray) -> float:
    mass = float(np.trace(operator))
    if mass <= _EPS:
        return 1.0
    shape = operator / mass
    return float(np.clip(1.0 - np.trace(shape @ shape), 0.0, 1.0))


def _bounded_probability(value: float, *, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be finite and in [0, 1]")
    return number


@dataclass(frozen=True, eq=False)
class QueryEdge:
    edge_id: str
    parent_id: str
    child_id: str
    role: str
    context_keys: tuple[str, ...]
    strength: float
    operator: np.ndarray
    embedding_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("edge_id", "parent_id", "child_id", "role"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be empty")
        if self.parent_id == self.child_id:
            raise ValueError("query edge cannot be a self-loop")
        context_keys = normalize_context_keys(self.context_keys)
        strength = _bounded_probability(self.strength, name="edge strength")
        matrix = np.asarray(self.operator, dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or matrix.shape[0] == 0:
            raise ValueError("query edge operator must be a non-empty square matrix")
        if not np.all(np.isfinite(matrix)):
            raise ValueError("query edge operator must be finite")
        operator = np.array(matrix, dtype=float, copy=True)
        operator.setflags(write=False)
        embedding_ids = tuple(sorted({str(item).strip() for item in self.embedding_ids if str(item).strip()}))
        evidence_ids = tuple(sorted({str(item).strip() for item in self.evidence_ids if str(item).strip()}))
        if not embedding_ids or not evidence_ids:
            raise ValueError("query edge requires embedding and evidence identifiers")
        object.__setattr__(self, "context_keys", context_keys)
        object.__setattr__(self, "strength", strength)
        object.__setattr__(self, "operator", operator)
        object.__setattr__(self, "embedding_ids", embedding_ids)
        object.__setattr__(self, "evidence_ids", evidence_ids)


@dataclass(frozen=True, eq=False)
class ContainerPath:
    root_id: str
    target_id: str
    container_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    strength: float
    operator: np.ndarray

    def __post_init__(self) -> None:
        if not self.container_ids or self.container_ids[0] != self.root_id:
            raise ValueError("path must start at root_id")
        if self.container_ids[-1] != self.target_id:
            raise ValueError("path must end at target_id")
        if len(self.edge_ids) != len(self.container_ids) - 1:
            raise ValueError("path edge count must match container transitions")
        strength = _bounded_probability(self.strength, name="path strength")
        operator = np.asarray(self.operator, dtype=float)
        if operator.ndim != 2 or operator.shape[0] != operator.shape[1]:
            raise ValueError("path operator must be square")
        result = np.array(operator, dtype=float, copy=True)
        result.setflags(write=False)
        object.__setattr__(self, "strength", strength)
        object.__setattr__(self, "operator", result)
        object.__setattr__(self, "evidence_ids", tuple(sorted(set(self.evidence_ids))))


@dataclass(frozen=True, eq=False)
class QueryActivation:
    root_id: str
    context_keys: tuple[str, ...]
    state: SemanticState
    container_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    contribution_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    path_count: int


@dataclass(frozen=True, eq=False)
class QueryProjection:
    parent_id: str
    child_id: str
    context_keys: tuple[str, ...]
    state: SemanticState
    path_strength: float
    path_count: int
    path: ContainerPath | None
    evidence_ids: tuple[str, ...]


class ContainerQueryIndex:
    """Efficient deterministic queries over one :class:`ContainerSnapshot`."""

    def __init__(
        self,
        snapshot: ContainerSnapshot,
        *,
        branch_limit: int = 12,
        max_paths_per_target: int = 4,
    ) -> None:
        if not isinstance(snapshot, ContainerSnapshot):
            raise TypeError("snapshot must be a ContainerSnapshot")
        if isinstance(branch_limit, bool) or not isinstance(branch_limit, int) or branch_limit < 1:
            raise ValueError("branch_limit must be a positive integer")
        if (
            isinstance(max_paths_per_target, bool)
            or not isinstance(max_paths_per_target, int)
            or max_paths_per_target < 1
        ):
            raise ValueError("max_paths_per_target must be a positive integer")
        self.snapshot = snapshot
        self.branch_limit = branch_limit
        self.max_paths_per_target = max_paths_per_target
        self._edges = self._build_edges()
        grouped: dict[str, list[QueryEdge]] = {}
        for edge in self._edges:
            grouped.setdefault(edge.parent_id, []).append(edge)
        self._outgoing: Mapping[str, tuple[QueryEdge, ...]] = MappingProxyType({
            parent: tuple(sorted(edges, key=lambda item: (-item.strength, item.edge_id))[:branch_limit])
            for parent, edges in grouped.items()
        })
        self._path_cache: dict[
            tuple[str, tuple[str, ...], int, float, float],
            Mapping[str, tuple[ContainerPath, ...]],
        ] = {}
        self._activation_cache: dict[
            tuple[str, tuple[str, ...], int, float, float],
            QueryActivation,
        ] = {}
        self._projection_cache: dict[
            tuple[str, str, tuple[str, ...], int, float, float],
            QueryProjection,
        ] = {}

    def _build_edges(self) -> tuple[QueryEdge, ...]:
        grouped: dict[tuple[str, str, str, tuple[str, ...]], list] = {}
        for embedding in self.snapshot.embeddings:
            if embedding.positive_weight <= _EPS:
                continue
            key = (
                embedding.parent_id,
                embedding.child_id,
                embedding.role,
                tuple(embedding.context_keys),
            )
            grouped.setdefault(key, []).append(embedding)

        edges: list[QueryEdge] = []
        for (parent, child, role, context_keys), members in sorted(grouped.items()):
            ordered = sorted(members, key=lambda item: (-item.positive_weight, item.embedding_id))
            residual = 1.0
            for embedding in ordered:
                residual *= 1.0 - float(np.clip(embedding.positive_weight, 0.0, 1.0))
            representative = ordered[0]
            embedding_ids = tuple(sorted(item.embedding_id for item in ordered))
            evidence_ids = tuple(sorted({
                evidence_id
                for item in ordered
                for evidence_id in item.evidence_ids
            }))
            edge_id = hashlib.sha256(
                "\0".join((parent, child, role, *context_keys, *embedding_ids)).encode("utf-8")
            ).hexdigest()
            edges.append(QueryEdge(
                edge_id=edge_id,
                parent_id=parent,
                child_id=child,
                role=role,
                context_keys=context_keys,
                strength=float(np.clip(1.0 - residual, 0.0, 1.0)),
                operator=representative.operator,
                embedding_ids=embedding_ids,
                evidence_ids=evidence_ids,
            ))
        return tuple(edges)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def outgoing(self, parent_id: str) -> tuple[QueryEdge, ...]:
        return self._outgoing.get(str(parent_id).strip(), ())

    @staticmethod
    def _context_affinity(edge: QueryEdge, query: tuple[str, ...], *, floor: float) -> float:
        if not query:
            return 1.0
        available = frozenset(normalize_context_keys((
            edge.context_keys,
            edge.parent_id,
            edge.child_id,
            edge.role,
        )))
        overlap = len(frozenset(query) & available) / len(query)
        return float(floor + (1.0 - floor) * overlap)

    def paths_from(
        self,
        root_id: str,
        *,
        context: Sequence[str] = (),
        max_depth: int = 2,
        decay: float = 0.75,
        context_floor: float = 0.1,
    ) -> Mapping[str, tuple[ContainerPath, ...]]:
        root = str(root_id).strip()
        if self.snapshot.get(root) is None:
            return MappingProxyType({})
        if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 0:
            raise ValueError("max_depth must be a non-negative integer")
        decay = _bounded_probability(decay, name="decay")
        context_floor = _bounded_probability(context_floor, name="context_floor")
        query = normalize_context_keys(context)
        key = (root, query, max_depth, decay, context_floor)
        cached = self._path_cache.get(key)
        if cached is not None:
            return cached

        paths: dict[str, list[ContainerPath]] = {
            root: [ContainerPath(
                root_id=root,
                target_id=root,
                container_ids=(root,),
                edge_ids=(),
                evidence_ids=(),
                strength=1.0,
                operator=np.eye(self.snapshot.dim),
            )]
        }

        def visit(
            current: str,
            transform: np.ndarray,
            strength: float,
            depth: int,
            container_ids: tuple[str, ...],
            edge_ids: tuple[str, ...],
            evidence_ids: tuple[str, ...],
        ) -> None:
            if depth >= max_depth:
                return
            for edge in self.outgoing(current):
                if edge.child_id in container_ids:
                    continue
                affinity = self._context_affinity(edge, query, floor=context_floor)
                next_strength = strength * decay * edge.strength * affinity
                if next_strength <= _EPS:
                    continue
                next_transform = transform @ edge.operator
                next_containers = (*container_ids, edge.child_id)
                next_edges = (*edge_ids, edge.edge_id)
                next_evidence = tuple(sorted({*evidence_ids, *edge.evidence_ids}))
                paths.setdefault(edge.child_id, []).append(ContainerPath(
                    root_id=root,
                    target_id=edge.child_id,
                    container_ids=next_containers,
                    edge_ids=next_edges,
                    evidence_ids=next_evidence,
                    strength=float(np.clip(next_strength, 0.0, 1.0)),
                    operator=next_transform,
                ))
                visit(
                    edge.child_id,
                    next_transform,
                    next_strength,
                    depth + 1,
                    next_containers,
                    next_edges,
                    next_evidence,
                )

        visit(root, np.eye(self.snapshot.dim), 1.0, 0, (root,), (), ())
        frozen = MappingProxyType({
            target: tuple(sorted(
                members,
                key=lambda item: (-item.strength, item.edge_ids, item.container_ids),
            )[: self.max_paths_per_target])
            for target, members in paths.items()
        })
        self._path_cache[key] = frozen
        return frozen

    def explain(
        self,
        parent_id: str,
        child_id: str,
        *,
        context: Sequence[str] = (),
        max_depth: int = 2,
        decay: float = 0.75,
        context_floor: float = 0.1,
    ) -> tuple[ContainerPath, ...]:
        return self.paths_from(
            parent_id,
            context=context,
            max_depth=max_depth,
            decay=decay,
            context_floor=context_floor,
        ).get(str(child_id).strip(), ())

    def structure_score(
        self,
        parent_id: str,
        child_id: str,
        *,
        context: Sequence[str] = (),
        max_depth: int = 2,
        decay: float = 0.75,
        context_floor: float = 0.1,
    ) -> float:
        paths = self.explain(
            parent_id,
            child_id,
            context=context,
            max_depth=max_depth,
            decay=decay,
            context_floor=context_floor,
        )
        return paths[0].strength if paths else 0.0

    def project(
        self,
        parent_id: str,
        child_id: str,
        *,
        context: Sequence[str] = (),
        max_depth: int = 2,
        decay: float = 0.75,
        context_floor: float = 0.1,
    ) -> QueryProjection:
        parent = str(parent_id).strip()
        child = str(child_id).strip()
        query = normalize_context_keys(context)
        decay = _bounded_probability(decay, name="decay")
        context_floor = _bounded_probability(context_floor, name="context_floor")
        cache_key = (parent, child, query, max_depth, decay, context_floor)
        cached = self._projection_cache.get(cache_key)
        if cached is not None:
            return cached
        container = self.snapshot.get(child)
        paths = self.explain(
            parent,
            child,
            context=query,
            max_depth=max_depth,
            decay=decay,
            context_floor=context_floor,
        )
        if container is None or not paths:
            result = QueryProjection(
                parent_id=parent,
                child_id=child,
                context_keys=query,
                state=SemanticState.empty(self.snapshot.dim),
                path_strength=0.0,
                path_count=0,
                path=None,
                evidence_ids=(),
            )
        else:
            best = paths[0]
            operator = best.strength * (
                best.operator @ container.local_state.to_operator() @ best.operator.T
            )
            evidence_ids = tuple(sorted({*best.evidence_ids, *container.evidence_ids}))
            result = QueryProjection(
                parent_id=parent,
                child_id=child,
                context_keys=query,
                state=SemanticState.from_operator(
                    operator,
                    uncertainty=_uncertainty(operator),
                    evidence_count=len(evidence_ids),
                ),
                path_strength=best.strength,
                path_count=len(paths),
                path=best,
                evidence_ids=evidence_ids,
            )
        self._projection_cache[cache_key] = result
        return result

    def activate(
        self,
        root_id: str,
        *,
        context: Sequence[str] = (),
        max_depth: int = 2,
        decay: float = 0.75,
        context_floor: float = 0.1,
    ) -> QueryActivation:
        root = str(root_id).strip()
        query = normalize_context_keys(context)
        decay = _bounded_probability(decay, name="decay")
        context_floor = _bounded_probability(context_floor, name="context_floor")
        cache_key = (root, query, max_depth, decay, context_floor)
        cached = self._activation_cache.get(cache_key)
        if cached is not None:
            return cached
        path_map = self.paths_from(
            root,
            context=query,
            max_depth=max_depth,
            decay=decay,
            context_floor=context_floor,
        )
        operator = np.zeros((self.snapshot.dim, self.snapshot.dim), dtype=float)
        evidence_ids: set[str] = set()
        edge_ids: set[str] = set()
        contribution_ids: set[str] = set()
        container_ids: list[str] = []
        path_count = sum(len(paths) for target, paths in path_map.items() if target != root)

        for target in sorted(path_map):
            container = self.snapshot.get(target)
            if container is None or not path_map[target]:
                continue
            best = path_map[target][0]
            container_ids.append(target)
            operator += best.strength * (
                best.operator @ container.local_state.to_operator() @ best.operator.T
            )
            evidence_ids.update(best.evidence_ids)
            evidence_ids.update(container.evidence_ids)
            edge_ids.update(best.edge_ids)
            contribution_ids.update(item.contribution_id for item in container.contributions)

        state = SemanticState.from_operator(
            operator,
            uncertainty=_uncertainty(operator),
            evidence_count=len(evidence_ids),
        )
        result = QueryActivation(
            root_id=root,
            context_keys=query,
            state=state,
            container_ids=tuple(container_ids),
            edge_ids=tuple(sorted(edge_ids)),
            contribution_ids=tuple(sorted(contribution_ids)),
            evidence_ids=tuple(sorted(evidence_ids)),
            path_count=path_count,
        )
        self._activation_cache[cache_key] = result
        return result

    def density_score(
        self,
        parent_id: str,
        child_id: str,
        *,
        context: Sequence[str] = (),
        max_depth: int = 2,
        decay: float = 0.75,
        context_floor: float = 0.1,
    ) -> float:
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
        return float(np.clip(
            projection.path_strength * operator_inclusion(projection.state, activation.state),
            0.0,
            1.0,
        ))

    def hybrid_score(
        self,
        parent_id: str,
        child_id: str,
        *,
        context: Sequence[str] = (),
        max_depth: int = 2,
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
