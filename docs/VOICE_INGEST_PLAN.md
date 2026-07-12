# FVSC voice-ingest integration plan

_Last updated: 2026-07-12_

## Why this block is necessary

FVSC cannot infer a useful personal semantic model from sparse evidence. Written
notes are high quality but incomplete: much of ordinary reasoning, self-talk,
planning and reflection remains spoken and disappears.

Voice input is therefore a reasonable next source of evidence, but it introduces
three risks that do not exist to the same degree in ordinary note ingest:

1. private raw audio can be much more sensitive than text;
2. other people's speech can be incorrectly attributed to the vault owner;
3. ASR cleanup and semantic extraction can silently change what was actually said.

The voice pipeline must therefore be a provenance-preserving evidence source, not
a direct shortcut from microphone samples into density matrices.

## Core rule

```text
microphone or audio file
  -> local capture record
  -> voice activity segmentation
  -> local transcription
  -> speaker attribution
  -> immutable transcript artifact
  -> semantic evidence candidates
  -> explicit promotion policy
  -> EvidenceLedger
  -> SemanticSnapshot
```

Raw audio, transcript text, normalized text and extracted semantic assertions are
separate artifacts. None may overwrite another.

## Product decision

Do **not** begin with unrestricted always-on recording.

The staged order is:

1. import an existing audio file;
2. explicit push-to-record or start/stop recording session;
3. owner-only background sessions with a visible recording indicator;
4. optional diarization and owner-speaker filtering;
5. bounded ambient capture only after privacy and attribution gates pass.

This order makes the transcription and promotion path testable before introducing
continuous capture, battery use, microphone lifecycle and bystander-speech risks.

## Non-negotiable invariants

- Recording is opt-in and visibly indicated at all times.
- A global emergency stop must immediately close the microphone stream.
- Network transcription is disabled by default.
- Raw audio is never stored inside a synced Obsidian vault by default.
- Unknown or non-owner speakers never become personal evidence automatically.
- A transcript is not evidence of truth; it is evidence that an utterance was
  detected and transcribed with a stated confidence.
- ASR output and semantic extraction remain independently inspectable.
- Generated summaries are excluded from semantic ingest.
- Deleting a capture creates a retraction or tombstone; unrelated evidence is not
  rebuilt or deleted.
- Retention policies are enforced automatically and covered by tests.

## Proposed architecture

### 1. Capture service

The capture worker should run as a separate local process managed by the FVSC
backend. Obsidian provides controls and status, but audio capture must not depend
on a visible note or active view.

```python
class AudioCaptureBackend(Protocol):
    def list_devices(self) -> list[AudioDevice]: ...
    def start(self, config: CaptureConfig) -> CaptureSession: ...
    def stop(self, session_id: str) -> CaptureSummary: ...
```

Initial input modes:

- `file_import` — WAV, FLAC, MP3, M4A or OGG input;
- `manual_session` — explicit start and stop;
- `background_session` — bounded session with explicit duration;
- `ambient` — deferred until the attribution and privacy gates pass.

Recommended capture representation:

- 16 kHz;
- mono;
- signed 16-bit PCM internally;
- short rolling chunks;
- pre-roll and post-roll around detected speech;
- monotonic timestamps in addition to wall-clock time.

The capture layer should expose an abstract backend so Windows, macOS and Linux
implementations can differ without changing the evidence model.

### 2. Ring buffer and segmentation

A memory-only rolling buffer prevents losing the beginning of an utterance while
avoiding permanent storage of continuous silence.

Suggested behavior:

- 3-5 seconds of pre-roll;
- frame-level voice activity detection;
- speech segments closed after configurable silence;
- adjacent segments merged when the gap is short;
- maximum segment length enforced;
- raw silence discarded unless diagnostic capture is explicitly enabled.

The first VAD implementation should use a replaceable `VoiceActivityDetector`
protocol. Silero VAD is a practical initial local backend; a simpler energy-based
backend remains useful as a deterministic test baseline.

