"""Immutable, cited contracts for replaceable semantic graph views.

The graph is derived state. It may describe parser hypotheses but has no method that
writes to ``EvidenceLedger`` or promotes a hypothesis to owner evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Literal, Mapping

from ..linguistic import LinguisticFrontendResult


SEMANTIC_GRAPH_SCHEMA = "fvsc.semantic-graph/v1"
AlignmentStatus = Literal["aligned", "implicit", "unknown"]
GraphScope = Literal["sentence", "document"]
NodeKind = Literal["concept", "metanode"]
ScalarValue = str | int | float | bool

_ALIGNMENT_STATUSES = frozenset({"aligned", "implicit", "unknown"})
_GRAPH_SCOPES = frozenset({"sentence", "document"})
_NODE_KINDS = frozenset({"concept", "metanode"})
_SHA256_LENGTH = 64


def _nonempty(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must not be empty")
    return result


def _optional_nonempty(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    return _nonempty(value, field=field)


def _digest(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if len(result) != _SHA256_LENGTH or any(
        char not in "0123456789abcdef" for char in result
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return result


def _confidence(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError("graph confidence must be finite and in [0, 1]")
    return result


def _scalar(value: Any) -> ScalarValue:
    if isinstance(value, (str, bool, int)):
        if isinstance(value, str) and not value.strip():
            raise ValueError("semantic attribute string must not be empty")
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError("semantic attribute value must be a finite JSON scalar")


@dataclass(frozen=True)
class SemanticNode:
    node_id: str
    concept: str
    sentence_id: str | None
    aligned_token_ids: tuple[str, ...] = ()
    alignment_status: AlignmentStatus = "aligned"
    kind: NodeKind = "concept"
    confidence: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", _nonempty(self.node_id, field="node_id"))
        object.__setattr__(self, "concept", _nonempty(self.concept, field="concept"))
        object.__setattr__(
            self,
            "sentence_id",
            _optional_nonempty(self.sentence_id, field="sentence_id"),
        )
        token_ids = tuple(_nonempty(value, field="aligned token id") for value in self.aligned_token_ids)
        if len(token_ids) != len(set(token_ids)):
            raise ValueError("semantic node aligned token ids must be unique")
        if self.alignment_status not in _ALIGNMENT_STATUSES:
            raise ValueError(f"unknown alignment status: {self.alignment_status!r}")
        if self.kind not in _NODE_KINDS:
            raise ValueError(f"unknown semantic node kind: {self.kind!r}")
        if self.alignment_status == "aligned" and not token_ids:
            raise ValueError("aligned semantic nodes require at least one token")
        if self.alignment_status != "aligned" and token_ids:
            raise ValueError("implicit or unknown semantic nodes cannot claim token alignment")
        if self.kind == "metanode" and self.sentence_id is not None:
            raise ValueError("semantic metanodes must be document-level")
        object.__setattr__(self, "aligned_token_ids", token_ids)
        object.__setattr__(self, "confidence", _confidence(self.confidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "aligned_token_ids": list(self.aligned_token_ids),
            "alignment_status": self.alignment_status,
            "concept": self.concept,
            "confidence": self.confidence,
            "kind": self.kind,
            "node_id": self.node_id,
            "sentence_id": self.sentence_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SemanticNode":
        raw_tokens = value.get("aligned_token_ids", [])
        if not isinstance(raw_tokens, list):
            raise ValueError("aligned_token_ids must be an array")
        return cls(
            node_id=value.get("node_id", ""),
            concept=value.get("concept", ""),
            sentence_id=value.get("sentence_id"),
            aligned_token_ids=tuple(raw_tokens),
            alignment_status=value.get("alignment_status", "unknown"),
            kind=value.get("kind", "concept"),
            confidence=value.get("confidence", 0.0),
        )


@dataclass(frozen=True)
class SemanticEdge:
    source_id: str
    relation: str
    target_id: str
    scope: GraphScope = "sentence"
    confidence: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _nonempty(self.source_id, field="edge source_id"))
        object.__setattr__(self, "relation", _nonempty(self.relation, field="edge relation"))
        object.__setattr__(self, "target_id", _nonempty(self.target_id, field="edge target_id"))
        if self.scope not in _GRAPH_SCOPES:
            raise ValueError(f"unknown semantic graph scope: {self.scope!r}")
        object.__setattr__(self, "confidence", _confidence(self.confidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence,
            "relation": self.relation,
            "scope": self.scope,
            "source_id": self.source_id,
            "target_id": self.target_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SemanticEdge":
        return cls(
            source_id=value.get("source_id", ""),
            relation=value.get("relation", ""),
            target_id=value.get("target_id", ""),
            scope=value.get("scope", "sentence"),
            confidence=value.get("confidence", 0.0),
        )


@dataclass(frozen=True)
class SemanticAttribute:
    node_id: str
    name: str
    value: ScalarValue
    confidence: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", _nonempty(self.node_id, field="attribute node_id"))
        object.__setattr__(self, "name", _nonempty(self.name, field="attribute name"))
        object.__setattr__(self, "value", _scalar(self.value))
        object.__setattr__(self, "confidence", _confidence(self.confidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": self.confidence,
            "name": self.name,
            "node_id": self.node_id,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SemanticAttribute":
        return cls(
            node_id=value.get("node_id", ""),
            name=value.get("name", ""),
            value=value.get("value", ""),
            confidence=value.get("confidence", 0.0),
        )


@dataclass(frozen=True)
class RepresentationLoss:
    """One source field that an adapter could not preserve structurally."""

    path: str
    reason: str
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _nonempty(self.path, field="loss path"))
        object.__setattr__(self, "reason", _nonempty(self.reason, field="loss reason"))
        object.__setattr__(self, "detail", str(self.detail).strip())

    def to_dict(self) -> dict[str, str]:
        return {"detail": self.detail, "path": self.path, "reason": self.reason}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RepresentationLoss":
        return cls(
            path=value.get("path", ""),
            reason=value.get("reason", ""),
            detail=value.get("detail", ""),
        )


@dataclass(frozen=True)
class SemanticGraphView:
    """Versioned semantic graph projection bound to one frontend and source revision."""

    source_id: str
    source_revision: str
    language_tag: str
    frontend_digest: str
    extractor: str
    extractor_version: str
    nodes: tuple[SemanticNode, ...]
    edges: tuple[SemanticEdge, ...] = ()
    attributes: tuple[SemanticAttribute, ...] = ()
    losses: tuple[RepresentationLoss, ...] = ()
    schema: str = SEMANTIC_GRAPH_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SEMANTIC_GRAPH_SCHEMA:
            raise ValueError("unsupported semantic graph schema")
        object.__setattr__(self, "source_id", _nonempty(self.source_id, field="source_id"))
        object.__setattr__(
            self,
            "source_revision",
            _digest(self.source_revision, field="source_revision"),
        )
        object.__setattr__(
            self,
            "frontend_digest",
            _digest(self.frontend_digest, field="frontend_digest"),
        )
        object.__setattr__(
            self,
            "language_tag",
            _nonempty(self.language_tag, field="language_tag"),
        )
        object.__setattr__(self, "extractor", _nonempty(self.extractor, field="extractor"))
        object.__setattr__(
            self,
            "extractor_version",
            _nonempty(self.extractor_version, field="extractor_version"),
        )
        node_ids = tuple(item.node_id for item in self.nodes)
        if node_ids != tuple(sorted(node_ids)):
            raise ValueError("semantic nodes must be sorted by node_id")
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("semantic node ids must be unique")
        node_by_id = {item.node_id: item for item in self.nodes}
        edge_keys = tuple(
            (item.scope, item.source_id, item.relation, item.target_id)
            for item in self.edges
        )
        if edge_keys != tuple(sorted(edge_keys)):
            raise ValueError("semantic edges must be deterministically sorted")
        if len(edge_keys) != len(set(edge_keys)):
            raise ValueError("semantic graph edges must be unique")
        for edge in self.edges:
            source = node_by_id.get(edge.source_id)
            target = node_by_id.get(edge.target_id)
            if source is None or target is None:
                raise ValueError("semantic graph edge references an unknown node")
            if edge.scope == "sentence" and (
                source.sentence_id is None
                or target.sentence_id is None
                or source.sentence_id != target.sentence_id
            ):
                raise ValueError("sentence semantic edges must stay inside one sentence")
        attribute_keys = tuple((item.node_id, item.name) for item in self.attributes)
        if attribute_keys != tuple(sorted(attribute_keys)):
            raise ValueError("semantic attributes must be deterministically sorted")
        if len(attribute_keys) != len(set(attribute_keys)):
            raise ValueError("semantic attributes must be unique per node and name")
        if any(item.node_id not in node_by_id for item in self.attributes):
            raise ValueError("semantic attribute references an unknown node")
        loss_keys = tuple((item.path, item.reason, item.detail) for item in self.losses)
        if loss_keys != tuple(sorted(loss_keys)):
            raise ValueError("representation losses must be deterministically sorted")

    def verify(self, frontend: LinguisticFrontendResult) -> None:
        if frontend.source_id != self.source_id:
            raise ValueError("semantic graph source_id does not match frontend")
        if frontend.source_revision != self.source_revision:
            raise ValueError("semantic graph source_revision does not match frontend")
        if frontend.language_tag != self.language_tag:
            raise ValueError("semantic graph language_tag does not match frontend")
        if frontend.digest != self.frontend_digest:
            raise ValueError("semantic graph frontend digest does not match frontend")
        token_by_id = {item.token_id: item for item in frontend.tokens}
        for node in self.nodes:
            for token_id in node.aligned_token_ids:
                token = token_by_id.get(token_id)
                if token is None:
                    raise ValueError("semantic node alignment references an unknown token")
                if token.sentence_id != node.sentence_id:
                    raise ValueError("semantic node alignment crosses sentence boundaries")

    @property
    def digest(self) -> str:
        payload = json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "attributes": [item.to_dict() for item in self.attributes],
            "edges": [item.to_dict() for item in self.edges],
            "extractor": self.extractor,
            "extractor_version": self.extractor_version,
            "frontend_digest": self.frontend_digest,
            "language_tag": self.language_tag,
            "losses": [item.to_dict() for item in self.losses],
            "nodes": [item.to_dict() for item in self.nodes],
            "schema": self.schema,
            "source_id": self.source_id,
            "source_revision": self.source_revision,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SemanticGraphView":
        raw_nodes = value.get("nodes", [])
        raw_edges = value.get("edges", [])
        raw_attributes = value.get("attributes", [])
        raw_losses = value.get("losses", [])
        if not all(
            isinstance(item, list)
            for item in (raw_nodes, raw_edges, raw_attributes, raw_losses)
        ):
            raise ValueError("semantic graph collections must be arrays")
        return cls(
            source_id=value.get("source_id", ""),
            source_revision=value.get("source_revision", ""),
            language_tag=value.get("language_tag", ""),
            frontend_digest=value.get("frontend_digest", ""),
            extractor=value.get("extractor", ""),
            extractor_version=value.get("extractor_version", ""),
            nodes=tuple(SemanticNode.from_dict(item) for item in raw_nodes),
            edges=tuple(SemanticEdge.from_dict(item) for item in raw_edges),
            attributes=tuple(SemanticAttribute.from_dict(item) for item in raw_attributes),
            losses=tuple(RepresentationLoss.from_dict(item) for item in raw_losses),
            schema=value.get("schema", ""),
        )


__all__ = [
    "AlignmentStatus",
    "GraphScope",
    "NodeKind",
    "RepresentationLoss",
    "SEMANTIC_GRAPH_SCHEMA",
    "SemanticAttribute",
    "SemanticEdge",
    "SemanticGraphView",
    "SemanticNode",
]
