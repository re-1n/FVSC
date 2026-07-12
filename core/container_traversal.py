"""Bounded aggregated traversal index for explicit container snapshots.

Raw snapshots retain one embedding per active evidence event. Recursive queries use
this derived index, which groups repeated evidence by ``parent, child, role`` while
preserving all evidence identifiers. The index prevents corpus frequency from turning
one semantic relation into an exponential number of traversal branches.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np

from .container_core import ContainerSnapshot, normalize_context_keys
from .semantic_metrics import operator_inclusion
from .semantic_state import SemanticState

_EPS = 1e-12


@dataclass(frozen=True, eq=False)
class TraversalEdge:
    edge_id: str
    parent_id: str
    child_id: str
    role: str
    strength: float
    operator: np.ndarray
    embedding_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, eq=False)
class IndexedActivation:
    root_id: str
    state: SemanticState
    evidence_ids: tuple[str, ...]
    contribution_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    path_count: int


@dataclass(frozen=True, eq=False)
class IndexedProjection:
    parent_id: str
    child_id: str
    state: SemanticState
    path_strength: float
    path_count: int
    evidence_ids: tuple[str, ...]


def _uncertainty(operator: np.ndarray) -> float:
    mass = float(np.trace(operator))
    if mass <= _EPS:
        return 1.0
    shape = operator / mass
    return float(np.clip(1.0 - np.trace(shape @ shape), 0.0, 1.0))


class BoundedContainerTraversal:
    """Aggregate repeated embeddings and bound recursive branching deterministically."""

    def __init__(self, snapshot: ContainerSnapshot, *, branch_limit: int = 12) -> None:
        if not isinstance(snapshot, ContainerSnapshot):
            raise TypeError("snapshot must be a ContainerSnapshot")
        if isinstance(branch_limit, bool) or not isinstance(branch_limit, int) or branch_limit < 1:
            raise ValueError("branch_limit must be a positive integer")
        self.snapshot = snapshot
        self.branch_limit = branch_limit
        self._edges = self._build_edges()
        self._outgoing: Mapping[str, tuple[TraversalEdge, ...]] = MappingProxyType(
            {
                parent: tuple(
                    sorted(edges, key=lambda item: (-item.strength, item.edge_id))[:branch_limit]
                )
                for parent, edges in self._group_by_parent(self._edges).items()
            }
        )

    @staticmethod
    def _group_by_parent(edges: Sequence[TraversalEdge]) -> dict[str, list[TraversalEdge]]:
        grouped: dict[str, list[TraversalEdge]] = {}
        for edge in edges:
            grouped.setdefault(edge.parent_id, []).append(edge)
        return grouped

    def _build_edges(self) -> tuple[TraversalEdge, ...]:
        grouped: dict[tuple[str, str, str], list] = {}
        for embedding in self.snapshot.embeddings:
            if embedding.positive_weight <= _EPS:
                continue
            grouped.setdefault(
                (embedding.parent_id, embedding.child_id, embedding.role), []
            ).append(embedding)

        edges: list[TraversalEdge] = []
        for (parent, child, role), members in sorted(grouped.items()):
            ordered = sorted(
                members,
                key=lambda item: (-item.positive_weight, item.embedding_id),
            )
            residual = 1.0
            for embedding in ordered:
                residual *= 1.0 - float(np.clip(embedding.positive_weight, 0.0, 1.0))
            strength = 1.0 - residual
            representative = ordered[0]
            embedding_ids = tuple(sorted(item.embedding_id for item in ordered))
            evidence_ids = tuple(sorted({
                evidence_id
                for item in ordered
                for evidence_id in item.evidence_ids
            }))
            edge_id = hashlib.sha256(
                "\0".join((parent, child, role, *embedding_ids)).encode("utf-8")
            ).hexdigest()
            operator = np.array(representative.operator, dtype=float, copy=True)
            operator.setflags(write=False)
            edges.append(
                TraversalEdge(
                    edge_id=edge_id,
                    parent_id=parent,
                    child_id=child,
                    role=role,
                    strength=float(np.clip(strength, 0.0, 1.0)),
                    operator=operator,
                    embedding_ids=embedding_ids,
                    evidence_ids=evidence_ids,
                )
            )
        return tuple(edges)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def outgoing(self, parent_id: str) -> tuple[TraversalEdge, ...]:
        return self._outgoing.get(str(parent_id).strip(), ())

    @staticmethod
    def _context_affinity(
        edge: TraversalEdge,
        query: Sequence[str],
        *,
        floor: float,
    ) -> float:
        if not math.isfinite(floor) or not 0.0 <= floor <= 1.0:
            raise ValueError("context floor must be in [0, 1]")
        normalized = frozenset(normalize_context_keys(query))
        if not normalized:
            return 1.0
        available = frozenset(normalize_context_keys((edge.parent_id, edge.child_id, edge.role)))
        overlap = len(normalized & available) / len(normalized)
        return float(floor + (1.0 - floor) * overlap)

    def _paths(
        self,
        parent_id: str,
        child_id: str,
        *,
        context: Sequence[str],
        max_depth: int,
        decay: float,
        context_floor: float,
    ) -> list[tuple[float, np.ndarray, tuple[str, ...], tuple[str, ...]]]:
        parent = str(parent_id).strip()
        child = str(child_id).strip()
        if not parent or not child or self.snapshot.get(parent) is None or self.snapshot.get(child) is None:
            return []
        if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 1:
            return []
        if not math.isfinite(decay) or not 0.0 <= decay <= 1.0:
            raise ValueError("decay must be in [0, 1]")
        if parent == child:
            return [(1.0, np.eye(self.snapshot.dim), (), ())]
        results: list[tuple[float, np.ndarray, tuple[str, ...], tuple[str, ...]]] = []

        def visit(
            current: str,
            transform: np.ndarray,
            strength: float,
            depth: int,
            seen: tuple[str, ...],
            edge_ids: tuple[str, ...],
            evidence_ids: tuple[str, ...],
        ) -> None:
            if depth >= max_depth:
                return
            for edge in self.outgoing(current):
                if edge.child_id in seen:
                    continue
                affinity = self._context_affinity(edge, context, floor=context_floor)
                next_strength = strength * decay * edge.strength * affinity
                if next_strength <= _EPS:
                    continue
                next_transform = transform @ edge.operator
                next_edge_ids = (*edge_ids, edge.edge_id)
                next_evidence = tuple(sorted({*evidence_ids, *edge.evidence_ids}))
                if edge.child_id == child:
                    results.append(
                        (next_strength, next_transform, next_edge_ids, next_evidence)
                    )
                visit(
                    edge.child_id,
                    next_transform,
                    next_strength,
                    depth + 1,
                    (*seen, edge.child_id),
                    next_edge_ids,
                    next_evidence,
                )

        visit(parent, np.eye(self.snapshot.dim), 1.0, 0, (parent,), (), ())
        return sorted(results, key=lambda item: (-item[0], item[2]))

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
        paths = self._paths(
            parent_id,
            child_id,
            context=context,
            max_depth=max_depth,
            decay=decay,
            context_floor=context_floor,
        )
        return float(np.clip(paths[0][0] if paths else 0.0, 0.0, 1.0))

    def activate(
        self,
        root_id: str,
        *,
        context: Sequence[str] = (),
        max_depth: int = 2,
        decay: float = 0.75,
        context_floor: float = 0.1,
    ) -> IndexedActivation:
        root = str(root_id).strip()
        if self.snapshot.get(root) is None:
            return IndexedActivation(
                root_id=root,
                state=SemanticState.empty(self.snapshot.dim),
                evidence_ids=(),
                contribution_ids=(),
                edge_ids=(),
                path_count=0,
            )
        selected: dict[str, tuple[float, np.ndarray, str]] = {}
        path_evidence: set[str] = set()
        edge_ids: set[str] = set()
        path_count = 0

        def visit(
            current: str,
            transform: np.ndarray,
            strength: float,
            depth: int,
            seen: tuple[str, ...],
        ) -> None:
            nonlocal path_count
            container = self.snapshot.get(current)
            assert container is not None
            for contribution in container.contributions:
                effective = strength * contribution.weight
                previous = selected.get(contribution.contribution_id)
                if previous is None or effective > previous[0] + _EPS:
                    selected[contribution.contribution_id] = (
                        effective,
                        transform @ contribution.operator @ transform.T,
                        contribution.event_id,
                    )
            if depth >= max_depth:
                return
            for edge in self.outgoing(current):
                if edge.child_id in seen:
                    continue
                affinity = self._context_affinity(edge, context, floor=context_floor)
                next_strength = strength * decay * edge.strength * affinity
                if next_strength <= _EPS:
                    continue
                path_count += 1
                edge_ids.add(edge.edge_id)
                path_evidence.update(edge.evidence_ids)
                visit(
                    edge.child_id,
                    transform @ edge.operator,
                    next_strength,
                    depth + 1,
                    (*seen, edge.child_id),
                )

        visit(root, np.eye(self.snapshot.dim), 1.0, 0, (root,))
        operator = np.zeros((self.snapshot.dim, self.snapshot.dim), dtype=float)
        evidence_ids = set(path_evidence)
        for effective, projected, event_id in selected.values():
            operator += effective * projected
            evidence_ids.add(event_id)
        state = SemanticState.from_operator(
            operator,
            uncertainty=_uncertainty(operator),
            evidence_count=len(evidence_ids),
        )
        return IndexedActivation(
            root_id=root,
            state=state,
            evidence_ids=tuple(sorted(evidence_ids)),
            contribution_ids=tuple(sorted(selected)),
            edge_ids=tuple(sorted(edge_ids)),
            path_count=path_count,
        )

    def project(
        self,
        parent_id: str,
        child_id: str,
        *,
        context: Sequence[str] = (),
        max_depth: int = 2,
        decay: float = 0.75,
        context_floor: float = 0.1,
    ) -> IndexedProjection:
        child = str(child_id).strip()
        container = self.snapshot.get(child)
        paths = self._paths(
            parent_id,
            child,
            context=context,
            max_depth=max_depth,
            decay=decay,
            context_floor=context_floor,
        )
        if container is None or not paths:
            return IndexedProjection(
                parent_id=str(parent_id).strip(),
                child_id=child,
                state=SemanticState.empty(self.snapshot.dim),
                path_strength=0.0,
                path_count=0,
                evidence_ids=(),
            )
        selected: dict[str, tuple[float, np.ndarray, str]] = {}
        evidence_ids: set[str] = set()
        for strength, transform, _edge_ids, path_evidence in paths:
            evidence_ids.update(path_evidence)
            for contribution in container.contributions:
                effective = strength * contribution.weight
                previous = selected.get(contribution.contribution_id)
                if previous is None or effective > previous[0] + _EPS:
                    selected[contribution.contribution_id] = (
                        effective,
                        transform @ contribution.operator @ transform.T,
                        contribution.event_id,
                    )
        operator = np.zeros((self.snapshot.dim, self.snapshot.dim), dtype=float)
        for effective, projected, event_id in selected.values():
            operator += effective * projected
            evidence_ids.add(event_id)
        state = SemanticState.from_operator(
            operator,
            uncertainty=_uncertainty(operator),
            evidence_count=len(evidence_ids),
        )
        return IndexedProjection(
            parent_id=str(parent_id).strip(),
            child_id=child,
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
        max_depth: int = 2,
    ) -> float:
        projection = self.project(parent_id, child_id, context=context, max_depth=max_depth)
        if projection.state.is_empty:
            return 0.0
        activation = self.activate(parent_id, context=context, max_depth=max_depth)
        if activation.state.is_empty:
            return 0.0
        return float(np.clip(
            projection.path_strength * operator_inclusion(projection.state, activation.state),
            0.0,
            1.0,
        ))
