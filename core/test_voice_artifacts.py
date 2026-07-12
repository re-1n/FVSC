from __future__ import annotations

import hashlib

import pytest

from core.voice_artifacts import (
    AudioCaptureArtifact,
    TranscriptArtifact,
    VoiceEvidenceCandidate,
    decide_promotion,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_audio_capture_is_content_addressed() -> None:
    first = AudioCaptureArtifact.create(
        mode="voice_memo",
        started_at=10.0,
        ended_at=12.5,
        sample_rate=16000,
        channels=1,
        source_hash=_sha("audio"),
        declared_owner_only=True,
        evidence_mode="save_owner_turns_for_review",
        metadata={"device": "default"},
    )
    second = AudioCaptureArtifact.create(
        mode="voice_memo",
        started_at=10.0,
        ended_at=12.5,
        sample_rate=16000,
        channels=1,
        source_hash=_sha("audio"),
        declared_owner_only=True,
        evidence_mode="save_owner_turns_for_review",
        metadata={"device": "default"},
    )
    assert first == second
    assert first.capture_id == second.capture_id


def test_transcript_revision_changes_identity_without_changing_capture() -> None:
    capture = AudioCaptureArtifact.create(
        mode="file_import",
        started_at=0.0,
        ended_at=5.0,
        sample_rate=16000,
        channels=1,
        source_hash=_sha("source"),
    )
    raw = TranscriptArtifact.create(
        capture_id=capture.capture_id,
        utterance_id="u1",
        start_seconds=0.2,
        end_seconds=2.0,
        text_raw="я думаю о карте",
        text_normalized="Я думаю о карте.",
        asr_backend="fake",
        model_id="fake-v1",
        speaker_attribution="declared_owner",
        confidence=0.9,
    )
    corrected = TranscriptArtifact.create(
        capture_id=capture.capture_id,
        utterance_id="u1",
        start_seconds=0.2,
        end_seconds=2.0,
        text_raw="я думаю о карте",
        text_normalized="Я думаю о смысловой карте.",
        asr_backend="fake",
        model_id="fake-v1",
        speaker_attribution="declared_owner",
        confidence=0.9,
        corrected=True,
    )
    assert raw.capture_id == corrected.capture_id
    assert raw.transcript_id != corrected.transcript_id


def test_conversation_only_turn_is_never_promotable() -> None:
    candidate = VoiceEvidenceCandidate.create(
        transcript_id=_sha("transcript"),
        capture_mode="antourage_dialogue",
        evidence_mode="conversation_only",
        speaker_attribution="verified_owner",
        transcript_confidence=0.99,
        speaker_confidence=0.99,
        reviewed_by_user=True,
        explicit_user_approval=True,
    )
    decision = decide_promotion(candidate, automatic_promotion_enabled=True)
    assert decision.status == "prohibited"
    assert decision.evidence_weight_multiplier == 0.0
    assert "conversation_only_mode" in decision.reasons


def test_known_non_owner_is_never_promotable() -> None:
    candidate = VoiceEvidenceCandidate.create(
        transcript_id=_sha("transcript"),
        capture_mode="voice_memo",
        evidence_mode="save_owner_turns_for_review",
        speaker_attribution="non_owner",
        transcript_confidence=0.99,
        speaker_confidence=0.99,
        reviewed_by_user=True,
        explicit_user_approval=True,
    )
    decision = decide_promotion(candidate, automatic_promotion_enabled=True)
    assert decision.status == "prohibited"
    assert decision.reasons == ("known_non_owner",)


def test_declared_owner_requires_manual_review() -> None:
    pending = VoiceEvidenceCandidate.create(
        transcript_id=_sha("transcript"),
        capture_mode="voice_memo",
        evidence_mode="save_owner_turns_for_review",
        speaker_attribution="declared_owner",
        transcript_confidence=0.95,
        speaker_confidence=None,
    )
    assert decide_promotion(pending).status == "manual_review"
    assert decide_promotion(pending).evidence_weight_multiplier == 0.0

    approved = VoiceEvidenceCandidate.create(
        transcript_id=pending.transcript_id,
        capture_mode=pending.capture_mode,
        evidence_mode=pending.evidence_mode,
        speaker_attribution=pending.speaker_attribution,
        transcript_confidence=pending.transcript_confidence,
        speaker_confidence=pending.speaker_confidence,
        reviewed_by_user=True,
        explicit_user_approval=True,
    )
    decision = decide_promotion(approved)
    assert decision.status == "manual_review"
    assert decision.evidence_weight_multiplier > 0.0


def test_automatic_promotion_requires_verified_calibrated_owner() -> None:
    candidate = VoiceEvidenceCandidate.create(
        transcript_id=_sha("transcript"),
        capture_mode="voice_memo",
        evidence_mode="save_owner_turns_for_review",
        speaker_attribution="verified_owner",
        transcript_confidence=0.95,
        speaker_confidence=0.92,
        reviewed_by_user=True,
        explicit_user_approval=True,
    )
    assert decide_promotion(candidate).status == "manual_review"
    decision = decide_promotion(candidate, automatic_promotion_enabled=True)
    assert decision.status == "automatic"
    assert decision.evidence_weight_multiplier == pytest.approx(0.75)


def test_invalid_capture_time_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="ended_at"):
        AudioCaptureArtifact.create(
            mode="voice_memo",
            started_at=5.0,
            ended_at=4.0,
            sample_rate=16000,
            channels=1,
            source_hash=_sha("audio"),
        )