### 3. Audio preprocessing

Preprocessing must be conservative. It may improve ASR input but must never
replace the source audio.

Pipeline:

```text
source chunk
  -> channel conversion
  -> resample to ASR rate
  -> loudness normalization
  -> optional conservative denoise
  -> clipped-signal and low-SNR diagnostics
  -> ASR input artifact
```

Every transformation records:

- algorithm and version;
- input and output hashes;
- parameters;
- signal-quality diagnostics.

Aggressive denoising is deferred because it can remove quiet speech or alter
phonetic cues.

### 4. ASR backend abstraction

```python
class TranscriptionBackend(Protocol):
    backend_id: str
    model_id: str

    def transcribe(
        self,
        audio: AudioArtifact,
        *,
        language: str | None,
        word_timestamps: bool,
    ) -> TranscriptArtifact: ...
```

Initial candidates:

- `faster-whisper` for the Python pilot, word timestamps and configurable local
  VAD integration;
- `whisper.cpp` as a low-dependency cross-platform fallback and future bundled
  desktop backend.

The backend choice is configuration, not part of evidence identity. Evidence
records include backend and model versions so the same audio can be
re-transcribed after a model upgrade without deleting the original result.

### 5. Speaker attribution

Speaker attribution is the most important semantic-safety gate.

Phase A:

- explicit owner-only recordings;
- no diarization requirement;
- all content is labelled `speaker_scope=declared_owner_session`.

Phase B:

- speaker diarization produces anonymous clusters such as `speaker_0`;
- no cluster is assumed to be the owner;
- the user may label a cluster manually.

Phase C:

- optional local owner-speaker enrollment;
- owner attribution requires a configurable confidence threshold;
- uncertain and overlapping speech remains unpromoted.

A local pyannote-based adapter may be added later, but it must remain optional
because it adds model downloads, heavier dependencies and separate telemetry or
model-access considerations.

Required promotion rule:

```text
owner confirmed or declared owner-only session -> eligible candidate
unknown speaker                              -> transcript only
non-owner speaker                            -> never personal evidence
overlap or uncertain speaker                 -> manual review
```

### 6. Immutable voice artifacts

Proposed value objects:

```python
@dataclass(frozen=True)
class AudioCapture:
    capture_id: str
    mode: str
    device_id: str
    started_at: float
    ended_at: float
    sample_rate: int
    channels: int
    source_hash: str
    retention_class: str

@dataclass(frozen=True)
class SpeechSegment:
    segment_id: str
    capture_id: str
    start_seconds: float
    end_seconds: float
    vad_backend: str
    speech_probability: float
    audio_hash: str

@dataclass(frozen=True)
class TranscriptSegment:
    transcript_id: str
    segment_id: str
    text_raw: str
    language: str | None
    words: tuple[TranscriptWord, ...]
    asr_backend: str
    model_id: str
    confidence: float | None
    speaker_label: str | None
    speaker_confidence: float | None

@dataclass(frozen=True)
class VoiceEvidenceCandidate:
    candidate_id: str
    transcript_id: str
    text_normalized: str
    proposed_assertions: tuple[dict, ...]
    promotion_state: str
    extraction_version: str
```

Artifacts are content-addressed where possible. Reprocessing creates new derived
artifacts linked to the same source capture.

### 7. Raw, normalized and extracted text

The system must preserve three layers:

1. `text_raw` — exact ASR output with timestamps;
2. `text_normalized` — punctuation, filler and casing cleanup;
3. `proposed_assertions` — parser output eligible for the evidence ledger.

Normalization rules must be reversible or at least auditable. Hesitations,
repetitions and false starts may be removed from `text_normalized`, but never
from `text_raw`.

Semantic extraction must not silently convert questions, quotations, jokes,
reported speech or negations into owner beliefs. These require explicit modality
and source-speech metadata.

### 8. Promotion policy

Voice-derived data receives a stricter promotion policy than ordinary notes.

Recommended initial rules:

