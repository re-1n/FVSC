"""Immutable, content-addressed evidence events for FVSC.

Aggregated density matrices are derived state.  This module defines the future
source-of-truth records from which semantic snapshots can be rebuilt.  Events are
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


def _canonical_json(value: Mapping[str, Any] | None) -> str:
    """Encode a JSON mapping deterministically and reject non-finite numbers."""
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


def _identity_payload(
    *,
    event_kind: str,
    source_id: str,
    source_revision: str | None,
    observed_at: float,
    subject: str | None,
    relation: str | None,
    object_: str | None,
    target_event_id: str | None,
    polarity: float,
    modality: float,
    intensity: float,
    confidence: float,
    interpretation_layer: int,
    extractor: str,
    extractor_version: str,
    context_json: str,
    provenance_json: str,
) -> dict[str, Any]:
    return {
        "event_kind": event_kind,
        "source_id": source_id,
        "source_revision": source_revision,
        "observed_at": observed_at,
        "subject": subject,
        "relation": relation,
        "object": object_,
        "target_event_id": target_event_id,
        "polarity": polarity,
        "modality": modality,
        "intensity": intensity,
        "confidence": confidence,
        "interpretation_layer": interpretation_layer,
        "extractor": extractor,
        "extractor_version": extractor_version,
        "context": json.loads(context_json),
        "provenance": json.loads(provenance_json),
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


def _clean_term(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


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
        if self.event_kind not in _EVENT_KINDS:
            raise ValueError(f"unknown event_kind: {self.event_kind}")

        source_id = str(self.source_id).strip()
        extractor = str(self.extractor).strip()
        extractor_version = str(self.extractor_version).strip()
        source_revision = (
            str(self.source_revision).strip() if self.source_revision is not None else None
        )
        subject = _clean_term(self.subject, field_name="subject")
        relation = _clean_term(self.relation, field_name="relation")
        object_ = _clean_term(self.object, field_name="object")
        target_event_id = (
            str(self.target_event_id).strip() if self.target_event_id is not None else None
        )

        if not source_id:
            raise ValueError("source_id must not be empty")
        if not extractor:
            raise ValueError("extractor must not be empty")
        if not extractor_version:
            raise ValueError("extractor_version must not be empty")
        if source_revision == "":
            source_revision = None

        observed_at = float(self.observed_at)
        recorded_at = float(self.recorded_at)
        if not math.isfinite(observed_at) or not math.isfinite(recorded_at):
            raise ValueError("event timestamps must be finite")

        polarity = float(self.polarity)
        modality = float(self.modality)
        intensity = float(self.intensity)
        confidence = float(self.confidence)
        for name, value, lower, upper in (
            ("polarity", polarity, -1.0, 1.0),
            ("modality", modality, 0.0, 1.0),
            ("intensity", intensity, 0.0, 1.0),
            ("confidence", confidence, 0.0, 1.0),
        ):
            if not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError(f"{name} must be finite and in [{lower:g}, {upper:g}]")

        if isinstance(self.interpretation_layer, bool):
            raise ValueError("interpretation_layer must be a non-negative integer")
        interpretation_layer = int(self.interpretation_layer)
        if interpretation_layer < 0 or interpretation_layer != self.interpretation_layer:
            raise ValueError("interpretation_layer must be a non-negative integer")

        context_json = _canonical_json(json.loads(self.context_json))
        provenance_json = _canonical_json(json.loads(self.provenance_json))

        has_statement = subject is not None and relation is not None and object_ is not None
        if self.event_kind == "assertion":
            if not has_statement:
                raise ValueError("assertion events require subject, relation and object")
            if target_event_id is not None:
                raise ValueError("assertion events cannot target another event")
        elif self.event_kind == "retraction":
            if target_event_id is None:
                raise ValueError("retraction events require target_event_id")
            if subject is not None or relation is not None or object_ is not None:
                raise ValueError("retraction events cannot carry a replacement statement")
        elif self.event_kind == "supersession":
            if target_event_id is None:
                raise ValueError("supersession events require target_event_id")
            if not has_statement:
                raise ValueError("supersession events require a replacement statement")

        if target_event_id is not None:
            if len(target_event_id) != 64 or any(c not in "0123456789abcdef" for c in target_event_id):
                raise ValueError("target_event_id must be a lowercase SHA-256 hex digest")

        payload = _identity_payload(
            event_kind=self.event_kind,
            source_id=source_id,
            source_revision=source_revision,
            observed_at=observed_at,
            subject=subject,
            relation=relation,
            object_=object_,
            target_event_id=target_event_id,
            polarity=polarity,
            modality=modality,
            intensity=intensity,
            confidence=confidence,
            interpretation_layer=interpretation_layer,
            extractor=extractor,
            extractor_version=extractor_version,
            context_json=context_json,
            provenance_json=provenance_json,
        )
        expected_id = _compute_event_id(payload)
        if self.event_id != expected_id:
            raise ValueError("event_id does not match the canonical event payload")

        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "source_revision", source_revision)
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "relation", relation)
        object.__setattr__(self, "object", object_)
        object.__setattr__(self, "target_event_id", target_event_id)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "recorded_at", recorded_at)
        object.__setattr__(self, "extractor", extractor)
        object.__setattr__(self, "extractor_version", extractor_version)
        object.__setattr__(self, "polarity", polarity)
        object.__setattr__(self, "modality", modality)
        object.__setattr__(self, "intensity", intensity)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "interpretation_layer", interpretation_layer)
        object.__setattr__(self, "context_json", context_json)
        object.__setattr__(self, "provenance_json", provenance_json)

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
        context_json = _canonical_json(context)
        provenance_json = _canonical_json(provenance)
        source_id_clean = str(source_id).strip()
        extractor_clean = str(extractor).strip()
        extractor_version_clean = str(extractor_version).strip()
        source_revision_clean = (
            str(source_revision).strip() if source_revision is not None else None
        )
        subject_clean = _clean_term(subject, field_name="subject")
        relation_clean = _clean_term(relation, field_name="relation")
        object_clean = _clean_term(object, field_name="object")
        target_clean = str(target_event_id).strip() if target_event_id is not None else None

        payload = _identity_payload(
            event_kind=event_kind,
            source_id=source_id_clean,
            source_revision=source_revision_clean,
            observed_at=float(observed_at),
            subject=subject_clean,
            relation=relation_clean,
            object_=object_clean,
            target_event_id=target_clean,
            polarity=float(polarity),
            modality=float(modality),
            intensity=float(intensity),
            confidence=float(confidence),
            interpretation_layer=int(interpretation_layer),
            extractor=extractor_clean,
            extractor_version=extractor_version_clean,
            context_json=context_json,
            provenance_json=provenance_json,
        )
        event_id = _compute_event_id(payload)
        return cls(
            event_id=event_id,
            event_kind=event_kind,
            source_id=source_id_clean,
            source_revision=source_revision_clean,
            observed_at=float(observed_at),
            recorded_at=time.time() if recorded_at is None else float(recorded_at),
            subject=subject_clean,
            relation=relation_clean,
            object=object_clean,
            target_event_id=target_clean,
            polarity=float(polarity),
            modality=float(modality),
            intensity=float(intensity),
            confidence=float(confidence),
            interpretation_layer=int(interpretation_layer),
            extractor=extractor_clean,
            extractor_version=extractor_version_clean,
            context_json=context_json,
            provenance_json=provenance_json,
        )

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
            event_kind=self.event_kind,
            source_id=self.source_id,
            source_revision=self.source_revision,
            observed_at=self.observed_at,
            subject=self.subject,
            relation=self.relation,
            object_=self.object,
            target_event_id=self.target_event_id,
            polarity=self.polarity,
            modality=self.modality,
            intensity=self.intensity,
            confidence=self.confidence,
            interpretation_layer=self.interpretation_layer,
            extractor=self.extractor,
            extractor_version=self.extractor_version,
            context_json=self.context_json,
            provenance_json=self.provenance_json,
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
            object=payload.pop("object", None),
            **payload,
        )
