"""Voice-session lifecycle API for the FVSC pilot.

This router intentionally exposes only deterministic session control at R0.  It
does not claim that microphone capture, ASR, speaker verification or real-time
chat are available yet.  Those capabilities plug into the same state machine in
later slices without changing evidence-promotion rules.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Literal
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from core.voice_session import VoiceSessionConfig, VoiceSessionManager


router = APIRouter(prefix="/pilot/voice", tags=["pilot-voice"])
_manager = VoiceSessionManager()
_lock = asyncio.Lock()


class StartVoiceSessionRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex, min_length=1, max_length=128)
    mode: Literal["voice_memo", "antourage_dialogue"]
    declared_owner_only: bool = True
    evidence_mode: Literal["conversation_only", "save_owner_turns_for_review"] = "conversation_only"
    retention_class: Literal["ephemeral", "24h", "7d", "keep"] = "24h"
    tts_enabled: bool = False


class StopVoiceSessionRequest(BaseModel):
    reason: str = Field(default="user_stop", min_length=1, max_length=128)


def _session_payload(session) -> dict:
    if session is None:
        return None
    return asdict(session)


def _capabilities() -> dict[str, bool]:
    return {
        "session_lifecycle": True,
        "audio_import": False,
        "microphone_capture": False,
        "local_asr": False,
        "speaker_verification": False,
        "realtime_dialogue": False,
        "local_tts": False,
    }


@router.get("/status")
async def voice_status():
    return {
        "runtime_version": "voice-r0",
        "active_session": _session_payload(_manager.active),
        "session_count": len(_manager.list_sessions()),
        "capabilities": _capabilities(),
        "warning": (
            "R0 lifecycle only: microphone capture, transcription, speaker "
            "verification and real-time Antourage transport are not connected yet."
        ),
    }


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def start_voice_session(req: StartVoiceSessionRequest):
    config = VoiceSessionConfig(
        mode=req.mode,
        declared_owner_only=req.declared_owner_only,
        evidence_mode=req.evidence_mode,
        retention_class=req.retention_class,
        tts_enabled=req.tts_enabled,
    )
    async with _lock:
        try:
            session = _manager.start(request_id=req.request_id, config=config)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "session": _session_payload(session),
        "capabilities": _capabilities(),
    }


@router.get("/sessions/{session_id}")
async def get_voice_session(session_id: str):
    session = _manager.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="voice session not found")
    return {"session": _session_payload(session)}


@router.post("/sessions/{session_id}/stop")
async def stop_voice_session(session_id: str, req: StopVoiceSessionRequest):
    async with _lock:
        try:
            session = _manager.stop(session_id, reason=req.reason)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="voice session not found") from exc
    return {"session": _session_payload(session)}


@router.post("/emergency-stop")
async def emergency_stop_voice():
    async with _lock:
        session = _manager.emergency_stop()
    return {
        "stopped": session is not None,
        "session": _session_payload(session),
    }
