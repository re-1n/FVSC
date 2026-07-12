from __future__ import annotations

import pytest

from core.voice_session import VoiceSessionConfig, VoiceSessionManager


class FakeClock:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def __call__(self) -> float:
        current = self.value
        self.value += 1.0
        return current


def test_start_is_idempotent_by_request_id() -> None:
    manager = VoiceSessionManager(clock=FakeClock())
    config = VoiceSessionConfig(mode="antourage_dialogue")
    first = manager.start(request_id="request-1", config=config)
    second = manager.start(request_id="request-1", config=config)
    assert first == second
    assert manager.active == first


def test_only_one_active_voice_session_is_allowed() -> None:
    manager = VoiceSessionManager(clock=FakeClock())
    manager.start(
        request_id="request-1",
        config=VoiceSessionConfig(mode="antourage_dialogue"),
    )
    with pytest.raises(RuntimeError, match="already active"):
        manager.start(
            request_id="request-2",
            config=VoiceSessionConfig(mode="voice_memo"),
        )


def test_half_duplex_dialogue_state_cycle() -> None:
    manager = VoiceSessionManager(clock=FakeClock())
    created = manager.start(
        request_id="dialogue-1",
        config=VoiceSessionConfig(mode="antourage_dialogue", tts_enabled=True),
    )
    listening = manager.transition(created.session_id, "listening")
    transcribing = manager.transition(
        created.session_id,
        "transcribing",
        active_utterance_id="utterance-1",
    )
    thinking = manager.transition(created.session_id, "thinking")
    speaking = manager.transition(created.session_id, "speaking")
    listening_again = manager.transition(created.session_id, "listening")

    assert listening.phase == "listening"
    assert transcribing.active_utterance_id == "utterance-1"
    assert thinking.phase == "thinking"
    assert speaking.phase == "speaking"
    assert listening_again.phase == "listening"
    assert listening_again.revision == 5


def test_invalid_transition_is_rejected() -> None:
    manager = VoiceSessionManager(clock=FakeClock())
    created = manager.start(
        request_id="dialogue-1",
        config=VoiceSessionConfig(mode="antourage_dialogue"),
    )
    with pytest.raises(ValueError, match="invalid voice transition"):
        manager.transition(created.session_id, "speaking")


def test_stop_and_emergency_stop_are_idempotent() -> None:
    manager = VoiceSessionManager(clock=FakeClock())
    created = manager.start(
        request_id="memo-1",
        config=VoiceSessionConfig(mode="voice_memo"),
    )
    manager.transition(created.session_id, "listening")
    stopped = manager.emergency_stop()
    assert stopped is not None
    assert stopped.phase == "stopped"
    assert stopped.stop_reason == "emergency_stop"
    assert manager.active is None
    assert manager.stop(created.session_id) == stopped
    assert manager.emergency_stop() is None


def test_voice_memo_defaults_to_review_mode() -> None:
    config = VoiceSessionConfig(mode="voice_memo")
    assert config.evidence_mode == "save_owner_turns_for_review"


def test_new_session_can_start_after_stop() -> None:
    manager = VoiceSessionManager(clock=FakeClock())
    first = manager.start(
        request_id="memo-1",
        config=VoiceSessionConfig(mode="voice_memo"),
    )
    manager.stop(first.session_id)
    second = manager.start(
        request_id="dialogue-2",
        config=VoiceSessionConfig(mode="antourage_dialogue"),
    )
    assert second.session_id != first.session_id
    assert manager.active == second
