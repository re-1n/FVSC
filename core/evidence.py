"""Immutable, content-addressed evidence events for FVSC.

Aggregated density matrices are derived state. This module defines the future
source-of-truth records from which semantic snapshots can be rebuilt. Events are
JSON-serialisable, append-only and content-addressed independently of ingestion
time, so replaying the same source revision produces the same event identifier.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import time
from typing import Any, Literal, Mapping


EventKind = Literal["assertion", "retraction", "supersession"]
_EVENT_KINDS = {"assertion", "retraction", "supersession"}
_SHA256_HEX_LENGTH = 64


def _canonical_json(value: Mapping[str, Any] | None) -> str:
    """Encode a JSON mapping deterministically and reject invalid values."""
    if value is None:
        value = {}
    if not isinstance(value, Mapping):
        raise ValueError("context and provenance must be mappings")
    try:
        return json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("context and provenance must contain JSON values") from exc


def _clean_term(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _optional_clean_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _non_negative_integer(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer")
    try:
        integer = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a non-negative integer") from exc
    if integer < 0 or integer != value:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return integer


def _validate_sha256(value: str, *, field_name: str) -> None:
    if len(value) != _SHA256_HEX_LENGTH or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")


def _normalize_fields(
    *,
    event_kind: str,
    source_id: str,
    observed_at: float,
    recorded_at: float,
    extractor: str,
    extractor_version: str,
    source_revision: str | None,
    subject: str | None,
    relation: str | None,
    object_: str | None,
    target_event_id: str | None,
    polarity: float,
    modality: float,
    intensity: float,
    confidence: float,
    interpretation_layer: Any,
    context_json: str,
    provenance_json: str,
) -> dict[str, Any]:
    if event_kind not in _EVENT_KINDS:
        raise ValueError(f"unknown event_kind: {event_kind}")

    source_id_clean = str(source_id).strip()
    extractor_clean = str(extractor).strip()
    extractor_version_clean = str(extractor_version).strip()
    if not source_id_clean:
        raise ValueError("source_id must not be empty")
    if not extractor_clean:
        raise ValueError("extractor must not be empty")
    if not extractor_version_clean:
        raise ValueError("extractor_version must not be empty")

    observed = float(observed_at)
    recorded = float(recorded_at)
    if not math.isfinite(observed) or not math.isfinite(recorded):
        raise ValueError("event timestamps must be finite")

    normalized_numbers: dict[str, float] = {}
    for name, raw_value, lower, upper in (
        ("polarity", polarity, -1.0, 1.0),
        ("modality", modality, 0.0, 1.0),
        ("intensity", intensity, 0.0, 1.0),
        ("confidence", confidence, 0.0, 1.0),
    ):
        value = float(raw_value)
        if not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError(f"{name} must be finite and in [{lower:g}, {upper:g}]")
        normalized_numbers[name] = value

    layer = _non_negative_integer(
        interpretation_layer,
        field_name="interpretation_layer",
    )
    subject_clean = _clean_term(subject, field_name="subject")
    relation_clean = _clean_term(relation, field_name="relation")
    object_clean = _clean_term(object_, field_name="object")
    revision_clean = _optional_clean_string(source_revision)
    target_clean = _optional_clean_string(target_event_id)
    if target_clean is not None:
        _validate_sha256(target_clean, field_name="target_event_id")

    try:
        context_clean = _canonical_json(json.loads(context_json))
        provenance_clean = _canonical_json(json.loads(provenance_json))
    except json.JSONDecodeError as exc:
        raise ValueError("context_json and provenance_json must contain JSON objects") from exc

    has_statement = (
        subject_clean is not None
        and relation_clean is not None
        and object_clean is not None
    )
    if event_kind == "assertion":
        if not has_statement:
            raise ValueError("assertion events require subject, relation and object")
        if target_clean is not None:
            raise ValueError("assertion events cannot target another event")
    elif event_kind == "retraction":
        if target_clean is None:
            raise ValueError("retraction events require target_event_id")
        if subject_clean is not None or relation_clean is not None or object_clean is not None:
            raise ValueError("retraction events cannot carry a replacement statement")
    elif event_kind == "supersession":
        if target_clean is None:
            raise ValueError("supersession events require target_event_id")
        if not has_statement:
            raise ValueError("supersession events require a replacement statement")

    return {
        "event_kind": event_kind,
        "source_id": source_id_clean,
        "observed_at": observed,
        "recorded_at": recorded,
        "extractor": extractor_clean,
        "extractor_version": extractor_version_clean,
        "source_revision": revision_clean,
        "subject": subject_clean,
        "relation": relation_clean,
        "object": object_clean,
        "target_event_id": target_clean,
        "polarity": normalized_numbers["polarity"],
        "modality": normalized_numbers["modality"],
        "intensity": normalized_numbers["intensity"],
        "confidence": normalized_numbers["confidence"],
        "interpretation_layer": layer,
        "context_json": context_clean,
        "provenance_json": provenance_clean,
    }


def _identity_payload(fields: Mapping[str, Any]) -> dict[str, Any]:
    """Return the content-addressed subset of normalized event fields."""
    return {
        "event_kind": fields["event_kind"],
        "source_id": fields["source_id"],
        "source_revision": fields["source_revision"],
        "observed_at": fields["observed_at"],
        "subject": fields["subject"],
        "relation": fields["relation"],
        "object": fields["object"],
        "target_event_id": fields["target_event_id"],
        "polarity": fields["polarity"],
        "modality": fields["modality"],
        "intensity": fields["intensity"],
        "confidence": fields["confidence"],
        "interpretation_layer": fields["interpretation_layer"],
        "extractor": fields["extractor"],
        "extractor_version": fields["extractor_version"],
        "context": json.loads(fields["context_json"]),
        "provenance": json.loads(fields["provenance_json"]),
    }


def _compute_event_id(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceEvent:
    """One immutable assertion or lifecycle operation over prior evidence."""

    event_id: str
    event_kind: EventKind
    source_id: str
    observed_at: float
    recorded_at: float
    extractor: str
    extractor_version: str

    source_revision: str | None = None
    subject: str | None = None
    relation: str | None = None
    object: str | None = None
    target_event_id: str | None = None

    polarity: float = 1.0
    modality: float = 1.0
    intensity: float = 0.5
    confidence: float = 1.0
    interpretation_layer: int = 0

    context_json: str = "{}"
    provenance_json: str = "{}"

    def __post_init__(self) -> None:
        normalized = _normalize_fields(
            event_kind=self.event_kind,
            source_id=self.source_id,
            observed_at=self.observed_at,
            recorded_at=self.recorded_at,
            extractor=self.extractor,
            extractor_version=self.extractor_version,
            source_revision=self.source_revision,
            subject=self.subject,
            relation=self.relation,
            object_=self.object,
            target_event_id=self.target_event_id,
            polarity=self.polarity,
            modality=self.modality,
            intensity=self.intensity,
            confidence=self.confidence,
            interpretation_layer=self.interpretation_layer,
            context_json=self.context_json,
            provenance_json=self.provenance_json,
        )
        expected_id = _compute_event_id(_identity_payload(normalized))
        if self.event_id != expected_id:
            raise ValueError("event_id does not match the canonical event payload")

        for field_name, value in normalized.items():
            object.__setattr__(self, field_name, value)

    @classmethod
    def create(
        cls,
        *,
        event_kind: EventKind,
        source_id: str,
        observed_at: float,
        extractor: str,
        extractor_version: str,
        recorded_at: float | None = None,
        source_revision: str | None = None,
        subject: str | None = None,
        relation: str | None = None,
        object: str | None = None,
        target_event_id: str | None = None,
        polarity: float = 1.0,
        modality: float = 1.0,
        intensity: float = 0.5,
        confidence: float = 1.0,
        interpretation_layer: int = 0,
        context: Mapping[str, Any] | None = None,
        provenance: Mapping[str, Any] | None = None,
    ) -> "EvidenceEvent":
        normalized = _normalize_fields(
            event_kind=event_kind,
            source_id=source_id,
            observed_at=observed_at,
            recorded_at=time.time() if recorded_at is None else recorded_at,
            extractor=extractor,
            extractor_version=extractor_version,
            source_revision=source_revision,
            subject=subject,
            relation=relation,
            object_=object,
            target_event_id=target_event_id,
            polarity=polarity,
            modality=modality,
            intensity=intensity,
            confidence=confidence,
            interpretation_layer=interpretation_layer,
            context_json=_canonical_json(context),
            provenance_json=_canonical_json(provenance),
        )
        event_id = _compute_event_id(_identity_payload(normalized))
        return cls(event_id=event_id, **normalized)

    @classmethod
    def assertion(cls, **kwargs: Any) -> "EvidenceEvent":
        return cls.create(event_kind="assertion", **kwargs)

    @classmethod
    def retraction(cls, **kwargs: Any) -> "EvidenceEvent":
        return cls.create(event_kind="retraction", **kwargs)

    @classmethod
    def supersession(cls, **kwargs: Any) -> "EvidenceEvent":
        return cls.create(event_kind="supersession", **kwargs)

    @property
    def context(self) -> dict[str, Any]:
        return json.loads(self.context_json)

    @property
    def provenance(self) -> dict[str, Any]:
        return json.loads(self.provenance_json)

    def identity_payload(self) -> dict[str, Any]:
        return _identity_payload(
            {
                "event_kind": self.event_kind,
                "source_id": self.source_id,
                "source_revision": self.source_revision,
                "observed_at": self.observed_at,
                "subject": self.subject,
                "relation": self.relation,
                "object": self.object,
                "target_event_id": self.target_event_id,
                "polarity": self.polarity,
                "modality": self.modality,
                "intensity": self.intensity,
                "confidence": self.confidence,
                "interpretation_layer": self.interpretation_layer,
                "extractor": self.extractor,
                "extractor_version": self.extractor_version,
                "context_json": self.context_json,
                "provenance_json": self.provenance_json,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            **self.identity_payload(),
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvidenceEvent":
        payload = dict(data)
        context_json = _canonical_json(payload.pop("context", None))
        provenance_json = _canonical_json(payload.pop("provenance", None))
        return cls(
            context_json=context_json,
            provenance_json=provenance_json,
            **payload,
        )
