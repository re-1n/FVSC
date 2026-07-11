# FVSC project status

_Last updated: 2026-07-12_

## Current milestone

FVSC has reached an **operational daily-pilot checkpoint**. The current branch is suitable for controlled use in a real Obsidian vault, but it is not yet evidence that the density-matrix model is practically useful or superior to simpler baselines.

Development branch:

```text
fix/security-and-integrity-hardening
```

Draft pull request:

```text
#1 — FVSC hardening and daily semantic pilot
```

Validated code checkpoint:

```text
6dc02f823c0845b97db7bdf270989159e9b06295
```

GitHub Actions run `29168631054` completed successfully at that checkpoint.

## What is implemented

### Security and integrity

- loopback API origin and Host restrictions;
- bounded API inputs and safer persistence paths;
- versioned, atomic JSON pilot persistence;
- generated FVSC notes and reports excluded from semantic ingest;
- deterministic basis generation and explicit dimension checks;
- source replacement, deletion, rename, retraction and restart restoration.

### Semantic runtime foundation

- immutable `SemanticState` with evidence mass separated from normalized PSD shape;
- content-addressed immutable evidence events;
- append-only evidence ledger with assertion, retraction and supersession;
- deterministic materialization into semantic snapshots;
- provenance-preserving concept reports and trace results;
- shape-only metrics with trace-mass controls.

### Daily Obsidian pilot

- backend entry point `service.pilot_app:app`;
- initial rebuild from eligible Markdown notes;
- live synchronization for create, modify, rename and delete events;
- state stored in `.fvsc/pilot-state.json`;
- daily review generated at `_fvsc_review/FVSC Daily Review.md`;
- checkbox feedback written to an append-only local feedback history;
- revised ratings supersede earlier ratings in summaries without deleting history;
- feedback survives a full rebuild;
- readiness endpoint with explicit minimum-data and usefulness gates.

### Evaluation

- controlled viability benchmark;
- chronological train/test split on the vault;
- FVSC comparison with direct graph, trace mass and deterministic random baselines;
- AUC, average precision, coverage and paired bootstrap interval;
- explicit `insufficient_data` verdict when the sample is too small;
- JSON and Markdown held-out reports generated after rebuild.

## Verified checks

The final engineering checkpoint passed:

- 43 Python tests;
- 12 live/integration tests intentionally deselected by the unit profile;
- end-to-end temporary-vault workflow;
- controlled viability benchmark;
- reproducible `npm ci` from the committed lockfile;
- TypeScript typecheck;
- production Obsidian bundle build;
- non-empty `main.js` packaging check;
- installable plugin artifact publication.

## What is not yet validated

The following claims must **not** be made yet:

- that FVSC is useful in the owner's ordinary workflow;
- that the generated relations accurately represent the owner's personal semantics;
- that density-matrix shape adds value beyond graph frequency or evidence mass;
- that the current deterministic role-based encoder is an adequate long-term encoder;
- that performance is acceptable on every large or unusual vault;
- that desktop installation and operation have been exercised on the owner's actual machine after this checkpoint.

## Operational readiness definition

The current implementation is operationally ready for a pilot because:

- rebuild and live-update paths are tested;
- state restoration is deterministic;
- generated reviews do not become evidence;
- feedback is persisted and revision-aware;
- a real production plugin bundle is produced by CI;
- failures in Python, npm, TypeScript or packaging now fail CI instead of being hidden by shell pipelines.

## Empirical readiness definition

Before interpreting the pilot as practically useful, collect at least:

| Measure | Minimum |
|---|---:|
| Current human ratings | 30 |
| Useful-rate | 0.65 |
| Mean rating | 3.5 / 5 |
| Held-out pairwise comparisons | 100 |
| Known-positive coverage | 0.50 |
| Ordinary-use duration | 7–14 days |

A unique-model-value claim additionally requires FVSC to beat the strongest registered simple baseline with a positive lower bound of the paired bootstrap confidence interval.

## Known engineering debt

- the draft PR is large and should be squash-merged after the pilot checkpoint is accepted;
- the legacy visualization/runtime remains beside the new pilot runtime;
- the current encoder is deterministic and context-light;
- installation is still manual rather than release-driven;
- there is no blinded in-plugin comparison interface yet;
- large-vault latency, memory use and cancellation behavior need measurements on real data;
- model and parser errors need structured inspection from actual pilot outputs.

## Resume point

The next session should begin with the real-vault installation checklist in `docs/NEXT_GOALS.md`, not with additional speculative operators. The first objective is to obtain trustworthy operational and human-feedback data from ordinary use.
