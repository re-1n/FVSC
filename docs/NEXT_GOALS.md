# FVSC next goals

_Last updated: 2026-07-12_

This plan deliberately prioritizes real-vault evidence over additional model complexity.

## Goal 0 — preserve the checkpoint

Before changing behavior again:

- keep the draft PR open and unmerged;
- keep the validated plugin artifact and CI diagnostics available;
- do not change readiness thresholds during the first collection period;
- do not promote generated review content into the evidence ledger;
- record defects separately from semantic usefulness ratings.

Exit condition: the current branch can be installed and started without modifying source code.

## Goal 1 — install on the owner's real vault

1. Switch the local repository to:

   ```text
   fix/security-and-integrity-hardening
   ```

2. Install dependencies from `requirements.txt`.
3. Install the CI-built Obsidian bundle into:

   ```text
   <vault>/.obsidian/plugins/fvsc-antourage/
   ```

4. Confirm the plugin points to the correct Python interpreter and repository path.
5. Confirm the status bar reaches `FVSC: up`.
6. Run:

   ```text
   FVSC Antourage: Pilot: rebuild semantic ledger
   ```

7. Verify these outputs exist:

   ```text
   .fvsc/pilot-state.json
   .fvsc/heldout-evaluation-latest.json
   _fvsc_review/FVSC Held-out Evaluation.md
   ```

8. Restart Obsidian and confirm `/pilot/status` restores the same active evidence state.

Exit condition: rebuild, restart and one live note modification succeed on the real vault without manual data repair.

## Goal 2 — exercise source lifecycle

During ordinary use, intentionally cover:

- create one new note;
- edit an existing note several times;
- rename one note;
- delete one temporary note;
- restart the backend or Obsidian;
- rebuild the pilot ledger once after feedback already exists.

Verify:

- stale assertions are retracted;
- unrelated evidence is unchanged;
- feedback history survives rebuild;
- `_fvsc_review` and `_fvsc_concepts` remain excluded from evidence;
- state remains readable after restart.

Exit condition: no source-lifecycle defect requires deleting `.fvsc/pilot-state.json`.

## Parallel Goal V — voice evidence and Antourage dialogue

Sparse written notes may leave the map without enough observations to test. Voice
capture is therefore a justified parallel input track, but it must not bypass the
existing evidence and review contracts. Follow:

- [VOICE_INGEST_PLAN.md](./VOICE_INGEST_PLAN.md) for the full capture roadmap;
- [VOICE_R1_PILOT.md](./VOICE_R1_PILOT.md) for the implemented local pilot;
- [VOICE_ANTOURAGE_PLAN.md](./VOICE_ANTOURAGE_PLAN.md) for real-time conversation.

### V-R0 — contracts and lifecycle — implemented and CI-tested

Current branch contains:

- immutable audio, transcript and voice-candidate artifacts;
- separate `conversation_only` and `save_owner_turns_for_review` modes;
- conservative manual/automatic promotion decisions;
- owner-speaker profile and verifier protocols;
- `declared_owner`, `verified_owner`, `uncertain`, `non_owner` and `overlap` decisions;
- explicit single-active-session state machine;
- idempotent start, stop and emergency stop;
- tests proving a `conversation_only` session does not mutate the semantic snapshot.

### V-R1 — audio import and voice memo — implemented, real-audio gate pending

Implemented software scope:

- bounded raw-body audio upload;
- content hashing and local storage outside the vault;
- stdlib WAV decoder for PCM 8/16/24/32-bit input;
- optional PyAV decoder for compressed audio;
- deterministic energy-VAD baseline;
- optional local `faster-whisper` adapter;
- persisted `awaiting_asr`, `failed`, `ready`, `no_speech` and `no_transcript` states;
- repeatable transcription after installing or fixing ASR;
- immutable raw and normalized transcript layers;
- correction as linked revisions;
- explicit promotion into `EvidenceLedger` with capture/transcript/session provenance;
- provenance-preserving retraction;
- `ephemeral`, `24h`, `7d` and `keep` raw-audio retention;
- failed-ASR source preservation;
- Obsidian import, owner voice-memo, review and emergency-stop controls;
- end-to-end synthetic WAV tests through promotion and retraction.

The Python backend intentionally reports `microphone_capture=false`: Obsidian owns the
microphone and uploads a bounded WAV. It reports `voice_memo_upload=true`.

