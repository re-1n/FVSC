# FVSC project status

_Last updated: 2026-07-12_

## Executive status

FVSC has reached an **operational experimental-pilot checkpoint**.

The implementation is sufficiently tested to begin controlled real-vault and real-audio use. However, the central empirical claim — that the current density-matrix shape adds value beyond simpler semantic structures — is **not demonstrated**.

Current classification:

| Question | Status |
|---|---|
| Engineering correctness | Demonstrated at the validated checkpoint |
| Local Obsidian pilot readiness | Ready for controlled use |
| Voice R1 implementation | Implemented and CI-tested |
| Voice R1 real-audio acceptance | Pending ten real owner recordings |
| Predictive value on public prose | Signal above random, but worse than direct graph |
| Personal practical usefulness | Not yet measured |
| Density-matrix superiority | Not demonstrated |

Development branch:

```text
fix/security-and-integrity-hardening
```

Draft pull request:

```text
#1 — FVSC hardening, daily pilot, and local voice R1
```

Latest validated code checkpoint:

```text
7d0045be11b2d88aaa2dc6732e4e7f3298018cb9
```

GitHub Actions run `29186483448` completed successfully at that checkpoint.

## Latest verified engineering checks

The full checkpoint passed:

- 51 Python tests;
- 12 live/integration tests intentionally deselected by the unit profile;
- end-to-end temporary-vault workflow;
- source create/modify/rename/delete and restart restoration;
- immutable evidence assertion, supersession and retraction;
- voice import, deterministic VAD, transcript correction and review;
- explicit voice evidence promotion and provenance-preserving retraction;
- voice retention and ASR-failure recovery;
- public-thread schema, grouping and determinism checks;
- controlled viability benchmark;
- reproducible `npm ci` from the committed lockfile;
- TypeScript typecheck;
- production Obsidian bundle build;
- non-empty `main.js` packaging check;
- installable plugin artifact publication.

This demonstrates that the implemented workflows behave consistently under the registered tests. It does not by itself demonstrate semantic usefulness.

## First evaluation on live public language

The first bounded natural-language benchmark used attributed Stack Exchange Workplace discussions from 2025.

Corpus:

- 1,068 attributed records;
- 194 discussion threads;
- 155 train threads and 39 test threads;
- all records from one thread remain on one side of the split;
- known-positive coverage: `0.8855`;
- 5,392,800 pairwise comparisons per model;
- corpus SHA-256: `fb914a374bbf5c44688325d6588d175b995592b73bf2b7b2cea724b7ac074ecb`.

Results:

| Model | ROC AUC | Average precision |
|---|---:|---:|
| Direct parser graph | **0.5935** | **0.8281** |
| FVSC normalized density shape | 0.5607 | 0.7934 |
| Deterministic random | 0.4936 | 0.7749 |
| Trace mass | 0.3484 | 0.7201 |

FVSC difference from the strongest baseline:

```text
-0.032830
```

Paired bootstrap 95% interval:

```text
[-0.033206, -0.032441]
```

Registered verdict:

```text
no_demonstrated_added_value
```

Interpretation:

- the current normalized matrix shape contains some predictive signal above deterministic random;
- it is reliably worse than retaining direct parser-edge frequency;
- the current hash-based materializer and shape metric have not justified their additional complexity;
- the result does not prove that density matrices are unsuitable in general;
- parser-derived labels are proxy labels and require a blinded manual audit before assigning the deficit entirely to the representation.

Full aggregate result: `benchmarks/results/public-language-workplace-2025-r1.md`.

## What is implemented

### Security and integrity

- loopback API origin and Host restrictions;
- bounded API inputs and safer persistence paths;
- versioned, atomic JSON pilot and voice persistence;
- generated FVSC notes, reports and raw corpora excluded from semantic ingest/version control;
- deterministic basis generation and explicit dimension checks;
- source replacement, deletion, rename, retraction and restart restoration.

### Semantic runtime foundation

- immutable `SemanticState` with evidence mass separated from normalized PSD shape;
- content-addressed immutable evidence events;
- append-only evidence ledger with assertion, retraction and supersession;
- deterministic materialization into semantic snapshots;
- provenance-preserving concept reports and trace results;
- shape-only metrics with direct-graph and trace-mass controls.

