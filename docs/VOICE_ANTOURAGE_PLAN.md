# FVSC real-time voice Antourage plan

_Last updated: 2026-07-12_

## Product goal

Add a local-first voice interface that serves two related but distinct purposes:

1. **voice evidence acquisition** — import or explicitly record owner speech, review the transcript, and optionally promote it into the FVSC evidence ledger;
2. **real-time Antourage conversation** — speak to the existing semantic chat and hear its answer without requiring keyboard input.

These paths share capture, VAD, ASR, speaker attribution and provenance, but they must not share automatic promotion semantics.

## Critical distinction

```text
voice memo / explicit evidence session
  -> transcript candidate
  -> review or promotion policy
  -> EvidenceLedger

real-time Antourage dialogue
  -> conversational transcript
  -> /viz/ask-compatible dialogue turn
  -> assistant response
  -> optional local TTS
  -> no EvidenceLedger mutation by default
```

A live conversation may be saved as a candidate only after an explicit user action. Assistant speech is never treated as owner evidence.

## Ownership model

An explicit recording button does not mathematically guarantee speaker identity. The system must distinguish:

- `declared_owner` — the user started an owner-only session and declares that only they are speaking;
- `verified_owner` — a local speaker verifier also matched an enrolled owner profile above a calibrated threshold;
- `uncertain` — identity confidence is insufficient;
- `non_owner` — another enrolled or confidently separated speaker;
- `overlap` — more than one speaker is active.

Initial policy:

| Attribution | Conversation | Evidence candidate | Automatic promotion |
|---|---:|---:|---:|
| declared owner | allowed | allowed | disabled |
| verified owner | allowed | allowed | disabled until calibrated |
| uncertain | allowed as transcript | manual review only | prohibited |
| non-owner | optional transcript | prohibited as personal evidence | prohibited |
| overlap | transcript with warning | manual review only | prohibited |

Speaker verification is an additional safety signal, not an absolute guarantee and not an anti-spoofing system.

## User-facing modes

### 1. Import audio

The user selects an existing audio file. The system:

- hashes and stores or references the source;
- runs VAD and local transcription;
- shows raw and normalized text;
- allows correction, discard, audio deletion and explicit promotion.

### 2. Record voice memo

A visible button starts an explicit owner-only capture session. On stop:

- the session closes deterministically;
- remaining buffered speech is flushed;
- a transcript candidate is created;
- nothing enters the semantic map before confirmation.

### 3. Talk to Antourage

A microphone button starts a conversational session. The first production mode is half-duplex:

```text
listen -> detect end of user turn -> transcribe -> ask Antourage
       -> stream text response -> optional TTS -> listen again
```

The user can select:

- `conversation_only` — do not create evidence candidates;
- `save_my_turns_for_review` — owner turns enter the voice review queue;
- `record_session_audio` — retain source audio according to an explicit retention policy.

### 4. Full-duplex conversation

Deferred until half-duplex is stable. It adds:

- barge-in while Antourage is speaking;
- immediate cancellation of TTS and the current model response;
- acoustic echo handling;
- simultaneous VAD during playback;
- stricter latency and device tests.

## Runtime architecture

```text
Obsidian microphone
  -> AudioWorklet / PCM16 frames
  -> local WebSocket
  -> session state machine
  -> rolling buffer
  -> VAD
  -> utterance segment
  -> streaming/chunked ASR
  -> optional speaker verification
  -> final user transcript
       |-> conversation session -> semantic chat -> text stream -> TTS
       `-> optional VoiceEvidenceCandidate -> review -> EvidenceLedger
```

### Frontend capture

The Obsidian plugin owns microphone permission and capture controls. Recommended initial transport:

- `getUserMedia` with echo cancellation, noise suppression and automatic gain control requested from the host;
- `AudioWorklet` for mono PCM frames;
- 16 kHz or 48 kHz source with deterministic server-side resampling;
- binary WebSocket frames for audio;
- JSON control events for lifecycle and status.

A `ScriptProcessorNode` fallback may exist for compatibility but must be labelled transitional.

### Backend session state

```python
class VoiceDialogueSession:
    session_id: str
    mode: str
    state: str
    declared_owner_only: bool
    save_owner_turns_for_review: bool
    retain_audio: bool
    started_at: float
    active_utterance_id: str | None
    conversation_id: str
