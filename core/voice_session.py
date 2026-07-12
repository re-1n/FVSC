"""Deterministic lifecycle for explicit FVSC voice sessions.

The manager owns no microphone implementation and never touches the evidence
ledger.  Capture, ASR, speaker verification and chat transports plug into this
state machine later.  One active session is allowed at a time so emergency stop
has a single unambiguous target.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import time
from typing import Callable, Literal

from .voice_artifacts import EvidenceMode, RetentionClass


SessionMode = Literal["voice_memo", "antourage_dialogue"]
SessionPhase = Literal[
    "created",
    "listening",
    "transcribing",
    "thinking",
    "speaking",
    "stopped",
    "failed",
]

_SESSION_MODES = {"voice_memo", "antourage_dialogue"}
_TERMINAL_PHASES = {"stopped", "failed"}
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "created": {"listening", "stopped", "failed"},
    "listening": {"transcribing", "stopped", "failed"},
    "transcribing": {"listening", "thinking", "stopped", "failed"},
    "thinking": {"speaking", "listening", "stopped", "failed"},
    "speaking": {"listening", "stopped", "failed"},
    "stopped": set(),
    "failed": set(),
}


def _clean(value: str, *, field_name: str) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _session_id(request_id: str, started_at: float, mode: str) -> str:
    payload = json.dumps(
        {
            "namespace": "fvsc-voice-session-v1",
            "request_id": request_id,
            "started_at": float(started_at),
            "mode": mode,
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VoiceSessionConfig:
    mode: SessionMode
    declared_owner_only: bool = True
    evidence_mode: EvidenceMode = "conversation_only"
    retention_class: RetentionClass = "24h"
    tts_enabled: bool = False

    def __post_init__(self) -> None:
        if self.mode not in _SESSION_MODES:
            raise ValueError(f"unknown session mode: {self.mode}")
        if self.mode == "voice_memo" and self.evidence_mode == "conversation_only":
            object.__setattr__(self, "evidence_mode", "save_owner_turns_for_review")


@dataclass(frozen=True)
class VoiceSessionSnapshot:
    session_id: str
    request_id: str
    config: VoiceSessionConfig
    phase: SessionPhase
    started_at: float
    updated_at: float
    stopped_at: float | None = None
    active_utterance_id: str | None = None
    stop_reason: str | None = None
    error: str | None = None
    revision: int = 0

    @property
    def terminal(self) -> bool:
        return self.phase in _TERMINAL_PHASES


class VoiceSessionManager:
    """Single-active-session coordinator with idempotent start and stop."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._clock = clock
        self._sessions: dict[str, VoiceSessionSnapshot] = {}
        self._request_index: dict[str, str] = {}
        self._active_session_id: str | None = None

    @property
    def active(self) -> VoiceSessionSnapshot | None:
        if self._active_session_id is None:
            return None
        return self._sessions[self._active_session_id]

    def get(self, session_id: str) -> VoiceSessionSnapshot | None:
        return self._sessions.get(str(session_id).strip())

    def list_sessions(self) -> tuple[VoiceSessionSnapshot, ...]:
        return tuple(
            sorted(
                self._sessions.values(),
                key=lambda session: (session.started_at, session.session_id),
            )
        )

    def start(
        self,
        *,
        request_id: str,
        config: VoiceSessionConfig,
    ) -> VoiceSessionSnapshot:
        request = _clean(request_id, field_name="request_id")
        existing_id = self._request_index.get(request)
        if existing_id is not None:
            return self._sessions[existing_id]
        if self.active is not None and not self.active.terminal:
            raise RuntimeError("another voice session is already active")

        now = float(self._clock())
        session = VoiceSessionSnapshot(
            session_id=_session_id(request, now, config.mode),
            request_id=request,
            config=config,
            phase="created",
            started_at=now,
            updated_at=now,
        )
        self._sessions[session.session_id] = session
        self._request_index[request] = session.session_id
        self._active_session_id = session.session_id
        return session

    def transition(
        self,
        session_id: str,
        phase: SessionPhase,
        *,
        active_utterance_id: str | None = None,
        error: str | None = None,
    ) -> VoiceSessionSnapshot:
        session = self._require(session_id)
        if session.phase == phase:
            return session
        if phase not in _ALLOWED_TRANSITIONS.get(session.phase, set()):
            raise ValueError(f"invalid voice transition: {session.phase} -> {phase}")

        now = float(self._clock())
        terminal = phase in _TERMINAL_PHASES
        updated = replace(
            session,
            phase=phase,
            updated_at=now,
            stopped_at=now if terminal else None,
            active_utterance_id=(
                None if terminal else self._clean_optional(active_utterance_id)
            ),
            error=self._clean_optional(error),
            revision=session.revision + 1,
        )
        self._sessions[session.session_id] = updated
        if terminal and self._active_session_id == session.session_id:
            self._active_session_id = None
        return updated

    def stop(
        self,
        session_id: str,
        *,
        reason: str = "user_stop",
    ) -> VoiceSessionSnapshot:
        session = self._require(session_id)
        if session.terminal:
            return session
        now = float(self._clock())
        updated = replace(
            session,
            phase="stopped",
            updated_at=now,
            stopped_at=now,
            active_utterance_id=None,
            stop_reason=_clean(reason, field_name="reason"),
            revision=session.revision + 1,
        )
        self._sessions[session.session_id] = updated
        if self._active_session_id == session.session_id:
            self._active_session_id = None
        return updated

    def fail(self, session_id: str, *, error: str) -> VoiceSessionSnapshot:
        session = self._require(session_id)
        if session.terminal:
            return session
        now = float(self._clock())
        updated = replace(
            session,
            phase="failed",
            updated_at=now,
            stopped_at=now,
            active_utterance_id=None,
            stop_reason="error",
            error=_clean(error, field_name="error"),
            revision=session.revision + 1,
        )
        self._sessions[session.session_id] = updated
        if self._active_session_id == session.session_id:
            self._active_session_id = None
        return updated

    def emergency_stop(self) -> VoiceSessionSnapshot | None:
        session = self.active
        if session is None:
            return None
        return self.stop(session.session_id, reason="emergency_stop")

    def _require(self, session_id: str) -> VoiceSessionSnapshot:
        cleaned = _clean(session_id, field_name="session_id")
        session = self._sessions.get(cleaned)
        if session is None:
            raise KeyError(f"unknown voice session: {cleaned}")
        return session

    @staticmethod
    def _clean_optional(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None