| Capture class | Default promotion |
|---|---|
| imported personal voice memo | review required |
| explicit owner-only session | review required, batch approval allowed |
| background owner session | review required |
| unknown-speaker segment | prohibited |
| non-owner segment | prohibited |
| low-confidence or overlap | prohibited until reviewed |

After enough validated data, high-confidence explicit owner-only sessions may be
promoted automatically with a lower evidence weight than user-authored text.
Ambient speech should remain review-gated.

Promotion creates ordinary immutable `EvidenceEvent` assertions with additional
voice provenance:

- capture ID;
- segment and transcript IDs;
- time range;
- speaker attribution state;
- ASR and extraction versions;
- confidence values;
- optional retained-audio reference.

### 9. Storage and retention

Default storage should be outside the vault in an application data directory:

```text
<FVSC app data>/voice/
  captures/
  segments/
  transcripts/
  diagnostics/
```

Only compact metadata and promoted evidence references belong in
`.fvsc/pilot-state.json`.

Suggested retention classes:

- `ephemeral` — delete source audio after successful transcription and review;
- `24h` — default diagnostic grace period;
- `7d` — temporary pilot debugging;
- `keep` — explicit user choice only.

Required behavior:

- deletion scheduler is deterministic and logged;
- a failed transcription never silently deletes the only source;
- retained audio can be deleted without deleting transcript or evidence history;
- storage paths are rejected if they resolve inside a synced vault unless the
  user explicitly overrides the warning;
- export is separate from ordinary persistence.

### 10. Service API

Proposed endpoints:

```text
GET    /pilot/voice/status
GET    /pilot/voice/devices
POST   /pilot/voice/import
POST   /pilot/voice/sessions
DELETE /pilot/voice/sessions/{session_id}
GET    /pilot/voice/candidates
GET    /pilot/voice/candidates/{candidate_id}
POST   /pilot/voice/candidates/{candidate_id}/promote
POST   /pilot/voice/candidates/{candidate_id}/discard
POST   /pilot/voice/candidates/{candidate_id}/correct
GET    /pilot/voice/metrics
```

Start and stop operations must be idempotent. Status must expose microphone use,
recording mode, elapsed duration, buffered duration, storage usage, transcription
queue and last error.

### 11. Obsidian UX

Initial commands:

```text
FVSC Antourage: Voice: import audio file
FVSC Antourage: Voice: start recording session
FVSC Antourage: Voice: stop recording session
FVSC Antourage: Voice: open transcript review queue
FVSC Antourage: Voice: emergency stop
```

Required UI elements:

- persistent recording indicator;
- elapsed time and active microphone;
- explicit background-session duration;
- queue length and processing state;
- transcript editor showing raw and normalized text;
- speaker label and confidence;
- promote, correct, discard and delete-audio actions;
- retention policy selector;
- warning when other people may be recorded.

Generated review material should live under `_fvsc_voice_review/` and be excluded
from semantic ingest.

## Delivery phases

### V0 — offline audio-file ingest

Deliverables:

- audio artifact schema;
- local file import;
- VAD segmentation;
- local ASR backend protocol;
- transcript persistence;
- review queue;
- explicit promotion to the existing evidence ledger.

Gate:

- deterministic replay from the same audio and model version;
- no evidence created before promotion;
- source hashes and time ranges survive restart;
- raw-audio deletion does not corrupt evidence history.

### V1 — explicit recording sessions

Deliverables:

- local microphone device selection;
- start, stop and emergency-stop lifecycle;
- ring buffer and speech segmentation;
- persistent visible recording state;
- recovery from backend or Obsidian restart;
- storage quota and retention scheduler.

Gate:

- no lost or duplicated segments in a 60-minute test;
- microphone always closes after stop or crash recovery;
- retention policy is enforced;
- CPU, memory and disk use are measured.

### V2 — transcript quality and correction loop

Deliverables:

- word timestamps;
- raw-versus-normalized transcript view;
- user corrections stored as revisions;
- ASR error corpus;
- Russian and mixed-language test set;
- hallucination and silence-output detection.