```

Allowed states:

```text
created -> listening -> transcribing -> thinking -> speaking -> listening
   |          |             |             |           |
   `----------+-------------+-------------+-----------+-> stopped
                                                        -> failed
```

All stop operations are idempotent. Emergency stop closes capture, discards uncommitted buffers, cancels ASR/LLM/TTS tasks and releases the microphone.

## WebSocket protocol

Proposed endpoint:

```text
WS /pilot/voice/realtime
```

Client control messages:

```json
{"type":"start","mode":"conversation_only","declared_owner_only":true}
{"type":"audio_format","sample_rate":48000,"channels":1,"encoding":"pcm_s16le"}
{"type":"stop_turn"}
{"type":"stop_session"}
{"type":"cancel_response"}
```

Binary messages contain PCM frames only after `audio_format` is accepted.

Server events:

```json
{"type":"session_started","session_id":"..."}
{"type":"vad_state","speaking":true}
{"type":"transcript_partial","utterance_id":"...","text":"..."}
{"type":"transcript_final","utterance_id":"...","text":"...","speaker":"declared_owner"}
{"type":"assistant_token","text":"..."}
{"type":"assistant_sentence","text":"..."}
{"type":"tts_chunk","format":"pcm_s16le","sample_rate":22050}
{"type":"turn_done"}
{"type":"error","code":"...","message":"..."}
```

The protocol must apply frame-size, duration, queue and message-rate limits.

## Antourage integration

The final transcript should enter the same semantic conversation path as the existing `/viz/ask` request. The chat implementation must be factored so REST/SSE and voice/WebSocket transports share:

- system prompt construction;
- semantic-map context selection;
- conversation history;
- concept markers and graph highlight events;
- cancellation semantics.

Do not call the HTTP `/viz/ask` endpoint from inside the backend. Extract a transport-independent chat generator and invoke it from both routers.

### Response speech

TTS is an adapter, not a prerequisite for voice input:

```python
class SpeechSynthesisBackend(Protocol):
    backend_id: str
    voice_id: str

    def synthesize(self, text: str) -> Iterable[AudioChunk]: ...
```

Initial rollout:

1. microphone input plus streamed text answer;
2. optional local TTS after complete sentences;
3. cancellation between sentences;
4. full barge-in after echo tests.

No cloud TTS is enabled by default.

## Owner speaker enrollment

Enrollment is explicit and local. Suggested flow:

1. record at least three prompted phrases in a quiet environment;
2. reject clipped, silent or too-short samples;
3. store derived speaker embeddings and model/version metadata, not raw enrollment audio by default;
4. calibrate an initial threshold from within-owner sample variation;
5. collect labelled owner/non-owner pilot samples before allowing automatic promotion.

Required records:

```python
class SpeakerProfile:
    profile_id: str
    label: str
    verifier_backend: str
    model_id: str
    embedding_revision: str
    created_at: float
    sample_count: int
    threshold: float
```

Verification result:

```python
class SpeakerDecision:
    attribution: str
    profile_id: str | None
    score: float | None
    threshold: float | None
    quality_ok: bool
    reasons: tuple[str, ...]
```

Unknown, low-quality and overlapping speech must never be converted into `verified_owner` merely because the session was declared owner-only.

## Persistence and provenance

Conversation and evidence storage are separated:

```text
<FVSC app data>/voice/
  captures/
  utterances/
  transcripts/
  speaker_profiles/
  conversations/
```

A promoted evidence event references:

- dialogue/session ID;
- utterance and transcript IDs;
- source time range;
- capture mode;
- declared-owner flag;
- speaker decision and verifier version;
- ASR model/version and confidence;
- whether the text was corrected before promotion.

