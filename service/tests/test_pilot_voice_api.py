from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from core.voice_session import VoiceSessionManager
from service import pilot_router, pilot_voice_router, viz_router
from service.pilot_app import app


def _reset(vault: Path) -> None:
    viz_router.configure(vault_path=vault)
    pilot_router._runtime = None
    pilot_router._feedback = []
    pilot_router._loaded_vault = None
    pilot_voice_router._manager = VoiceSessionManager()


def test_voice_lifecycle_is_idempotent_and_does_not_mutate_semantic_state(tmp_path: Path) -> None:
    _reset(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        before = client.get("/pilot/status")
        assert before.status_code == 200
        before_snapshot = before.json()["snapshot_id"]

        status = client.get("/pilot/voice/status")
        assert status.status_code == 200
        assert status.json()["capabilities"]["session_lifecycle"] is True
        assert status.json()["capabilities"]["microphone_capture"] is False
        assert status.json()["active_session"] is None

        request = {
            "request_id": "voice-test-1",
            "mode": "antourage_dialogue",
            "declared_owner_only": True,
            "evidence_mode": "conversation_only",
            "retention_class": "ephemeral",
            "tts_enabled": False,
        }
        started = client.post("/pilot/voice/sessions", json=request)
        assert started.status_code == 201, started.text
        session = started.json()["session"]
        assert session["phase"] == "created"
        assert session["config"]["evidence_mode"] == "conversation_only"

        duplicate = client.post("/pilot/voice/sessions", json=request)
        assert duplicate.status_code == 201
        assert duplicate.json()["session"]["session_id"] == session["session_id"]

        conflict = client.post(
            "/pilot/voice/sessions",
            json={**request, "request_id": "voice-test-2"},
        )
        assert conflict.status_code == 409

        fetched = client.get(f"/pilot/voice/sessions/{session['session_id']}")
        assert fetched.status_code == 200
        assert fetched.json()["session"]["request_id"] == "voice-test-1"

        stopped = client.post(
            f"/pilot/voice/sessions/{session['session_id']}/stop",
            json={"reason": "test_complete"},
        )
        assert stopped.status_code == 200
        assert stopped.json()["session"]["phase"] == "stopped"
        assert stopped.json()["session"]["stop_reason"] == "test_complete"

        stopped_again = client.post(
            f"/pilot/voice/sessions/{session['session_id']}/stop",
            json={"reason": "ignored_second_stop"},
        )
        assert stopped_again.status_code == 200
        assert stopped_again.json()["session"] == stopped.json()["session"]

        after = client.get("/pilot/status")
        assert after.status_code == 200
        assert after.json()["snapshot_id"] == before_snapshot


def test_emergency_stop_closes_active_session(tmp_path: Path) -> None:
    _reset(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        started = client.post(
            "/pilot/voice/sessions",
            json={
                "request_id": "memo-test",
                "mode": "voice_memo",
                "declared_owner_only": True,
            },
        )
        assert started.status_code == 201
        session = started.json()["session"]
        assert session["config"]["evidence_mode"] == "save_owner_turns_for_review"

        emergency = client.post("/pilot/voice/emergency-stop")
        assert emergency.status_code == 200
        assert emergency.json()["stopped"] is True
        assert emergency.json()["session"]["stop_reason"] == "emergency_stop"

        second = client.post("/pilot/voice/emergency-stop")
        assert second.status_code == 200
        assert second.json() == {"stopped": False, "session": None}
