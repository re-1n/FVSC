# FVSC Voice R1 pilot

_Last updated: 2026-07-12_

## Scope

R1 provides bounded local audio import and explicit owner voice-memo sessions. It
does not provide background recording, real-time Antourage dialogue, speaker
verification or automatic promotion into the semantic map.

The production path is:

```text
local file or explicit microphone button
  -> WAV/compressed audio capture outside the vault
  -> deterministic decode and energy VAD
  -> optional local faster-whisper ASR
  -> immutable raw and normalized transcript
  -> review/correction queue
  -> explicit user promotion
  -> EvidenceLedger with voice provenance
```

## Installation

The ordinary text pilot still uses:

```bash
python -m pip install -r requirements.txt
```

Install the optional local voice stack in the same Python environment used by the
Obsidian plugin:

```bash
python -m pip install -r requirements-voice.txt
```

This adds `faster-whisper` and PyAV. The Whisper model is loaded lazily on the first
transcription. Select it with:

```text
FVSC_ASR_MODEL=small
```

The default is `small`. Model downloads, inference speed and hardware acceleration
are environment-specific and are therefore not part of the default CI profile.

## Storage

Raw audio is stored outside the configured Obsidian vault by default:

- Windows: `%LOCALAPPDATA%/FVSC/voice/`
- macOS: `~/Library/Application Support/FVSC/voice/`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/fvsc/voice/`

Override only with an explicit local path:

```text
FVSC_VOICE_DATA_DIR=/path/outside/the/vault
```

The backend rejects a voice data directory that resolves inside the vault.

Stored structure:

```text
voice/
  captures/
  voice-index.json
```

`voice-index.json` contains immutable capture/transcript/candidate artifacts plus
separate lifecycle records. Deleting raw audio does not rewrite the content-addressed
capture artifact and does not delete transcript or evidence history.

## Obsidian commands

```text
FVSC Antourage: Voice: import audio file
FVSC Antourage: Voice: start/stop owner voice memo
FVSC Antourage: Voice: open transcript review queue
FVSC Antourage: Voice: emergency stop
```

A microphone ribbon button toggles the explicit voice-memo session. The status bar
shows `voice recording` while capture is active. Plugin unload invokes emergency
stop before shutting down the backend.

The R1 browser capture uses a transitional `ScriptProcessorNode`, requests echo
cancellation/noise suppression/automatic gain control, and uploads a bounded mono
PCM WAV. R2 will replace this with `AudioWorklet` and a WebSocket transport.

## Review and promotion

For each ASR result the review modal shows:

- raw ASR text;
- normalized text;
- ASR confidence when available;
- declared speaker attribution;
- correction, promotion and discard actions.

Correction creates a new immutable transcript and candidate revision. Old revisions
remain linked but are no longer current.

Promotion is always explicit in R1. The resulting `EvidenceEvent` records include:

- capture, transcript, candidate and explicit session IDs;
- capture mode;
- `declared_owner` attribution;
- ASR backend and model;
- transcript confidence;
- whether the transcript was corrected;
- retention class and promotion decision.

Promoted evidence cannot be discarded directly. It must be retracted, which appends
lifecycle events without erasing history.

## Behaviour without local ASR

Audio import and explicit WAV capture remain available when `faster-whisper` is not
installed. The source is stored with status `awaiting_asr`; no transcript or evidence
is invented. After installing the voice dependencies, call:

```text
POST /pilot/voice/captures/{capture_id}/transcribe
```

A model failure stores the capture as `failed` with a retryable diagnostic. The only
source audio is retained even when the selected retention class is `ephemeral`.

## Retention

- `ephemeral`: delete after all current candidates are promoted or discarded;
- `24h`: delete raw audio after 24 hours;
- `7d`: delete raw audio after seven days;
- `keep`: retain until explicit deletion.

Pure-silence captures may be removed immediately under `ephemeral`. Failed or empty
transcriptions retain their source for retry or explicit deletion.

Retention is checked when the voice repository starts and during voice API activity.
R1 does not yet run a continuously resident cleanup scheduler while the FVSC backend
is stopped.

## API

```text
GET    /pilot/voice/status
POST   /pilot/voice/import
POST   /pilot/voice/sessions
GET    /pilot/voice/sessions/{id}
POST   /pilot/voice/sessions/{id}/stop
POST   /pilot/voice/emergency-stop
GET    /pilot/voice/captures/{id}
POST   /pilot/voice/captures/{id}/transcribe
DELETE /pilot/voice/captures/{id}/audio
GET    /pilot/voice/candidates
GET    /pilot/voice/candidates/{id}
POST   /pilot/voice/candidates/{id}/correct
POST   /pilot/voice/candidates/{id}/promote
POST   /pilot/voice/candidates/{id}/discard
POST   /pilot/voice/candidates/{id}/retract
```

Audio upload uses the raw request body and an `X-FVSC-Filename` header. The R1 limit
is 100 MiB and two decoded hours. WAV works without optional decoder dependencies;
FLAC, MP3, M4A, OGG and WebM require PyAV.

## Pilot gate

R1 is accepted for ordinary local testing only after:

1. CI passes Python tests, controlled benchmark, plugin typecheck and production build;
2. ten real owner recordings can be imported or recorded;
3. all ten can be transcribed, corrected, promoted or discarded and restored after restart;
4. raw-audio deletion leaves transcript and evidence history readable;
5. no candidate enters the map before explicit promotion;
6. no failed ASR invocation deletes the only source.

This gate validates the ingestion workflow, not ASR accuracy or speaker identity.
Those require a real 30-minute annotated audio sample and the R3 owner-verification
evaluation.