Assistant output remains conversation history and is excluded from owner evidence.

## Service endpoints

REST lifecycle and review:

```text
GET    /pilot/voice/status
POST   /pilot/voice/import
POST   /pilot/voice/sessions
POST   /pilot/voice/sessions/{id}/stop
POST   /pilot/voice/emergency-stop
POST   /pilot/voice/enrollment
GET    /pilot/voice/speaker-profiles
GET    /pilot/voice/candidates
POST   /pilot/voice/candidates/{id}/promote
POST   /pilot/voice/candidates/{id}/correct
POST   /pilot/voice/candidates/{id}/discard
```

Real-time transport:

```text
WS     /pilot/voice/realtime
```

## Obsidian controls

Antourage toolbar:

- microphone toggle: `Talk to Antourage`;
- recording-state indicator visible while any capture is active;
- mode selector: conversation only / save my turns for review;
- stop and emergency-stop controls;
- transcript partial/final status;
- speaker attribution badge;
- TTS mute toggle.

Commands:

```text
FVSC Antourage: Voice: import audio file
FVSC Antourage: Voice: record voice memo
FVSC Antourage: Voice: talk to Antourage
FVSC Antourage: Voice: stop current voice session
FVSC Antourage: Voice: emergency stop
FVSC Antourage: Voice: enroll owner voice
FVSC Antourage: Voice: open transcript review queue
```

## Delivery order

### R0 — contracts and deterministic session lifecycle

- immutable voice artifacts;
- speaker-attribution enum and promotion policy;
- explicit session state machine;
- idempotent stop/emergency stop;
- fake capture, ASR, verifier and TTS backends for tests.

Gate: lifecycle and promotion-policy tests are deterministic and no session mutates the evidence ledger implicitly.

### R1 — audio import and voice memo button

- bounded local file upload;
- WAV baseline and replaceable decoder;
- VAD and local ASR adapter;
- transcript review queue;
- Obsidian import and record controls;
- explicit evidence promotion.

Gate: ten real owner recordings survive restart, correction, promotion and raw-audio deletion without provenance loss.

### R2 — half-duplex Antourage voice

- WebSocket audio transport;
- VAD turn completion;
- partial and final transcripts;
- shared chat generator with `/viz/ask`;
- streamed text answer;
- cancellation and emergency stop.

Gate: twenty five-turn sessions complete without duplicated/lost turns; median end-of-speech to first answer token is measured and no conversation mutates the ledger in `conversation_only` mode.

### R3 — owner speaker verification

- local enrollment;
- speaker-verifier adapter;
- quality and overlap gates;
- calibrated threshold;
- owner/unknown/non-owner evaluation set.

Gate: zero known non-owner utterances are promoted in the labelled pilot set. Automatic promotion remains disabled unless this gate passes with enough negative examples.

### R4 — local TTS and barge-in

- sentence-level local TTS;
- streamed playback;
- cancellation;
- initially pause capture during TTS;
- later echo-aware full-duplex and barge-in.

Gate: user interruption stops audible output and generation promptly; echo does not create false user turns in the test environment.

### R5 — semantic value experiment

Compare:

1. text-only daily pilot;
2. text plus reviewed voice memos;
3. text plus reviewed Antourage user turns;
4. verified-owner automatic candidates, only if R3 passed.

Measure coverage gain, review burden, correction rate, contamination, daily-review usefulness and held-out performance against graph and mass baselines.

## Stop conditions

Stop voice collection and fix the system if:

- microphone state is not visibly indicated;
- emergency stop fails to release capture;
- assistant text enters owner evidence;
- non-owner or uncertain speech is promoted automatically;
- raw audio leaves the machine in local-only mode;
- a conversation in `conversation_only` mode changes the semantic snapshot;
- speaker-profile or transcript deletion corrupts unrelated evidence;
- echo creates repeated false turns;
- CI becomes red at the branch head.
