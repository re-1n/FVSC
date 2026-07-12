from __future__ import annotations

from io import BytesIO
from pathlib import Path
import wave

import numpy as np
from fastapi.testclient import TestClient

from core.voice_ingest import ASRResult
from service import pilot_router, pilot_voice_router, viz_router
from service.pilot_app import app


class FakeASR:
    backend_id = "fake-local-asr-v1"
    model_id = "fixture-ru-v1"
    available = True

    def transcribe(self, path: Path, *, language: str | None, regions):
        return [
            ASRResult(
                start_seconds=regions[0].start_seconds,
                end_seconds=regions[-1].end_seconds,
                text="Свобода включает выбор и ответственность. Ответственность требует честности.",
                confidence=0.95,
                language=language or "ru",
            )
        ]


def _wav_fixture() -> bytes:
    sample_rate = 16_000
    silence = np.zeros(sample_rate // 3, dtype=np.float32)
    t = np.arange(sample_rate, dtype=np.float32) / sample_rate
    signal = 0.3 * np.sin(2.0 * np.pi * 180.0 * t)
    pcm = np.clip(np.concatenate([silence, signal, silence]) * 32767, -32768, 32767).astype("<i2")
    buffer = BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


def _reset(vault: Path, voice_root: Path) -> None:
    viz_router.configure(vault_path=vault)
    pilot_router._runtime = None
    pilot_router._feedback = []
    pilot_router._loaded_vault = None
    pilot_voice_router.configure_voice_repository(root=voice_root, asr_backend=FakeASR())


def test_voice_import_review_promotion_provenance_and_retraction(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    voice_root = tmp_path / "voice"
    vault.mkdir()
    _reset(vault, voice_root)

    with TestClient(app, base_url="http://127.0.0.1") as client:
        before = client.get("/pilot/status")
        assert before.status_code == 200
        initial_snapshot = before.json()["snapshot_id"]

        imported = client.post(
            "/pilot/voice/import?mode=voice_memo&language=ru",
            content=_wav_fixture(),
            headers={
                "x-fvsc-filename": "owner-memo.wav",
                "content-type": "audio/wav",
            },
        )
        assert imported.status_code == 201, imported.text
        imported_data = imported.json()
        assert imported_data["capture"]["status"] == "ready"
        candidate_id = imported_data["candidates"][0]["candidate"]["candidate_id"]

        corrected = client.post(
            f"/pilot/voice/candidates/{candidate_id}/correct",
            json={
                "text": "Свобода включает осознанный выбор и ответственность. "
                "Ответственность требует честности и внимания."
            },
        )
        assert corrected.status_code == 200, corrected.text
        candidate_id = corrected.json()["candidate"]["candidate_id"]

        promoted = client.post(
            f"/pilot/voice/candidates/{candidate_id}/promote",
            json={"automatic_promotion_enabled": False},
        )
        assert promoted.status_code == 200, promoted.text
        promoted_data = promoted.json()
        assert promoted_data["source_update"]["asserted_events"] > 0
        assert promoted_data["snapshot_id"] != initial_snapshot
        promoted_candidate_id = promoted_data["candidate"]["candidate"]["candidate_id"]

        runtime = pilot_router._runtime
        assert runtime is not None
        voice_events = [
            event for event in runtime.ledger.active_events
            if event.extractor == "fvsc-reviewed-voice-transcript"
        ]
        assert voice_events
        provenance = voice_events[0].provenance
        assert provenance["source_type"] == "voice_transcript"
        assert provenance["capture_id"]
        assert provenance["transcript_id"]
        assert provenance["speaker_attribution"] == "declared_owner"

        retracted = client.post(
            f"/pilot/voice/candidates/{promoted_candidate_id}/retract",
            json={"reason": "fixture cleanup"},
        )
        assert retracted.status_code == 200, retracted.text
        assert retracted.json()["source_update"]["retracted_events"] > 0
        assert not [
            event for event in runtime.ledger.active_events
            if event.extractor == "fvsc-reviewed-voice-transcript"
        ]

        status = client.get("/pilot/voice/status")
        assert status.status_code == 200
        assert status.json()["capabilities"]["audio_import"] is True
        assert status.json()["capabilities"]["local_asr"] is True
