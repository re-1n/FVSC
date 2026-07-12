"""Local R1 voice ingest, review and explicit evidence-promotion API."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
import time
from typing import Any, Literal
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from core.voice_artifacts import VoiceEvidenceCandidate, decide_promotion
from core.voice_ingest import ASRBackend, MAX_AUDIO_BYTES, VoiceIngestError
from core.voice_r1_repository import R1VoiceRepository
from core.voice_session import VoiceSessionConfig, VoiceSessionManager

from . import pilot_router as pilot_router_module


router = APIRouter(prefix="/pilot/voice", tags=["pilot-voice"])
_manager = VoiceSessionManager()
_repository: R1VoiceRepository | None = None
_repository_vault: Path | None = None
_repository_root: Path | None = None
_repository_asr: ASRBackend | None = None
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


class CorrectVoiceCandidateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)


class PromoteVoiceCandidateRequest(BaseModel):
    automatic_promotion_enabled: bool = False


class RetractVoiceCandidateRequest(BaseModel):
    reason: str = Field(default="user_retracted_voice_evidence", min_length=1, max_length=256)


def configure_voice_repository(
    *, root: Path | str | None = None, asr_backend: ASRBackend | None = None,
) -> None:
    global _repository, _repository_vault, _repository_root, _repository_asr
    _repository = None
    _repository_vault = None
    _repository_root = Path(root).resolve() if root is not None else None
    _repository_asr = asr_backend


def _voice_repository() -> R1VoiceRepository:
    global _repository, _repository_vault
    vault = pilot_router_module._vault_path()
    if _repository is None or _repository_vault != vault:
        _repository = R1VoiceRepository(
            _repository_root, vault_path=vault, asr_backend=_repository_asr,
        )
        _repository_vault = vault
    return _repository


def _session_payload(session) -> dict[str, Any] | None:
    return None if session is None else asdict(session)


def _capabilities(repository: R1VoiceRepository) -> dict[str, bool]:
    return {
        "session_lifecycle": True,
        "audio_import": True,
        "microphone_capture": False,
        "voice_memo_upload": True,
        "local_asr": repository.asr_available,
        "speaker_verification": False,
        "realtime_dialogue": False,
        "local_tts": False,
        "transcript_review": True,
        "explicit_evidence_promotion": True,
        "retention_enforcement": True,
    }


def _raise_ingest_error(exc: VoiceIngestError) -> None:
    message = str(exc)
    lowered = message.casefold()
    if "exceeds" in lowered:
        code = 413
    elif "extension" in lowered or "decoder" in lowered or "wav" in lowered:
        code = 415
    elif "not installed" in lowered:
        code = 503
    else:
        code = 422
    raise HTTPException(status_code=code, detail=message) from exc


def _resolve_memo_session(session_id: str | None, mode: str):
    session = _manager.get(session_id) if session_id else None
    if session is None and session_id is None and mode == "voice_memo":
        active = _manager.active
        if active is not None and active.config.mode == "voice_memo" and not active.terminal:
            session = active
    if session_id is not None and session is None:
        raise HTTPException(status_code=404, detail="voice session not found")
    if session is not None:
        if session.terminal:
            raise HTTPException(status_code=409, detail="voice session is already terminal")
        if session.config.mode != "voice_memo" or mode != "voice_memo":
            raise HTTPException(status_code=409, detail="session is not a voice-memo session")
    return session


@router.get("/status")
async def voice_status():
    repository = _voice_repository()
    warning = None if repository.asr_available else (
        "Audio import and WAV capture are available, but local ASR is not installed. "
        "Install requirements-voice.txt before expecting automatic transcripts."
    )
    return {
        "runtime_version": "voice-r1",
        "active_session": _session_payload(_manager.active),
        "session_count": len(_manager.list_sessions()),
        "capabilities": _capabilities(repository),
        "repository": repository.status(),
        "warning": warning,
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
    return {"session": _session_payload(session), "capabilities": _capabilities(_voice_repository())}


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
    return {"stopped": session is not None, "session": _session_payload(session)}


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_voice_audio(
    request: Request,
    mode: Literal["file_import", "voice_memo"] = "file_import",
    declared_owner_only: bool = True,
    evidence_mode: Literal["conversation_only", "save_owner_turns_for_review"] = "save_owner_turns_for_review",
    retention_class: Literal["ephemeral", "24h", "7d", "keep"] = "24h",
    language: str | None = None,
    session_id: str | None = None,
    observed_at: float | None = None,
):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_AUDIO_BYTES:
                raise HTTPException(status_code=413, detail="audio body exceeds R1 size limit")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid Content-Length") from exc

    session = _resolve_memo_session(session_id, mode)
    if session is not None:
        session_id = session.session_id
        declared_owner_only = session.config.declared_owner_only
        evidence_mode = session.config.evidence_mode
        retention_class = session.config.retention_class

    filename = request.headers.get("x-fvsc-filename", "").strip()
    body = await request.body()
    repository = _voice_repository()
    async with _lock:
        try:
            return await asyncio.to_thread(
                repository.import_audio,
                body,
                filename=filename,
                mode=mode,
                declared_owner_only=declared_owner_only,
                evidence_mode=evidence_mode,
                retention_class=retention_class,
                language=language,
                observed_at=observed_at,
                session_id=session_id,
            )
        except VoiceIngestError as exc:
            _raise_ingest_error(exc)


@router.get("/captures/{capture_id}")
async def get_voice_capture(capture_id: str):
    try:
        return _voice_repository().get_capture(capture_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/captures/{capture_id}/transcribe")
async def transcribe_voice_capture(capture_id: str, language: str | None = None):
    repository = _voice_repository()
    async with _lock:
        try:
            return await asyncio.to_thread(repository.transcribe_capture, capture_id, language=language)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except VoiceIngestError as exc:
            _raise_ingest_error(exc)


@router.get("/candidates")
async def list_voice_candidates(include_terminal: bool = False):
    repository = _voice_repository()
    return {
        "candidates": repository.list_candidates(include_terminal=include_terminal),
        "repository": repository.status(),
    }


@router.get("/candidates/{candidate_id}")
async def get_voice_candidate(candidate_id: str):
    try:
        return _voice_repository().candidate_payload(candidate_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/candidates/{candidate_id}/correct")
async def correct_voice_candidate(candidate_id: str, req: CorrectVoiceCandidateRequest):
    repository = _voice_repository()
    async with _lock:
        try:
            current = repository.candidate_payload(candidate_id)
            if current["candidate"]["promotion_state"] != "pending_review":
                raise HTTPException(status_code=409, detail="only pending candidates can be corrected")
            return repository.correct_candidate(candidate_id, req.text)
        except VoiceIngestError as exc:
            _raise_ingest_error(exc)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/candidates/{candidate_id}/discard")
async def discard_voice_candidate(candidate_id: str):
    repository = _voice_repository()
    async with _lock:
        try:
            current = repository.candidate_payload(candidate_id)
            if current["candidate"]["promotion_state"] != "pending_review":
                raise HTTPException(status_code=409, detail="promoted evidence must be retracted, not discarded")
            discarded = repository.discard_candidate(candidate_id)
            repository.enforce_retention()
            return discarded
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/candidates/{candidate_id}/promote")
async def promote_voice_candidate(candidate_id: str, req: PromoteVoiceCandidateRequest):
    repository = _voice_repository()
    async with _lock:
        try:
            current = repository.candidate_payload(candidate_id)
            if current["candidate"]["promotion_state"] != "pending_review":
                raise HTTPException(status_code=409, detail="candidate is not pending review")
            approved_payload = repository.approve_candidate(candidate_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        approved = VoiceEvidenceCandidate(**approved_payload["candidate"])
        decision = decide_promotion(approved, automatic_promotion_enabled=req.automatic_promotion_enabled)
        if not decision.permitted or decision.evidence_weight_multiplier <= 0.0:
            raise HTTPException(status_code=409, detail={"status": decision.status, "reasons": decision.reasons})

        transcript = approved_payload["transcript"]
        capture_record = approved_payload["capture"]
        capture = capture_record["artifact"]
        semantic_input = pilot_router_module._parse_text(transcript["text_normalized"])
        if not semantic_input:
            raise HTTPException(status_code=422, detail="reviewed transcript did not produce semantic relations")

        source_id = f"voice/{capture['capture_id']}/{transcript['transcript_id']}"
        provenance = {
            "source_type": "voice_transcript",
            "capture_id": capture["capture_id"],
            "transcript_id": transcript["transcript_id"],
            "candidate_id": approved.candidate_id,
            "session_id": capture_record.get("session_id"),
            "capture_mode": capture["mode"],
            "speaker_attribution": transcript["speaker_attribution"],
            "asr_backend": transcript["asr_backend"],
            "asr_model": transcript["model_id"],
            "corrected": transcript["corrected"],
            "audio_retention_class": capture["retention_class"],
        }
        context = {
            "voice_evidence": True,
            "speaker_confidence": transcript.get("speaker_confidence"),
            "transcript_confidence": transcript.get("confidence"),
            "promotion_status": decision.status,
            "promotion_reasons": list(decision.reasons),
        }
        async with pilot_router_module._lock:
            runtime, feedback, vault = pilot_router_module._ensure_loaded()
            update = runtime.replace_source(
                source_id=source_id,
                semantic_input=semantic_input,
                source_revision=transcript["transcript_id"],
                observed_at=float(capture["started_at"]),
                extractor="fvsc-reviewed-voice-transcript",
                extractor_version="voice-r1",
                event_context=context,
                event_provenance=provenance,
                confidence_multiplier=decision.evidence_weight_multiplier,
            )
            pilot_router_module._save(runtime, feedback, vault)

        promoted = repository.mark_promoted(approved.candidate_id, source_id=source_id)
        retention_deleted = repository.enforce_retention()
        return {
            "candidate": promoted,
            "decision": asdict(decision),
            "source_update": asdict(update),
            "snapshot_id": update.snapshot_id,
            "retention_deleted_capture_ids": retention_deleted,
        }


@router.post("/candidates/{candidate_id}/retract")
async def retract_voice_candidate(candidate_id: str, req: RetractVoiceCandidateRequest):
    repository = _voice_repository()
    async with _lock:
        try:
            payload = repository.candidate_payload(candidate_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        source_id = payload.get("source_id")
        if not source_id or payload["candidate"]["promotion_state"] != "promoted":
            raise HTTPException(status_code=409, detail="candidate has no promoted evidence")
        async with pilot_router_module._lock:
            runtime, feedback, vault = pilot_router_module._ensure_loaded()
            update = runtime.delete_source(source_id=source_id, observed_at=time.time())
            pilot_router_module._save(runtime, feedback, vault)
        discarded = repository.discard_candidate(candidate_id)
        repository.enforce_retention()
        return {"candidate": discarded, "source_update": asdict(update), "reason": req.reason}


@router.delete("/captures/{capture_id}/audio")
async def delete_voice_audio(capture_id: str):
    repository = _voice_repository()
    async with _lock:
        try:
            return repository.delete_audio(capture_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except VoiceIngestError as exc:
            _raise_ingest_error(exc)
