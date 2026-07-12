# FVSC project status

_Last updated: 2026-07-12_

## Executive status

FVSC has reached an **operational experimental-pilot checkpoint** with a first explicit asymmetric container backend.

The implementation is sufficiently tested to begin controlled real-vault and real-audio use. The central representation question remains open:

- the original density-only backend is reliably weaker than a direct graph on the complete first public corpus;
- explicit container structure is statistically competitive with the direct graph on a bounded real-language slice;
- projected density has not yet improved the container structure;
- personal practical usefulness remains unmeasured.

Current classification:

| Question | Status |
|---|---|
| Engineering correctness | Demonstrated at the validated checkpoint |
| Local Obsidian pilot readiness | Ready for controlled use |
| Voice R1 implementation | Implemented and CI-tested |
| Voice R1 real-audio acceptance | Pending ten real owner recordings |
| Density-only predictive value | Worse than direct graph on the first complete corpus |
| Explicit container predictive value | Competitive, not superior, on the first bounded slice |
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

Latest validated code experiment checkpoint:

```text
e05e923f2f13ac3d8f11a0c75a205629c1d8f7f6
```

Registered runs:

```text
standard tests:              29193677444
explicit-container live run: 29193677480
```

## Latest verified engineering checks

The checkpoint passed:

- 145 Python tests;
- 12 live/integration tests intentionally deselected by the unit profile;
- end-to-end temporary-vault workflow;
- source create/modify/rename/delete and restart restoration;
- immutable evidence assertion, supersession and retraction;
- Voice R1 import, deterministic VAD, transcript correction and review;
- explicit voice evidence promotion and provenance-preserving retraction;
- voice retention and ASR-failure recovery;
- explicit container materialization and independent directed embeddings;
- bounded recursive activation and cycle protection;
- context-sensitive cached path queries;
- evidence-backed container explanations;
- resource-bounded graph/container/density ablation;
- controlled viability benchmark;
- reproducible `npm ci` from the committed lockfile;
- TypeScript typecheck;
- production Obsidian bundle build;
- installable plugin artifact publication.

This demonstrates consistent behaviour under registered tests. It does not demonstrate personal usefulness or semantic correctness.

## Density-only evaluation on live public language

The first complete natural-language benchmark used attributed Stack Exchange Workplace discussions from 2025.

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

- the current normalized matrix shape contains some signal above deterministic random;
- it is reliably worse than direct parser-edge frequency;
- this rejects the present density-only materializer for that task, not density matrices in general;
- parser-derived labels are proxy labels and require blinded manual audit.

Aggregate result: `benchmarks/results/public-language-workplace-2025-r1.md`.

## Explicit ContainerCore v1 evaluation

ContainerCore implements the original asymmetric nesting hypothesis as a derived layer over the evidence ledger:

- `A <- B` and `B <- A` are independent evidence-backed embeddings;
- roles and context keys are preserved;
- recursive activation is depth- and branch-bounded;
- cycles are blocked per path;
- each container contribution is counted once through its strongest selected path;
- explanations return container paths, edge IDs and evidence IDs;
- density matrices are optional local state, not canonical memory.

The first completed live ablation used a deterministic chronological 80-thread slice from the same frozen corpus.

Protocol:

- available corpus: 1,068 records / 194 threads;
- selected chronological slice: 80 threads;
- train/test: 64 / 16;
- known-positive coverage: `0.7821`;
- sampled positives/negatives: 320 / 320;
- pairwise comparisons per model: 6,400;
- semantic dimension: 16;
- maximum recursive depth: 2;
- runtime: 39.71 seconds;
- materializer: `explicit-container-core-signed-permutation-v1`.

Results:

| Backend | ROC AUC | Average precision |
|---|---:|---:|
| Direct graph | **0.5716** | 0.5867 |
| Conditional graph | 0.5702 | 0.5709 |
| Container structure | 0.5637 | 0.5872 |
| Container projected density | 0.5631 | **0.5875** |
| Container hybrid | 0.5631 | 0.5869 |
| Density without containers | 0.5567 | 0.5558 |
| PPMI graph | 0.5509 | 0.5503 |
| Random | 0.5364 | 0.5148 |

Best-container AUC difference from the strongest non-container baseline:

```text
-0.007891
```

Paired document-bootstrap 95% interval:

```text
[-0.04890625, 0.02907617]
```

Direction-dependent forward/reverse score rate on evaluated positive pairs:

```text
0.5125
```

Registered verdict:

```text
container_model_competitive
```

Interpretation:

