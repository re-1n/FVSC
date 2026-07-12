from __future__ import annotations

from core.speaker_verification import SpeakerProfile, decide_speaker


def _profile() -> SpeakerProfile:
    return SpeakerProfile.create(
        label="owner",
        verifier_backend="fake-verifier",
        model_id="fake-v1",
        embedding_revision="sha256:owner-profile",
        created_at=100.0,
        sample_count=3,
        threshold=0.80,
        rejection_margin=0.15,
    )


def test_declared_owner_without_profile_remains_declaration_only() -> None:
    decision = decide_speaker(
        declared_owner_only=True,
        profile=None,
        score=None,
        quality_ok=True,
    )
    assert decision.attribution == "declared_owner"
    assert decision.profile_id is None


def test_verified_owner_requires_threshold_match() -> None:
    profile = _profile()
    decision = decide_speaker(
        declared_owner_only=True,
        profile=profile,
        score=0.91,
        quality_ok=True,
    )
    assert decision.attribution == "verified_owner"
    assert decision.profile_id == profile.profile_id


def test_declaration_does_not_override_verifier_rejection() -> None:
    profile = _profile()
    decision = decide_speaker(
        declared_owner_only=True,
        profile=profile,
        score=0.50,
        quality_ok=True,
    )
    assert decision.attribution == "non_owner"


def test_uncertainty_band_does_not_become_declared_owner() -> None:
    profile = _profile()
    decision = decide_speaker(
        declared_owner_only=True,
        profile=profile,
        score=0.72,
        quality_ok=True,
    )
    assert decision.attribution == "uncertain"


def test_overlap_and_low_quality_are_hard_gates() -> None:
    profile = _profile()
    overlap = decide_speaker(
        declared_owner_only=True,
        profile=profile,
        score=0.99,
        quality_ok=True,
        overlap=True,
    )
    assert overlap.attribution == "overlap"

    low_quality = decide_speaker(
        declared_owner_only=True,
        profile=profile,
        score=0.99,
        quality_ok=False,
    )
    assert low_quality.attribution == "uncertain"
    assert low_quality.quality_ok is False
