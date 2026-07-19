"""Typed source-level attribution without duplicating private source bodies."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Iterable, Literal, Mapping


ActorRole = Literal["owner", "non_owner", "unknown"]
TextOriginStatus = Literal["owner", "external", "mixed", "unresolved"]
OwnerRelation = Literal["authored", "adopted", "selected", "not_adopted", "unknown"]
ExpressionKind = Literal[
    "quotation",
    "song_lyric",
    "ai_output",
    "translated_external",
    "owner_commentary",
    "unclassified",
]

ACTOR_ROLES = frozenset({"owner", "non_owner", "unknown"})
TEXT_ORIGIN_STATUSES = frozenset({"owner", "external", "mixed", "unresolved"})
OWNER_RELATIONS = frozenset(
    {"authored", "adopted", "selected", "not_adopted", "unknown"}
)
EXPRESSION_KINDS = frozenset(
    {
        "quotation",
        "song_lyric",
        "ai_output",
        "translated_external",
        "owner_commentary",
        "unclassified",
    }
)


def _digest(value: Any, *, field: str) -> str:
    digest = str(value).strip()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return digest


@dataclass(frozen=True)
class ExpressionSpan:
    """One typed half-open span over normalized ``SourceDocument.text``."""

    start: int
    end: int
    text_sha256: str
    kind: ExpressionKind
    origin_status: TextOriginStatus = "unresolved"
    owner_relation: OwnerRelation = "unknown"
    derivation: str = "explicit-annotation"

    def __post_init__(self) -> None:
        if (
            isinstance(self.start, bool)
            or isinstance(self.end, bool)
            or not isinstance(self.start, int)
            or not isinstance(self.end, int)
            or self.start < 0
            or self.end <= self.start
        ):
            raise ValueError("expression span offsets must be a non-empty half-open range")
        if self.kind not in EXPRESSION_KINDS:
            raise ValueError(f"unknown expression kind: {self.kind!r}")
        if self.origin_status not in TEXT_ORIGIN_STATUSES:
            raise ValueError(f"unknown text origin status: {self.origin_status!r}")
        if self.owner_relation not in OWNER_RELATIONS:
            raise ValueError(f"unknown owner relation: {self.owner_relation!r}")
        derivation = str(self.derivation).strip()
        if not derivation:
            raise ValueError("expression span derivation must not be empty")
        object.__setattr__(
            self,
            "text_sha256",
            _digest(self.text_sha256, field="expression span digest"),
        )
        object.__setattr__(self, "derivation", derivation)

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        start: int,
        end: int,
        kind: ExpressionKind,
        origin_status: TextOriginStatus = "unresolved",
        owner_relation: OwnerRelation = "unknown",
        derivation: str = "explicit-annotation",
    ) -> "ExpressionSpan":
        if end > len(text):
            raise ValueError("expression span extends beyond source text")
        value = text[start:end]
        if not value:
            raise ValueError("expression span must not be empty")
        return cls(
            start=start,
            end=end,
            text_sha256=hashlib.sha256(value.encode("utf-8")).hexdigest(),
            kind=kind,
            origin_status=origin_status,
            owner_relation=owner_relation,
            derivation=derivation,
        )

    def verify(self, text: str) -> None:
        if self.end > len(text):
            raise ValueError("expression span extends beyond source text")
        digest = hashlib.sha256(text[self.start : self.end].encode("utf-8")).hexdigest()
        if digest != self.text_sha256:
            raise ValueError("expression span does not match source text")

    def to_dict(self) -> dict[str, Any]:
        return {
            "derivation": self.derivation,
            "end": self.end,
            "kind": self.kind,
            "origin_status": self.origin_status,
            "owner_relation": self.owner_relation,
            "start": self.start,
            "text_sha256": self.text_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExpressionSpan":
        return cls(
            start=value.get("start", -1),
            end=value.get("end", -1),
            text_sha256=value.get("text_sha256", ""),
            kind=value.get("kind", "unclassified"),
            origin_status=value.get("origin_status", "unresolved"),
            owner_relation=value.get("owner_relation", "unknown"),
            derivation=value.get("derivation", "explicit-annotation"),
        )


@dataclass(frozen=True)
class SourceAttribution:
    """Safe attribution envelope for one source revision.

    ``transport_author_role`` identifies who sent or published the envelope. It does
    not assert who composed every substring. ``owner_adopted_expression`` records the
    current owner-selection policy but does not imply literal endorsement.
    """

    transport_author_role: ActorRole
    owner_adopted_expression: bool
    text_origin_status: TextOriginStatus = "unresolved"
    forwarded: bool = False
    forward_origin_role: ActorRole | None = None
    expression_spans: tuple[ExpressionSpan, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported source-attribution schema version")
        if self.transport_author_role not in ACTOR_ROLES:
            raise ValueError(
                f"unknown transport author role: {self.transport_author_role!r}"
            )
        if not isinstance(self.owner_adopted_expression, bool):
            raise ValueError("owner_adopted_expression must be boolean")
        if self.text_origin_status not in TEXT_ORIGIN_STATUSES:
            raise ValueError(f"unknown text origin status: {self.text_origin_status!r}")
        if not isinstance(self.forwarded, bool):
            raise ValueError("forwarded must be boolean")
        if self.forward_origin_role is not None and self.forward_origin_role not in ACTOR_ROLES:
            raise ValueError(f"unknown forward origin role: {self.forward_origin_role!r}")
        if not self.forwarded and self.forward_origin_role is not None:
            raise ValueError("a non-forwarded source cannot have a forward origin role")
        ordered = tuple(sorted(self.expression_spans, key=lambda item: (item.start, item.end)))
        if ordered != self.expression_spans:
            raise ValueError("expression spans must be sorted")
        previous_end = 0
        for span in ordered:
            if span.start < previous_end:
                raise ValueError("expression spans must not overlap")
            previous_end = span.end

    def verify(self, text: str) -> None:
        for span in self.expression_spans:
            span.verify(text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expression_spans": [item.to_dict() for item in self.expression_spans],
            "forward_origin_role": self.forward_origin_role,
            "forwarded": self.forwarded,
            "owner_adopted_expression": self.owner_adopted_expression,
            "schema_version": self.schema_version,
            "text_origin_status": self.text_origin_status,
            "transport_author_role": self.transport_author_role,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceAttribution":
        raw_spans = value.get("expression_spans", [])
        if not isinstance(raw_spans, list):
            raise ValueError("source-attribution expression_spans must be an array")
        return cls(
            transport_author_role=value.get("transport_author_role", "unknown"),
            owner_adopted_expression=value.get("owner_adopted_expression", False),
            text_origin_status=value.get("text_origin_status", "unresolved"),
            forwarded=value.get("forwarded", False),
            forward_origin_role=value.get("forward_origin_role"),
            expression_spans=tuple(ExpressionSpan.from_dict(item) for item in raw_spans),
            schema_version=value.get("schema_version", 0),
        )

    @classmethod
    def from_metadata(cls, metadata: Mapping[str, Any]) -> "SourceAttribution":
        raw = metadata.get("source_attribution")
        if isinstance(raw, dict):
            return cls.from_dict(raw)

        owner_authored = metadata.get("owner_authored")
        if owner_authored is True:
            author_role: ActorRole = "owner"
        elif owner_authored is False and metadata.get("author_key"):
            author_role = "non_owner"
        else:
            author_role = "unknown"
        forwarded = metadata.get("forwarded") is True
        return cls(
            transport_author_role=author_role,
            owner_adopted_expression=metadata.get("owner_adopted_expression") is True,
            text_origin_status="unresolved",
            forwarded=forwarded,
            forward_origin_role="unknown" if forwarded else None,
        )


def source_attribution(
    *,
    transport_author_role: ActorRole,
    owner_adopted_expression: bool,
    text_origin_status: TextOriginStatus = "unresolved",
    forwarded: bool = False,
    forward_origin_role: ActorRole | None = None,
    expression_spans: Iterable[ExpressionSpan] = (),
) -> SourceAttribution:
    """Build a deterministically ordered source-attribution envelope."""
    return SourceAttribution(
        transport_author_role=transport_author_role,
        owner_adopted_expression=owner_adopted_expression,
        text_origin_status=text_origin_status,
        forwarded=forwarded,
        forward_origin_role=forward_origin_role,
        expression_spans=tuple(sorted(expression_spans, key=lambda item: (item.start, item.end))),
    )


__all__ = [
    "ACTOR_ROLES",
    "EXPRESSION_KINDS",
    "OWNER_RELATIONS",
    "TEXT_ORIGIN_STATUSES",
    "ActorRole",
    "ExpressionKind",
    "ExpressionSpan",
    "OwnerRelation",
    "SourceAttribution",
    "TextOriginStatus",
    "source_attribution",
]
