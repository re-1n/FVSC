"""Local owner-speaker verification contracts and conservative decisions."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Protocol, Sequence

from .voice_artifacts import SpeakerAttribution


def _clean(value: str, *, field_name: str) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _bounded(value: float, *, field_name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{field_name} must be finite and in [0, 1]")
    return number


def _profile_id(payload: dict) -> str:
    canonical = json.dumps(
        {"namespace": "fvsc-speaker-profile-v1", **payload},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SpeakerProfile:
    profile_id: str
    label: str
    verifier_backend: str
    model_id: str
    embedding_revision: str
    created_at: float
    sample_count: int
    threshold: float
    rejection_margin: float = 0.15

    def __post_init__(self) -> None:
        label = _clean(self.label, field_name="label")
        verifier_backend = _clean(self.verifier_backend, field_name="verifier_backend")
        model_id = _clean(self.model_id, field_name="model_id")
        embedding_revision = _clean(self.embedding_revision, field_name="embedding_revision")
        created_at = float(self.created_at)
        if not math.isfinite(created_at):
            raise ValueError("created_at must be finite")
        if isinstance(self.sample_count, bool) or int(self.sample_count) != self.sample_count:
            raise ValueError("sample_count must be a positive integer")
        sample_count = int(self.sample_count)
        if sample_count < 1:
            raise ValueError("sample_count must be a positive integer")
        threshold = _bounded(self.threshold, field_name="threshold")
        rejection_margin = _bounded(self.rejection_margin, field_name="rejection_margin")
        if rejection_margin > threshold:
            raise ValueError("rejection_margin must not exceed threshold")

        payload = {
            "label": label,
            "verifier_backend": verifier_backend,
            "model_id": model_id,
            "embedding_revision": embedding_revision,
            "created_at": created_at,
            "sample_count": sample_count,
            "threshold": threshold,
            "rejection_margin": rejection_margin,
        }
        expected = _profile_id(payload)
        if self.profile_id != expected:
            raise ValueError("profile_id does not match the canonical profile payload")

        object.__setattr__(self, "label", label)
        object.__setattr__(self, "verifier_backend", verifier_backend)
        object.__setattr__(self, "model_id", model_id)
        object.__setattr__(self, "embedding_revision", embedding_revision)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "sample_count", sample_count)
        object.__setattr__(self, "threshold", threshold)
        object.__setattr__(self, "rejection_margin", rejection_margin)

    @classmethod
    def create(
        cls,
        *,
        label: str,
        verifier_backend: str,
        model_id: str,
        embedding_revision: str,
        created_at: float,
        sample_count: int,
        threshold: float,
        rejection_margin: float = 0.15,
    ) -> "SpeakerProfile":
        payload = {
            "label": str(label).strip(),
            "verifier_backend": str(verifier_backend).strip(),
            "model_id": str(model_id).strip(),
            "embedding_revision": str(embedding_revision).strip(),
            "created_at": float(created_at),
            "sample_count": int(sample_count),
            "threshold": float(threshold),
            "rejection_margin": float(rejection_margin),
        }
        return cls(profile_id=_profile_id(payload), **payload)


@dataclass(frozen=True)
class SpeakerDecision:
    attribution: SpeakerAttribution
    profile_id: str | None
    score: float | None
    threshold: float | None
    quality_ok: bool
    reasons: tuple[str, ...]


class SpeakerVerifier(Protocol):
    backend_id: str
    model_id: str

    def enroll(
        self,
        audio_refs: Sequence[str],
        *,
        label: str,
        created_at: float,
    ) -> SpeakerProfile:
        ...

    def verify(self, audio_ref: str, profile: SpeakerProfile) -> SpeakerDecision:
        ...


def decide_speaker(
    *,
    declared_owner_only: bool,
    profile: SpeakerProfile | None,
    score: float | None,
    quality_ok: bool,
    overlap: bool = False,
) -> SpeakerDecision:
    """Classify a speaker without allowing declaration to override a mismatch."""

    if overlap:
        return SpeakerDecision(
            attribution="overlap",
            profile_id=profile.profile_id if profile else None,
            score=score,
            threshold=profile.threshold if profile else None,
            quality_ok=quality_ok,
            reasons=("overlapping_speech",),
        )
    if not quality_ok:
        return SpeakerDecision(
            attribution="uncertain",
            profile_id=profile.profile_id if profile else None,
            score=score,
            threshold=profile.threshold if profile else None,
            quality_ok=False,
            reasons=("insufficient_audio_quality",),
        )
    if profile is None:
        return SpeakerDecision(
            attribution="declared_owner" if declared_owner_only else "uncertain",
            profile_id=None,
            score=None,
            threshold=None,
            quality_ok=True,
            reasons=(
                "owner_only_session_without_verifier"
                if declared_owner_only
                else "no_speaker_profile"
            ,),
        )
    if score is None:
        return SpeakerDecision(
            attribution="uncertain",
            profile_id=profile.profile_id,
            score=None,
            threshold=profile.threshold,
            quality_ok=True,
            reasons=("verifier_score_missing",),
        )

    normalized_score = _bounded(score, field_name="score")
    if normalized_score >= profile.threshold:
        return SpeakerDecision(
            attribution="verified_owner",
            profile_id=profile.profile_id,
            score=normalized_score,
            threshold=profile.threshold,
            quality_ok=True,
            reasons=("score_above_owner_threshold",),
        )

    rejection_threshold = profile.threshold - profile.rejection_margin
    if normalized_score <= rejection_threshold:
        return SpeakerDecision(
            attribution="non_owner",
            profile_id=profile.profile_id,
            score=normalized_score,
            threshold=profile.threshold,
            quality_ok=True,
            reasons=("score_below_rejection_threshold",),
        )

    return SpeakerDecision(
        attribution="uncertain",
        profile_id=profile.profile_id,
        score=normalized_score,
        threshold=profile.threshold,
        quality_ok=True,
        reasons=("score_in_uncertainty_band",),
    )