Real-audio acceptance gate:

1. install `requirements-voice.txt` in the plugin's Python environment;
2. record or import at least ten actual owner voice memos;
3. measure VAD misses, ASR errors and processing time;
4. correct, promote or discard every candidate;
5. restart Obsidian/backend and verify queue restoration;
6. delete retained raw audio and verify transcript/evidence history;
7. confirm no candidate enters the map before explicit promotion.

Exit condition: ten real owner recordings pass this flow without state repair,
untraceable assertions or source loss.

### V-R2 — half-duplex Antourage voice — next after the R1 real-audio gate

Deliverables:

- replace transitional capture processing with `AudioWorklet`;
- PCM WebSocket transport;
- VAD-completed user turns;
- partial and final transcripts;
- transport-independent chat generator shared with `/viz/ask`;
- streamed Antourage text response;
- response cancellation and emergency stop;
- explicit setting to save only user turns for later review.

Exit condition: twenty five-turn sessions complete without lost or duplicated turns,
`conversation_only` never changes the ledger, and end-of-speech latency is measured.

### V-R3 — owner voice detection

Deliverables:

- explicit local enrollment with several prompted phrases;
- quality checks and versioned speaker profile;
- replaceable verifier backend;
- uncertainty band, rejection threshold and overlap gate;
- labelled owner/non-owner pilot set;
- speaker decision attached to every candidate.

Exit condition: zero known non-owner utterances are promoted in the labelled pilot
set. Automatic promotion remains disabled until this gate has enough negative examples.

### V-R4 — spoken answers and barge-in

Deliverables:

- optional local TTS;
- sentence-level playback;
- mute and cancel controls;
- initially pause capture during playback;
- later acoustic-echo testing and full barge-in.

Exit condition: interruption promptly stops audio and generation, and echo does not
create false owner turns in the target environment.

### Voice safeguards

- no automatic evidence creation before review in the initial pilot;
- no network transcription or TTS by default;
- no raw audio inside a synced vault by default;
- no unknown or non-owner speaker promoted automatically;
- assistant responses never become owner evidence;
- model and preprocessing versions recorded in provenance;
- deleting retained audio does not delete transcript or evidence history;
- failed ASR never deletes the only source;
- recording state is always visible and emergency stop releases capture.

## Parallel Goal B — public natural-language robustness benchmark

The framework is implemented in `core/natural_language_benchmark.py`; protocol and
source restrictions are in [NATURAL_LANGUAGE_BENCHMARK.md](./NATURAL_LANGUAGE_BENCHMARK.md).

Source decision:

- do not scrape or persist Reddit content under the current general Data API terms;
- start with attributed Stack Exchange API records under their applicable CC BY-SA version;
- keep downloaded corpora local under `data/public_corpora/`;
- never connect public corpus records to the personal `EvidenceLedger`.

Implemented:

- versioned JSONL schema with author/source/license attribution;
- Stack Exchange question/answer fetcher with API backoff handling;
- code-block removal and quote markers;
- grouping all posts from one thread before chronological split;
- corpus hash, license distribution and attribution completeness;
- parser diagnostics and existing held-out FVSC/direct-graph/trace-mass/random comparison;
- deterministic fixture tests;
- raw corpus and generated report paths excluded from Git.

Next experiment:

1. freeze one bounded date range before inspecting results;
2. fetch 300–1,000 records from `workplace`;
3. require at least 100 parseable threads;
4. run the benchmark and archive only the aggregate report plus corpus hash;
5. manually blind-label at least 100 parser relations;
6. repeat separately on `interpersonal` and `worldbuilding`/`writers`;
7. add TF-IDF, PPMI and frozen embedding baselines before any strong model claim.

Exit condition: at least one corpus has adequate held-out coverage, a completed manual
parser audit and a report that can be reproduced from an attributed local corpus.

## Goal 3 — collect human usefulness data

For 7–14 days:

1. write notes normally;
2. generate the daily semantic review after meaningful writing sessions;
3. mark at most one checkbox per concept;
4. rate outputs based on usefulness and accuracy, not novelty;
5. record parser or UI defects separately.

Minimum sample:

- 30 current concept ratings;
- useful-rate target of at least 0.65;
- mean rating target of at least 3.5/5.

Exit conditions:

- **pass:** human usefulness gates are met;
- **fail:** enough ratings exist but usefulness remains below either threshold;
- **continue collecting:** fewer than 30 current ratings exist.