### Daily Obsidian pilot

- backend entry point `service.pilot_app:app`;
- initial rebuild from eligible Markdown notes;
- live synchronization for create, modify, rename and delete events;
- state stored in `.fvsc/pilot-state.json`;
- daily review generated under `_fvsc_review/`;
- append-only local feedback history;
- revision-aware feedback summaries that survive rebuild;
- readiness endpoint with explicit minimum-data and usefulness gates.

### Voice R1

- explicit owner voice-memo sessions and emergency stop;
- bounded local audio import and Obsidian PCM WAV recording;
- deterministic WAV decode and energy VAD;
- optional PyAV and local `faster-whisper` adapters;
- retryable `awaiting_asr` and `failed` captures;
- immutable capture, transcript and review-candidate artifacts;
- transcript correction as a new revision;
- explicit promotion into the evidence ledger;
- complete capture/session/transcript/ASR provenance;
- `ephemeral`, `24h`, `7d` and `keep` raw-audio retention;
- raw-audio deletion without deleting transcript or evidence history.

## What is not yet validated

The following claims must not be made:

- that FVSC is useful in the owner's ordinary workflow;
- that generated relations accurately represent the owner's personal semantics;
- that density-matrix shape adds value beyond direct graph, TF-IDF, PPMI or embedding baselines;
- that the current deterministic hash-based encoder is an adequate long-term encoder;
- that owner-speaker identity is verified in R1;
- that voice capture and local ASR work reliably on the owner's actual audio environment;
- that performance is acceptable on every large or unusual vault.

## Required empirical gates

### Personal pilot

| Measure | Minimum |
|---|---:|
| Current human ratings | 30 |
| Useful-rate | 0.65 |
| Mean rating | 3.5 / 5 |
| Held-out pairwise comparisons | 100 |
| Known-positive coverage | 0.50 |
| Ordinary-use duration | 7–14 days |

### Voice R1

- ten real owner recordings;
- import or explicit recording succeeds;
- transcription can be corrected;
- promotion/discard and restart restoration succeed;
- raw-audio deletion preserves provenance;
- no assistant or known non-owner speech enters owner evidence automatically.

### Public-language benchmark

- blinded manual audit of at least 100 parser-derived relations;
- TF-IDF baseline;
- PPMI baseline;
- frozen embedding baseline;
- independent runs on interpersonal and narrative/worldbuilding corpora.

## Development prospects

The project has credible prospects as a system, even though the current matrix hypothesis is unproven.

The strongest reusable assets are already independent of the final semantic representation:

- append-only evidence and provenance;
- deterministic source lifecycle;
- versioned semantic snapshots;
- local voice capture, review and retention;
- Obsidian integration;
- auditable evaluation and readiness gates;
- future operator and scenario interfaces.

The next research value comes from improving context handling, independently auditing labels and comparing against stronger baselines — not from increasing matrix complexity without evidence.

Decision rule:

- if a context-aware encoder and independently audited labels produce a reproducible advantage, density matrices remain a candidate core representation;
- if they still fail against simpler baselines, the project should preserve its evidence, voice, provenance and operator architecture while treating density matrices as an optional backend.

Therefore the project should continue, but continuation of the **system** and continuation of the **current density-matrix implementation** are separate decisions.

## Repository condition

The active branch is 166 commits ahead of `main` and changes 101 files. The branch is a valid experimental checkpoint but its raw history should not be integrated directly.

Current policy:

- keep `main`;
- keep `fix/security-and-integrity-hardening` while PR `#1` is open;
- do not delete branches without checking unique commits and open PRs;
- reconstruct accepted work as a small set of logical commits before integration;
- consolidate scattered test locations after the real-pilot checkpoint;
- delete the active feature branch only after an accepted integration commit or release tag preserves it.

See `docs/REPOSITORY_HYGIENE.md`.

## Resume point

Proceed in this order:

1. install the validated plugin and local voice dependencies;
2. complete ten real owner voice memos;
3. run the real-vault pilot and collect explicit usefulness ratings;
4. blind-audit public-corpus parser relations;
5. add stronger baselines;
6. decide whether to improve or demote the matrix representation;
7. clean and reconstruct the integration history only after the checkpoint is accepted.
