"""Revision-bound owner annotations over immutable source documents.

The persisted overlay contains locators, offsets and digests, never source text.  It
can refine an automatically detected expression boundary without changing the source
document body or its revision.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from .source_provenance import (
    ExpressionKind,
    ExpressionSpan,
    OwnerEndorsement,
    OwnerRelation,
    SourceAttribution,
    TextOriginStatus,
)
from .vault_ingest import SourceDocument


OWNER_ANNOTATION_DERIVATION = "owner-annotation:v1"
MAX_OWNER_ANNOTATION_BYTES = 8 * 1024 * 1024
_DIGEST_LENGTH = 64
_OVERLAY_FIELDS = frozenset({"annotations", "overlay_id", "schema_version"})
_ANNOTATION_FIELDS = frozenset({"source_id", "source_revision", "span"})
_SPAN_FIELDS = frozenset(
    {
        "derivation",
        "end",
        "kind",
        "origin_status",
        "owner_endorsement",
        "owner_relation",
        "start",
        "text_sha256",
    }
)


def _digest(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if len(result) != _DIGEST_LENGTH or any(
        char not in "0123456789abcdef" for char in result
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return result


def _source_id(value: Any) -> str:
    result = str(value).strip()
    if not result or "\\" in result:
        raise ValueError("annotation source_id must be a safe POSIX-relative path")
    path = PurePosixPath(result)
    if path.is_absolute() or ".." in path.parts or result.endswith("/"):
        raise ValueError("annotation source_id must be a safe POSIX-relative path")
    normalized = path.as_posix()
    if normalized in {"", "."}:
        raise ValueError("annotation source_id must identify a source")
    return normalized


def _reject_unknown_fields(
    value: Mapping[str, Any],
    allowed: frozenset[str],
    *,
    field: str,
) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{field} contains unknown fields: {sorted(unknown)}")


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("owner annotation overlay must contain JSON values") from exc


def _content_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OwnerExpressionAnnotation:
    """One explicit owner judgment about a verified expression span."""

    source_id: str
    source_revision: str
    span: ExpressionSpan

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _source_id(self.source_id))
        object.__setattr__(
            self,
            "source_revision",
            _digest(self.source_revision, field="annotation source_revision"),
        )
        if not isinstance(self.span, ExpressionSpan):
            raise TypeError("annotation span must be an ExpressionSpan")
        if self.span.derivation != OWNER_ANNOTATION_DERIVATION:
            raise ValueError(
                f"owner annotation derivation must be {OWNER_ANNOTATION_DERIVATION!r}"
            )
        if (
            self.span.kind == "unclassified"
            and self.span.origin_status == "unresolved"
            and self.span.owner_relation == "unknown"
            and self.span.owner_endorsement == "unresolved"
        ):
            raise ValueError("owner annotation must add at least one known relation")

    @classmethod
    def create(
        cls,
        document: SourceDocument,
        *,
        start: int,
        end: int,
        kind: ExpressionKind,
        origin_status: TextOriginStatus = "unresolved",
        owner_relation: OwnerRelation = "unknown",
        owner_endorsement: OwnerEndorsement = "unresolved",
    ) -> "OwnerExpressionAnnotation":
        return cls(
            source_id=document.source_id,
            source_revision=document.source_revision,
            span=ExpressionSpan.from_text(
                document.text,
                start=start,
                end=end,
                kind=kind,
                origin_status=origin_status,
                owner_relation=owner_relation,
                owner_endorsement=owner_endorsement,
                derivation=OWNER_ANNOTATION_DERIVATION,
            ),
        )

    def verify(self, document: SourceDocument) -> None:
        if document.source_id != self.source_id:
            raise ValueError("owner annotation source_id does not match the document")
        if document.source_revision != self.source_revision:
            raise ValueError("owner annotation source revision changed")
        self.span.verify(document.text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_revision": self.source_revision,
            "span": self.span.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OwnerExpressionAnnotation":
        if not isinstance(value, Mapping):
            raise ValueError("owner annotation must be an object")
        _reject_unknown_fields(value, _ANNOTATION_FIELDS, field="owner annotation")
        raw_span = value.get("span")
        if not isinstance(raw_span, Mapping):
            raise ValueError("owner annotation span must be an object")
        _reject_unknown_fields(raw_span, _SPAN_FIELDS, field="owner annotation span")
        return cls(
            source_id=value.get("source_id", ""),
            source_revision=value.get("source_revision", ""),
            span=ExpressionSpan.from_dict(raw_span),
        )


@dataclass(frozen=True)
class OwnerAnnotationOverlay:
    """Deterministically ordered, content-addressed owner annotations."""

    annotations: tuple[OwnerExpressionAnnotation, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported owner annotation overlay schema version")
        ordered = tuple(
            sorted(
                self.annotations,
                key=lambda item: (item.source_id, item.span.start, item.span.end),
            )
        )
        if ordered != self.annotations:
            raise ValueError("owner annotations must be deterministically sorted")
        previous: OwnerExpressionAnnotation | None = None
        for annotation in ordered:
            if not isinstance(annotation, OwnerExpressionAnnotation):
                raise TypeError("overlay annotations must be OwnerExpressionAnnotation")
            if previous is not None and previous.source_id == annotation.source_id:
                if annotation.span.start < previous.span.end:
                    raise ValueError("owner annotations for one source must not overlap")
            previous = annotation

    def _payload(self) -> dict[str, Any]:
        return {
            "annotations": [item.to_dict() for item in self.annotations],
            "schema_version": self.schema_version,
        }

    @property
    def overlay_id(self) -> str:
        return _content_digest(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {"overlay_id": self.overlay_id, **self._payload()}

    @classmethod
    def create(
        cls,
        annotations: Iterable[OwnerExpressionAnnotation] = (),
    ) -> "OwnerAnnotationOverlay":
        return cls(
            annotations=tuple(
                sorted(
                    annotations,
                    key=lambda item: (item.source_id, item.span.start, item.span.end),
                )
            )
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OwnerAnnotationOverlay":
        if not isinstance(value, Mapping):
            raise ValueError("owner annotation overlay must be an object")
        _reject_unknown_fields(value, _OVERLAY_FIELDS, field="owner annotation overlay")
        raw_annotations = value.get("annotations", [])
        if not isinstance(raw_annotations, list):
            raise ValueError("owner annotation overlay annotations must be an array")
        result = cls(
            annotations=tuple(
                OwnerExpressionAnnotation.from_dict(item) for item in raw_annotations
            ),
            schema_version=value.get("schema_version", 0),
        )
        supplied_id = value.get("overlay_id")
        if supplied_id is not None and supplied_id != result.overlay_id:
            raise ValueError("overlay_id does not match the canonical annotation payload")
        return result


def load_owner_annotation_overlay(path: Path) -> OwnerAnnotationOverlay:
    """Load one small private overlay without following a symlink."""
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"refusing non-regular owner annotation overlay: {source}")
    if source.stat().st_size > MAX_OWNER_ANNOTATION_BYTES:
        raise ValueError("owner annotation overlay exceeds the size limit")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("owner annotation overlay must be valid UTF-8 JSON") from exc
    if not isinstance(value, Mapping):
        raise ValueError("owner annotation overlay must contain an object")
    return OwnerAnnotationOverlay.from_dict(value)


def apply_owner_annotation_overlay(
    documents: Iterable[SourceDocument],
    overlay: OwnerAnnotationOverlay,
) -> tuple[SourceDocument, ...]:
    """Return metadata-refined documents while preserving every source body/revision."""
    values = tuple(documents)
    by_id = {document.source_id: document for document in values}
    if len(by_id) != len(values):
        raise ValueError("source documents must have unique source ids")

    grouped: dict[str, list[OwnerExpressionAnnotation]] = {}
    for annotation in overlay.annotations:
        document = by_id.get(annotation.source_id)
        if document is None:
            raise ValueError("owner annotation references an absent source")
        annotation.verify(document)
        grouped.setdefault(annotation.source_id, []).append(annotation)

    result: list[SourceDocument] = []
    for document in values:
        annotations = grouped.get(document.source_id)
        if not annotations:
            result.append(document)
            continue

        metadata = document.metadata
        base = SourceAttribution.from_metadata(metadata)
        base.verify(document.text)
        spans = list(base.expression_spans)
        for annotation in annotations:
            replacement_index: int | None = None
            for index, existing in enumerate(spans):
                same_boundary = (
                    existing.start == annotation.span.start
                    and existing.end == annotation.span.end
                )
                overlaps = (
                    annotation.span.start < existing.end
                    and existing.start < annotation.span.end
                )
                if same_boundary:
                    replacement_index = index
                    break
                if overlaps:
                    raise ValueError(
                        "owner annotation partially overlaps an existing expression span"
                    )
            if replacement_index is None:
                spans.append(annotation.span)
            else:
                spans[replacement_index] = annotation.span

        refined = SourceAttribution(
            transport_author_role=base.transport_author_role,
            owner_adopted_expression=base.owner_adopted_expression,
            text_origin_status=base.text_origin_status,
            forwarded=base.forwarded,
            forward_origin_role=base.forward_origin_role,
            expression_spans=tuple(
                sorted(spans, key=lambda item: (item.start, item.end))
            ),
            schema_version=base.schema_version,
        )
        refined.verify(document.text)
        metadata["source_attribution"] = refined.to_dict()
        metadata["owner_annotation_overlay_id"] = overlay.overlay_id
        result.append(
            SourceDocument.create(
                source_id=document.source_id,
                source_revision=document.source_revision,
                observed_at=document.observed_at,
                text=document.text,
                adapter=document.adapter,
                source_kind=document.source_kind,
                raw_chars=document.raw_chars,
                metadata=metadata,
            )
        )
    return tuple(result)


__all__ = [
    "MAX_OWNER_ANNOTATION_BYTES",
    "OWNER_ANNOTATION_DERIVATION",
    "OwnerAnnotationOverlay",
    "OwnerExpressionAnnotation",
    "apply_owner_annotation_overlay",
    "load_owner_annotation_overlay",
]
