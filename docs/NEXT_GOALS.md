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

## Parallel Goal V0 — obtain reviewed voice evidence

Sparse written notes may leave the map without enough observations to test. Voice
capture is therefore a justified parallel input track, but it must not bypass the
existing evidence and review contracts.

Follow [VOICE_INGEST_PLAN.md](./VOICE_INGEST_PLAN.md). The first milestone is
**audio-file import**, not always-on recording.

Deliverables:

- immutable audio, speech-segment and transcript artifact schemas;
- local audio-file import and source hashing;
- replaceable VAD backend;
- local ASR backend with word or segment timestamps;
- raw and normalized transcript layers;
- transcript review queue;
- explicit promotion of reviewed candidates into `EvidenceLedger`;
- raw-audio retention and deletion policy;
- end-to-end test from audio fixture to promoted and retracted evidence.

Required safeguards:

- no automatic evidence creation before review;
- no network transcription by default;
- no raw audio inside a synced vault by default;
- no unknown or non-owner speaker promoted as personal evidence;
- model and preprocessing versions recorded in provenance;
- deleting retained audio does not delete transcript or evidence history.

Exit condition: at least ten real personal voice memos can be imported,
transcribed, corrected, promoted and restored after restart without manual state
repair or untraceable semantic assertions.

Only after this gate:

1. add explicit microphone start/stop sessions;
2. measure ASR and VAD quality on at least 30 annotated minutes;
3. add optional speaker separation;
4. consider bounded background sessions with a persistent visible indicator and
   emergency stop.

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
- the recording state is not visibly observable or the emergency stop fails;
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
- [ ] Begin V0 by defining immutable audio and transcript artifacts.
- [ ] Add local audio-file import before implementing microphone capture.
- [ ] Record installation/runtime defects in the PR or a dedicated issue.