- explicit structure is close to the direct graph on this bounded slice;
- the interval crosses zero, so superiority and inferiority are both unproven at this scale;
- projected density did not improve ROC AUC over structure-only containers;
- the current evidence favours continuing work on explicit asymmetric structure rather than increasing matrix complexity;
- full-corpus scale-up and strong contextual-polysemy tests remain pending.

Aggregate result: `benchmarks/results/container-core-workplace-2025-80threads-v1.md`.

## What is implemented

### Security and integrity

- loopback API origin and Host restrictions;
- bounded API inputs and safer persistence paths;
- versioned, atomic JSON pilot and voice persistence;
- generated notes, reports and raw corpora excluded from ingest/version control;
- deterministic basis generation and explicit dimension checks;
- source replacement, deletion, rename, retraction and restart restoration.

### Semantic runtime foundation

- immutable `SemanticState` with evidence mass separated from normalized PSD shape;
- content-addressed immutable evidence events;
- append-only evidence ledger with assertion, retraction and supersession;
- deterministic materialization into semantic snapshots;
- provenance-preserving reports and trace results;
- graph, density, PPMI and random controls.

### Explicit ContainerCore

- immutable containers, facets, contributions and embeddings;
- independent asymmetric embedding directions;
- context-preserving query edges;
- bounded recursive projection and activation;
- deterministic path explanations with provenance;
- structure-only, projected-density and hybrid scores;
- signed-permutation operator baseline for resource-bounded evaluation;
- cached public-language ablation.

### Daily Obsidian pilot

- backend entry point `service.pilot_app:app`;
- initial rebuild from eligible Markdown notes;
- live synchronization for create, modify, rename and delete events;
- state stored in `.fvsc/pilot-state.json`;
- daily review and append-only local feedback;
- readiness endpoint with minimum-data and usefulness gates.

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
- raw-audio retention and deletion without deleting semantic history.

## What is not yet validated

The following claims must not be made:

- that FVSC is useful in the owner's ordinary workflow;
- that parser-generated relations accurately represent personal semantics;
- that ContainerCore is superior to a direct or conditional graph;
- that density state adds value to the container topology;
- that deterministic signed-permutation operators are adequate long-term operators;
- that owner-speaker identity is verified in R1;
- that local ASR works reliably on the owner's actual recordings;
- that performance is acceptable on the complete public corpus or every vault.

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

### ContainerCore and public-language evaluation

- blinded manual audit of at least 100 parser-derived relations;
- human-labelled contextual-polysemy benchmark;
- order-sensitive context-update benchmark;
- learned or calibrated projection operators;
- strongest-path versus evidence-disjoint and probabilistic path aggregation;
- frozen embedding baseline;
- independent interpersonal and narrative/worldbuilding corpora;
- full 194-thread scale-up after reducing dense materialization cost.

## Development prospects

The project has credible prospects as a system.

The strongest reusable assets are independent of the final local state representation:

- append-only evidence and provenance;
- explicit asymmetric container topology;
- deterministic source lifecycle;
- versioned snapshots;
- local voice capture, review and retention;
- Obsidian integration;
- auditable evaluation and readiness gates;
- operator and scenario interfaces.

Current decision rule:

- keep the direct graph as the strongest simple reference;
- keep ContainerCore experimental while its paired interval overlaps the graph;
- keep density state optional until it adds reproducible value over container structure;
- do not increase model complexity without independently audited labels or strong contextual tasks.

Therefore the project should continue, but continuation of the **system**, **container topology** and **density-state backend** are separate decisions.

## Repository condition

The active branch is a valid experimental checkpoint, but its long raw history should not be integrated directly.

Current policy:

- keep `main` unchanged;
- keep `fix/security-and-integrity-hardening` while PR `#1` is open;
- do not delete branches without checking unique commits and open PRs;
- reconstruct accepted work as a small set of logical commits before integration;
- consolidate scattered test locations after the real-pilot checkpoint;
- delete the feature branch only after an accepted integration commit or release tag preserves it.

See `docs/REPOSITORY_HYGIENE.md`.

## Resume point

Proceed in this order:

1. complete a blinded manual audit of at least 100 parser relations;
2. run the human-labelled contextual-polysemy test;
3. test calibrated projection and path-aggregation alternatives;
4. install the validated plugin and complete ten real owner voice memos;
5. run the real-vault pilot and collect explicit usefulness ratings;
6. scale the container benchmark only after reducing dense materialization cost;
7. clean and reconstruct integration history only after the checkpoint is accepted.