Gate:

- annotated pilot sample of at least 30 minutes;
- acceptable word error rate for the actual microphone and environment;
- no silent or low-confidence segment is promoted without review;
- corrections survive re-transcription.

### V3 — speaker separation

Deliverables:

- diarization backend protocol;
- anonymous speaker clusters;
- owner-speaker confirmation or enrollment;
- overlapping-speech handling;
- strict owner-only promotion filter.

Gate:

- zero known non-owner utterances promoted in the annotated pilot set;
- uncertain attribution always reaches manual review;
- speaker metadata survives rebuild and model upgrades.

### V4 — bounded background sessions

Deliverables:

- explicitly timed background recording;
- system-level visible state or tray indicator;
- pause zones and schedules;
- privacy hotkey;
- automatic silence disposal;
- daily capture summary.

Gate:

- owner can always determine whether recording is active;
- emergency stop works when Obsidian UI is not focused;
- no recording starts after reboot without explicit policy;
- no network egress in local-only mode;
- bystander handling is tested before ordinary use.

### V5 — semantic value experiment

Compare three periods or conditions:

1. text notes only;
2. text plus reviewed voice evidence;
3. text plus automatically promoted high-confidence owner-only voice evidence.

Metrics:

- number of active evidence events;
- new concept and relation coverage;
- percentage of voice candidates promoted;
- correction rate;
- useful-rate of daily reviews;
- owner-rated contamination or irrelevance;
- held-out FVSC performance versus graph and mass baselines;
- additional value per minute of review effort.

Gate:

Voice integration is practically justified only if it increases useful evidence
coverage without an unacceptable increase in correction burden, privacy risk or
false semantic assertions.

## Evaluation checklist

### Capture reliability

- dropped frames and discontinuities;
- duplicate segments;
- device disconnect recovery;
- crash recovery;
- microphone close latency;
- disk quota enforcement.

### VAD quality

- missed owner speech;
- false activations on music, television and keyboard noise;
- clipped beginnings and endings;
- average retained-audio ratio.

### ASR quality

- word error rate on manually corrected segments;
- deletion, insertion and substitution errors;
- Russian, English and mixed-language behavior;
- hallucination rate during silence or noise;
- timestamp alignment.

### Speaker safety

- owner precision and recall;
- unknown-speaker rate;
- non-owner promotion count;
- overlap handling;
- manual-label correction rate.

### Semantic quality

- candidate acceptance rate;
- parser error rate;
- negation and quotation errors;
- evidence duplication;
- useful-rate in daily review;
- predictive delta versus text-only baseline.

### Operational cost

- CPU and GPU load;
- memory use;
- battery impact;
- storage per hour;
- transcription latency;
- review minutes per recorded hour.

## Initial implementation sequence

Use small commits in this order:

1. `docs: define voice data and privacy contracts`;
2. `feat(voice): add immutable audio and transcript artifacts`;
3. `feat(voice): add local file import and hashing`;
4. `feat(voice): add replaceable VAD protocol and deterministic baseline`;
5. `feat(voice): add faster-whisper backend behind an optional dependency`;
6. `feat(voice): persist transcript review queue atomically`;
7. `feat(voice): promote reviewed transcript candidates to EvidenceLedger`;
8. `test(voice): add end-to-end audio fixture workflow`;
9. `feat(plugin): add audio import and review commands`;
10. `feat(voice): add explicit microphone sessions`;
11. `test(voice): exercise stop, crash and retention behavior`;
12. only then begin diarization and bounded background capture.

## Immediate recommendation

The next engineering milestone should be **V0: local audio-file ingest**, not
always-on recording. It directly addresses data scarcity while keeping capture
consent, speaker scope and transcription quality observable.

Once V0 works on real voice memos, V1 adds explicit microphone sessions. The
background recorder should remain disabled until transcript quality, retention
and owner-speaker attribution are measured on the actual machine and acoustic
environment.
