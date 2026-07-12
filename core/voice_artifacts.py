"""Immutable voice artifacts and strict evidence-promotion policy.

Voice capture, transcription and semantic evidence are deliberately separate.
A live dialogue turn or transcript never mutates the FVSC evidence ledger merely
because it was recorded.  Promotion requires an explicit policy decision with
speaker attribution, provenance and review state preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Literal, Mapping


CaptureMode = Literal["file_import", "voice_memo", "antourage_dialogue"]
SpeakerAttribution = Literal[
    "declared_owner",
    "verified_owner",
    "uncertain",
    "non_owner",
    "overlap",
]
EvidenceMode = Literal["conversation_only", "save_owner_turns_for_review"]
RetentionClass = Literal["ephemeral", "24h", "7d", "keep"]
PromotionState = Literal["pending_review", "promoted", "discarded"]
PromotionStatus = Literal["prohibited", "manual_review", "automatic"]

_CAPTURE_MODES = {"file_import", "voice_memo", "antourage_dialogue"}
_SPEAKER_ATTRIBUTIONS = {
    "declared_owner",
    "verified_owner",
    "uncertain",
    "non_owner",
    "overlap",
}
_EVIDENCE_MODES = {"conversation_only", "save_owner_turns_for_review"}
_RETENTION_CLASSES = {"ephemeral", "24h", "7d", "keep"}
_PROMOTION_STATES = {"pending_review", "promoted", "discarded"}
_SHA256_LENGTH = 64


def _finite(value: Any, *, field_name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def _bounded_optional(value: float | None, *, field_name: str) -> float | None:
    if value is None:
        return None
    number = _finite(value, field_name=field_name)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{field_name} must be in [0, 1]")
    return number


def _clean(value: str, *, field_name: str) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _optional_clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _validate_sha256(value: str, *, field_name: str) -> str:
    cleaned = _clean(value, field_name=field_name).lower()
    if len(cleaned) != _SHA256_LENGTH or any(c not in "0123456789abcdef" for c in cleaned):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
    return cleaned


def _canonical_json(value: Mapping[str, Any] | None) -> str:
    try:
        return json.dumps(
            dict(value or {}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("metadata must contain JSON-compatible values") from exc


def _content_id(namespace: str, payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        {"namespace": namespace, **dict(payload)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AudioCaptureArtifact:
    """Metadata for imported or explicitly recorded source audio."""

    capture_id: str
    mode: CaptureMode
    started_at: float
    ended_at: float
    sample_rate: int
    channels: int
    source_hash: str
    retention_class: RetentionClass
    declared_owner_only: bool
    evidence_mode: EvidenceMode
    storage_ref: str | None = None
    metadata_json: str = "{}"

    def __post_init__(self) -> None:
        if self.mode not in _CAPTURE_MODES:
            raise ValueError(f"unknown capture mode: {self.mode}")
        if self.retention_class not in _RETENTION_CLASSES:
            raise ValueError(f"unknown retention class: {self.retention_class}")
        if self.evidence_mode not in _EVIDENCE_MODES:
            raise ValueError(f"unknown evidence mode: {self.evidence_mode}")
        started = _finite(self.started_at, field_name="started_at")
        ended = _finite(self.ended_at, field_name="ended_at")
        if ended < started:
            raise ValueError("ended_at must not precede started_at")
        if isinstance(self.sample_rate, bool) or int(self.sample_rate) != self.sample_rate or self.sample_rate < 1:
            raise ValueError("sample_rate must be a positive integer")
        if isinstance(self.channels, bool) or int(self.channels) != self.channels or self.channels < 1:
            raise ValueError("channels must be a positive integer")
        source_hash = _validate_sha256(self.source_hash, field_name="source_hash")
        storage_ref = _optional_clean(self.storage_ref)
        try:
            metadata_json = _canonical_json(json.loads(self.metadata_json))
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("metadata_json must contain a JSON object") from exc

        payload = {
            "mode": self.mode,
            "started_at": started,
            "ended_at": ended,
            "sample_rate": int(self.sample_rate),
            "channels": int(self.channels),
            "source_hash": source_hash,
            "retention_class": self.retention_class,
            "declared_owner_only": bool(self.declared_owner_only),
            "evidence_mode": self.evidence_mode,
            "storage_ref": storage_ref,
            "metadata": json.loads(metadata_json),
        }
        expected = _content_id("fvsc-audio-capture-v1", payload)
        if self.capture_id != expected:
            raise ValueError("capture_id does not match the canonical capture payload")

        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "ended_at", ended)
        object.__setattr__(self, "sample_rate", int(self.sample_rate))
        object.__setattr__(self, "channels", int(self.channels))
        object.__setattr__(self, "source_hash", source_hash)
        object.__setattr__(self, "storage_ref", storage_ref)
        object.__setattr__(self, "metadata_json", metadata_json)

    @classmethod
    def create(
        cls,
        *,
        mode: CaptureMode,
        started_at: float,
        ended_at: float,
        sample_rate: int,
        channels: int,
        source_hash: str,
        retention_class: RetentionClass = "24h",
        declared_owner_only: bool = False,
        evidence_mode: EvidenceMode = "conversation_only",
        storage_ref: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "AudioCaptureArtifact":
        metadata_json = _canonical_json(metadata)
        payload = {
            "mode": mode,
            "started_at": float(started_at),
            "ended_at": float(ended_at),
            "sample_rate": int(sample_rate),
            "channels": int(channels),
            "source_hash": str(source_hash).strip().lower(),
            "retention_class": retention_class,
            "declared_owner_only": bool(declared_owner_only),
            "evidence_mode": evidence_mode,
            "storage_ref": _optional_clean(storage_ref),
            "metadata": json.loads(metadata_json),
        }
        return cls(
            capture_id=_content_id("fvsc-audio-capture-v1", payload),
            mode=mode,
            started_at=started_at,
            ended_at=ended_at,
            sample_rate=sample_rate,
            channels=channels,
            source_hash=source_hash,
            retention_class=retention_class,
            declared_owner_only=declared_owner_only,
            evidence_mode=evidence_mode,
            storage_ref=storage_ref,
            metadata_json=metadata_json,
        )

    @property
    def metadata(self) -> dict[str, Any]:
        return json.loads(self.metadata_json)


@dataclass(frozen=True)
class TranscriptArtifact:
    """One immutable ASR result for a bounded utterance."""

    transcript_id: str
    capture_id: str
    utterance_id: str
    start_seconds: float
    end_seconds: float
    text_raw: str
    text_normalized: str
    asr_backend: str
    model_id: str
    speaker_attribution: SpeakerAttribution
    confidence: float | None = None
    speaker_confidence: float | None = None
    corrected: bool = False
    metadata_json: str = "{}"

    def __post_init__(self) -> None:
        capture_id = _validate_sha256(self.capture_id, field_name="capture_id")
        utterance_id = _clean(self.utterance_id, field_name="utterance_id")
        start = _finite(self.start_seconds, field_name="start_seconds")
        end = _finite(self.end_seconds, field_name="end_seconds")
        if start < 0.0 or end < start:
            raise ValueError("transcript time range is invalid")
        text_raw = _clean(self.text_raw, field_name="text_raw")
        text_normalized = _clean(self.text_normalized, field_name="text_normalized")
        asr_backend = _clean(self.asr_backend, field_name="asr_backend")
        model_id = _clean(self.model_id, field_name="model_id")
        if self.speaker_attribution not in _SPEAKER_ATTRIBUTIONS:
            raise ValueError(f"unknown speaker attribution: {self.speaker_attribution}")
        confidence = _bounded_optional(self.confidence, field_name="confidence")
        speaker_confidence = _bounded_optional(
            self.speaker_confidence,
            field_name="speaker_confidence",
        )
        try:
            metadata_json = _canonical_json(json.loads(self.metadata_json))
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("metadata_json must contain a JSON object") from exc

        payload = {
            "capture_id": capture_id,
            "utterance_id": utterance_id,
            "start_seconds": start,
            "end_seconds": end,
            "text_raw": text_raw,
            "text_normalized": text_normalized,
            "asr_backend": asr_backend,
            "model_id": model_id,
            "speaker_attribution": self.speaker_attribution,
            "confidence": confidence,
            "speaker_confidence": speaker_confidence,
            "corrected": bool(self.corrected),
            "metadata": json.loads(metadata_json),
        }
        expected = _content_id("fvsc-transcript-v1", payload)
        if self.transcript_id != expected:
            raise ValueError("transcript_id does not match the canonical transcript payload")

        object.__setattr__(self, "capture_id", capture_id)
        object.__setattr__(self, "utterance_id", utterance_id)
        object.__setattr__(self, "start_seconds", start)
        object.__setattr__(self, "end_seconds", end)
        object.__setattr__(self, "text_raw", text_raw)
        object.__setattr__(self, "text_normalized", text_normalized)
        object.__setattr__(self, "asr_backend", asr_backend)
        object.__setattr__(self, "model_id", model_id)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "speaker_confidence", speaker_confidence)
        object.__setattr__(self, "metadata_json", metadata_json)

    @classmethod
    def create(
        cls,
        *,
        capture_id: str,
        utterance_id: str,
        start_seconds: float,
        end_seconds: float,
        text_raw: str,
        text_normalized: str,
        asr_backend: str,
        model_id: str,
        speaker_attribution: SpeakerAttribution,
        confidence: float | None = None,
        speaker_confidence: float | None = None,
        corrected: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> "TranscriptArtifact":
        metadata_json = _canonical_json(metadata)
        payload = {
            "capture_id": str(capture_id).strip().lower(),
            "utterance_id": str(utterance_id).strip(),
            "start_seconds": float(start_seconds),
            "end_seconds": float(end_seconds),
            "text_raw": str(text_raw).strip(),
            "text_normalized": str(text_normalized).strip(),
            "asr_backend": str(asr_backend).strip(),
            "model_id": str(model_id).strip(),
            "speaker_attribution": speaker_attribution,
            "confidence": confidence,
            "speaker_confidence": speaker_confidence,
            "corrected": bool(corrected),
            "metadata": json.loads(metadata_json),
        }
        return cls(
            transcript_id=_content_id("fvsc-transcript-v1", payload),
            capture_id=capture_id,
            utterance_id=utterance_id,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            text_raw=text_raw,
            text_normalized=text_normalized,
            asr_backend=asr_backend,
            model_id=model_id,
            speaker_attribution=speaker_attribution,
            confidence=confidence,
            speaker_confidence=speaker_confidence,
            corrected=corrected,
            metadata_json=metadata_json,
        )

    @property
    def metadata(self) -> dict[str, Any]:
        return json.loads(self.metadata_json)


@dataclass(frozen=True)
class VoiceEvidenceCandidate:
    """Reviewable bridge between a transcript and semantic assertions."""

    candidate_id: str
    transcript_id: str
    capture_mode: CaptureMode
    evidence_mode: EvidenceMode
    speaker_attribution: SpeakerAttribution
    transcript_confidence: float | None
    speaker_confidence: float | None
    promotion_state: PromotionState = "pending_review"
    reviewed_by_user: bool = False
    explicit_user_approval: bool = False

    def __post_init__(self) -> None:
        transcript_id = _validate_sha256(self.transcript_id, field_name="transcript_id")
        if self.capture_mode not in _CAPTURE_MODES:
            raise ValueError(f"unknown capture mode: {self.capture_mode}")
        if self.evidence_mode not in _EVIDENCE_MODES:
            raise ValueError(f"unknown evidence mode: {self.evidence_mode}")
        if self.speaker_attribution not in _SPEAKER_ATTRIBUTIONS:
            raise ValueError(f"unknown speaker attribution: {self.speaker_attribution}")
        if self.promotion_state not in _PROMOTION_STATES:
            raise ValueError(f"unknown promotion state: {self.promotion_state}")
        transcript_confidence = _bounded_optional(
            self.transcript_confidence,
            field_name="transcript_confidence",
        )
        speaker_confidence = _bounded_optional(
            self.speaker_confidence,
            field_name="speaker_confidence",
        )
        payload = {
            "transcript_id": transcript_id,
            "capture_mode": self.capture_mode,
            "evidence_mode": self.evidence_mode,
            "speaker_attribution": self.speaker_attribution,
            "transcript_confidence": transcript_confidence,
            "speaker_confidence": speaker_confidence,
            "promotion_state": self.promotion_state,
            "reviewed_by_user": bool(self.reviewed_by_user),
            "explicit_user_approval": bool(self.explicit_user_approval),
        }
        expected = _content_id("fvsc-voice-candidate-v1", payload)
        if self.candidate_id != expected:
            raise ValueError("candidate_id does not match the canonical candidate payload")
        object.__setattr__(self, "transcript_id", transcript_id)
        object.__setattr__(self, "transcript_confidence", transcript_confidence)
        object.__setattr__(self, "speaker_confidence", speaker_confidence)

    @classmethod
    def create(
        cls,
        *,
        transcript_id: str,
        capture_mode: CaptureMode,
        evidence_mode: EvidenceMode,
        speaker_attribution: SpeakerAttribution,
        transcript_confidence: float | None,
        speaker_confidence: float | None,
        promotion_state: PromotionState = "pending_review",
        reviewed_by_user: bool = False,
        explicit_user_approval: bool = False,
    ) -> "VoiceEvidenceCandidate":
        payload = {
            "transcript_id": str(transcript_id).strip().lower(),
            "capture_mode": capture_mode,
            "evidence_mode": evidence_mode,
            "speaker_attribution": speaker_attribution,
            "transcript_confidence": transcript_confidence,
            "speaker_confidence": speaker_confidence,
            "promotion_state": promotion_state,
            "reviewed_by_user": bool(reviewed_by_user),
            "explicit_user_approval": bool(explicit_user_approval),
        }
        return cls(
            candidate_id=_content_id("fvsc-voice-candidate-v1", payload),
            transcript_id=transcript_id,
            capture_mode=capture_mode,
            evidence_mode=evidence_mode,
            speaker_attribution=speaker_attribution,
            transcript_confidence=transcript_confidence,
            speaker_confidence=speaker_confidence,
            promotion_state=promotion_state,
            reviewed_by_user=reviewed_by_user,
            explicit_user_approval=explicit_user_approval,
        )


@dataclass(frozen=True)
class PromotionDecision:
    status: PromotionStatus
    reasons: tuple[str, ...]
    evidence_weight_multiplier: float

    @property
    def permitted(self) -> bool:
        return self.status != "prohibited"


def decide_promotion(
    candidate: VoiceEvidenceCandidate,
    *,
    automatic_promotion_enabled: bool = False,
    minimum_transcript_confidence: float = 0.75,
    minimum_speaker_confidence: float = 0.80,
) -> PromotionDecision:
    """Return the strict initial promotion decision for one voice candidate.

    ``automatic`` is deliberately difficult to reach.  It requires an explicit
    evidence-producing mode, verified owner attribution, calibrated confidence
    and an external feature flag.  Manual approval remains possible for declared
    owner and uncertain/overlap cases, but never for known non-owner speech.
    """

    transcript_threshold = _bounded_optional(
        minimum_transcript_confidence,
        field_name="minimum_transcript_confidence",
    )
    speaker_threshold = _bounded_optional(
        minimum_speaker_confidence,
        field_name="minimum_speaker_confidence",
    )
    assert transcript_threshold is not None
    assert speaker_threshold is not None

    reasons: list[str] = []
    if candidate.evidence_mode == "conversation_only":
        return PromotionDecision(
            status="prohibited",
            reasons=("conversation_only_mode",),
            evidence_weight_multiplier=0.0,
        )
    if candidate.speaker_attribution == "non_owner":
        return PromotionDecision(
            status="prohibited",
            reasons=("known_non_owner",),
            evidence_weight_multiplier=0.0,
        )
    if candidate.promotion_state == "discarded":
        return PromotionDecision(
            status="prohibited",
            reasons=("candidate_discarded",),
            evidence_weight_multiplier=0.0,
        )

    transcript_ok = (
        candidate.transcript_confidence is not None
        and candidate.transcript_confidence >= transcript_threshold
    )
    speaker_ok = (
        candidate.speaker_confidence is not None
        and candidate.speaker_confidence >= speaker_threshold
    )

    if candidate.speaker_attribution in {"uncertain", "overlap"}:
        reasons.append(candidate.speaker_attribution)
    if not transcript_ok:
        reasons.append("low_or_missing_transcript_confidence")
    if candidate.speaker_attribution == "verified_owner" and not speaker_ok:
        reasons.append("low_or_missing_speaker_confidence")

    can_automatic = (
        automatic_promotion_enabled
        and candidate.speaker_attribution == "verified_owner"
        and transcript_ok
        and speaker_ok
        and candidate.reviewed_by_user
        and candidate.explicit_user_approval
    )
    if can_automatic:
        return PromotionDecision(
            status="automatic",
            reasons=("verified_owner_calibrated",),
            evidence_weight_multiplier=0.75,
        )

    if candidate.explicit_user_approval and candidate.reviewed_by_user:
        if candidate.speaker_attribution in {
            "declared_owner",
            "verified_owner",
            "uncertain",
            "overlap",
        }:
            return PromotionDecision(
                status="manual_review",
                reasons=tuple(reasons or ["explicit_user_approval"]),
                evidence_weight_multiplier=0.5 if reasons else 0.75,
            )

    return PromotionDecision(
        status="manual_review",
        reasons=tuple(reasons or ["user_review_required"]),
        evidence_weight_multiplier=0.0,
    )