## Goal 4 — obtain a meaningful held-out evaluation

Rerun the pilot rebuild after the vault has enough dated notes. Review:

```text
_fvsc_review/FVSC Held-out Evaluation.md
```

Required minimum:

- at least 100 FVSC pairwise comparisons;
- known-positive coverage of at least 0.50;
- verdict other than `insufficient_data`.

Interpretation:

- `promising_added_value` permits a longer frozen-model pilot;
- `no_demonstrated_added_value` means the system may still be useful, but density shape has not beaten simple baselines;
- `not_predictive` blocks stronger model claims;
- `insufficient_data` requires more dated notes, not threshold changes.

Exit condition: a report with adequate coverage and comparison count exists.

## Goal 5 — inspect actual failure modes

After the first real sample, classify low-rated outputs into:

- parser extraction error;
- weak or missing context;
- relation direction error;
- evidence-mass dominance;
- shape metric failure;
- stale-source or provenance error;
- review-selection bias;
- UI or wording problem;
- genuinely surprising but useful relation;
- ASR transcription error;
- voice activity segmentation error;
- speaker attribution or reported-speech error.

Produce a small anonymized defect corpus before changing the encoder.

Exit condition: the dominant failure class is supported by examples rather than intuition.

## Goal 6 — improve only the bottleneck demonstrated by data

Priority order after the pilot:

1. correctness or persistence defects;
2. installation and recovery UX;
3. large-vault performance and cancellation;
4. parser precision and relation direction;
5. voice transcription and speaker-attribution defects;
6. contextual encoding;
7. blinded comparison UI;
8. additional semantic operators.

Do not begin cross-person alignment, persona simulation or scenario generation while Goals 1–5 remain incomplete.

## Goal 7 — prepare the branch for merge

After the operational checkpoint is accepted:

- update documentation with actual pilot results;
- remove or isolate dead migration scaffolding;
- confirm all CI checks at the final head;
- review security boundaries again;
- squash the large draft history into a small number of auditable commits;
- merge only after deciding whether the pilot remains experimental or becomes the default entry point.

Exit condition: the PR has a bounded scope, current evidence, green CI and an explicit release decision.

## Stop conditions

Pause the pilot and fix the system before collecting more semantic ratings if any of the following occurs:

- evidence from generated review files enters the map;
- a rebuild deletes feedback history;
- deleting or renaming one note corrupts unrelated evidence;
- state cannot be restored after restart;
- the plugin requires repeated manual repair to start;
- private vault or voice data is exposed outside the local machine unexpectedly;
- raw audio persists beyond its configured retention period;
- unknown or non-owner speech is promoted into the owner's map automatically;
- assistant speech enters owner evidence;
- a `conversation_only` session changes the semantic snapshot;
- the recording state is not visibly observable or the emergency stop fails;
- a failed ASR invocation loses the only source audio;
- public benchmark text enters the personal evidence ledger;
- posts from one public thread cross train/test;
- source/license attribution is missing from a public corpus;
- the held-out split uses future notes for training;
- CI becomes red at the branch head.

## Next-session checklist

- [ ] Install the verified plugin artifact.
- [ ] Start the backend from the current branch.
- [ ] Run the first real-vault rebuild.
- [ ] Inspect the generated held-out report without interpreting sparse results as success.
- [ ] Restart Obsidian and verify restoration.
- [ ] Modify one ordinary note and confirm live ingest.
- [ ] Generate the first daily review.
- [ ] Submit the first usefulness ratings.
- [x] Define immutable voice artifacts and promotion policy.
- [x] Define owner-verifier and explicit voice-session lifecycle contracts.
- [x] Implement bounded audio import, local storage, VAD and optional ASR.
- [x] Implement Obsidian voice-memo capture and transcript review.
- [x] Preserve session/capture/transcript provenance through promotion and retraction.
- [x] Implement retention and failed-ASR retry behaviour.
- [ ] Install `requirements-voice.txt` and run ten real owner voice memos.
- [x] Implement an attributed public natural-language benchmark adapter.
- [ ] Fetch and freeze the first Stack Exchange corpus.
- [ ] Complete the first blinded parser-relation audit.
- [ ] Implement half-duplex Antourage voice only after the R1 real-audio gate.
- [ ] Record installation/runtime defects in the PR or a dedicated issue.
