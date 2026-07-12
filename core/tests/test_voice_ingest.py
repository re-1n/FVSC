from __future__ import annotations

from io import BytesIO
from pathlib import Path
import wave

import numpy as np

from core.voice_ingest import ASRResult
from core.voice_r1_repository import R1VoiceRepository


class FakeASR:
    backend_id = "fake-local-asr-v1"
    model_id = "fixture-ru-v1"
    available = True

    def transcribe(self, path: Path, *, language: str | None, regions):
        assert path.exists()
        assert regions
        return [
            ASRResult(
                start_seconds=regions[0].start_seconds,
                end_seconds=regions[-1].end_seconds,
                text="Свобода включает выбор и ответственность.",
                confidence=0.93,
                language=language or "ru",
            )
        ]


def _wav_fixture() -> bytes:
    sample_rate = 16_000
    silence = np.zeros(sample_rate // 2, dtype=np.float32)
    t = np.arange(sample_rate, dtype=np.float32) / sample_rate
    voiced = 0.25 * np.sin(2.0 * np.pi * 220.0 * t)
    samples = np.concatenate([silence, voiced, silence])
    pcm = np.clip(samples * 32767.0, -32768, 32767).astype("<i2")
    buffer = BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


def test_voice_repository_import_correct_restart_and_delete_audio(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    root = tmp_path / "voice-data"
    vault.mkdir()
    repository = R1VoiceRepository(root, vault_path=vault, asr_backend=FakeASR())

    imported = repository.import_audio(
        _wav_fixture(),
        filename="memo.wav",
        mode="voice_memo",
        declared_owner_only=True,
        evidence_mode="save_owner_turns_for_review",
        language="ru",
        observed_at=100.0,
        session_id="explicit-owner-session",
    )
    capture = imported["capture"]
    assert capture["status"] == "ready"
    assert capture["session_id"] == "explicit-owner-session"
    assert capture["artifact"]["metadata_json"]
    assert len(imported["candidates"]) == 1
    candidate = imported["candidates"][0]
    assert candidate["transcript"]["speaker_attribution"] == "declared_owner"
    assert candidate["transcript"]["text_normalized"].startswith("Свобода")

    original_id = candidate["candidate"]["candidate_id"]
    corrected = repository.correct_candidate(
        original_id,
        "Свобода включает осознанный выбор и ответственность.",
    )
    corrected_id = corrected["candidate"]["candidate_id"]
    assert corrected_id != original_id
    assert corrected["transcript"]["corrected"] is True
    assert "осознанный" in corrected["transcript"]["text_normalized"]
    assert repository.candidate_payload(original_id)["superseded_by"] == corrected_id

    restored = R1VoiceRepository(root, vault_path=vault, asr_backend=FakeASR())
    pending = restored.list_candidates()
    assert [item["candidate"]["candidate_id"] for item in pending] == [corrected_id]

    capture_id = capture["artifact"]["capture_id"]
    storage_ref = capture["artifact"]["storage_ref"]
    immutable_artifact = dict(capture["artifact"])
    assert (root / storage_ref).exists()
    deleted = restored.delete_audio(capture_id)
    assert deleted["audio_deleted_at"] is not None
    assert deleted["audio_present"] is False
    assert deleted["artifact"] == immutable_artifact
    assert not (root / storage_ref).exists()
    # Transcript/candidate history survives raw-audio deletion.
    assert restored.candidate_payload(corrected_id)["transcript"]["text_normalized"]


def test_ephemeral_audio_waits_for_review_then_is_deleted(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    root = tmp_path / "voice-data"
    vault.mkdir()
    repository = R1VoiceRepository(root, vault_path=vault, asr_backend=FakeASR())
    imported = repository.import_audio(
        _wav_fixture(),
        filename="ephemeral.wav",
        mode="voice_memo",
        retention_class="ephemeral",
        evidence_mode="save_owner_turns_for_review",
        observed_at=200.0,
    )
    capture_id = imported["capture"]["artifact"]["capture_id"]
    storage_ref = imported["capture"]["artifact"]["storage_ref"]
    candidate_id = imported["candidates"][0]["candidate"]["candidate_id"]
    assert repository.enforce_retention(now=10_000.0) == []
    assert (root / storage_ref).exists()

    repository.discard_candidate(candidate_id)
    assert repository.enforce_retention(now=10_001.0) == [capture_id]
    assert not (root / storage_ref).exists()
