# FVSC repository hygiene

_Last updated: 2026-07-12_

## Current condition

The repository contains a valid experimental checkpoint, but its development history is not suitable for direct integration as-is.

Cleanup assessment baseline:

- default branch: `main`;
- active development branch: `fix/security-and-integrity-hardening`;
- open draft PR: `#1`;
- branch delta at assessment start: 166 commits ahead of `main`, 0 behind;
- changed files at assessment start: 101;
- latest validated code checkpoint: `7d0045be11b2d88aaa2dc6732e4e7f3298018cb9`;
- latest full code CI run: `29186483448` — successful.

The current branch is therefore a useful research and pilot checkpoint, but not a clean release branch.

## Branch decisions

### Keep now

- `main` — stable base and merge target;
- `fix/security-and-integrity-hardening` — contains the only open PR and the validated R1 implementation.

### Delete now

- `repo-hygiene-plan` — temporary redundant pointer created during the cleanup assessment. It has zero unique commits relative to `fix/security-and-integrity-hardening` and is three commits behind it. Deleting it loses no work.

Delete with:

```bash
git push origin --delete repo-hygiene-plan
```

### Do not delete yet

A branch must not be deleted while any of the following is true:

- it is the head of an open PR;
- it contains commits not reachable from `main` or a preserved release tag;
- it contains the only reference to a reproducible benchmark or build artifact;
- its replacement integration commit has not passed CI;
- a real-vault or real-audio pilot still depends on that exact checkpoint.

### Delete after integration

The active feature branch may be deleted only after:

1. an accepted integration commit or release tag preserves the checkpoint;
2. the integration history passes the same Python, benchmark and plugin checks;
3. the real-vault state and voice repository can be restored on the integrated code;
4. the PR is merged or explicitly closed as superseded.

Any other stale branch may be deleted when it has no open PR and either has no unique commits or its unique commits are intentionally archived elsewhere.

## Local branch audit

Run before deleting any branch:

```bash
git fetch --all --prune
git branch -r --sort=-committerdate
git branch -r --merged origin/main
git log --oneline origin/main..origin/<branch>
```

For a branch with unique commits, inspect the diff before deciding:

```bash
git diff --stat origin/main...origin/<branch>
git range-diff origin/main...origin/<branch>
```

## Cleanup sequence

### Phase A — preserve the validated checkpoint

- keep PR `#1` as draft;
- keep the frozen benchmark reports and corpus hashes;
- keep raw public corpora and personal voice data out of Git;
- record exact tested commit and workflow run in `README.md`, `PROJECT_STATUS.md` and the PR body;
- do not rename runtime modules during the first real-vault and real-audio pilot.

### Phase B — reduce integration history

Before merging, reconstruct the accepted work as approximately five logical commits:

1. security, persistence and deterministic infrastructure;
2. immutable evidence and semantic runtime;
3. daily Obsidian pilot and held-out evaluation;
4. local voice R1;
5. public-language benchmark, documentation and CI.

The raw development history should remain available through the draft PR or an archival tag, but it should not become the permanent `main` history.

### Phase C — normalize the source tree

Current cleanup targets:

- tests are split across `tests/`, `core/tests/`, `core/test_*.py` and `service/tests/`;
- legacy density runtime and pilot runtime live side by side without a package boundary;
- service routers combine stable API, pilot API and legacy visualization concerns;
- several long planning documents overlap in scope;
- release and compatibility policy are not yet formalized.

Target layout after the pilot checkpoint:

```text
src/fvsc/
  semantic/
  evidence/
  voice/
  service/
  legacy/

tests/
  unit/
  integration/
  e2e/

benchmarks/
  specs/
  results/

docs/
  status/
  architecture/
  operations/
  experiments/
```

This is a migration target, not a reason to rewrite working paths before the pilot.

### Phase D — release hygiene

Add before declaring a stable release:

- `CHANGELOG.md`;
- explicit project license and third-party attribution policy;
- `CONTRIBUTING.md` with test and benchmark rules;
- compatibility matrix for Python, Obsidian, Node and local ASR;
- release tag and checksums for the plugin bundle;
- migration notes for pilot-state and voice-repository schema changes.

## Evidence-status policy

Every public project-status statement must distinguish three questions:

1. **Engineering correctness** — do tests, persistence and packaging work?
2. **Predictive semantic value** — does FVSC beat simple baselines on held-out data?
3. **Personal practical usefulness** — does the owner find it accurate and useful in ordinary life?

Current answers:

- engineering correctness: demonstrated at the validated checkpoint;
- predictive semantic value: not demonstrated; current FVSC shape loses to the direct graph on the first public corpus;
- personal practical usefulness: not yet measured with the required real-vault ratings;
- real voice usability: implementation is ready for a pilot, but ten real recordings have not yet passed the R1 acceptance gate.

## Stop condition for the density-matrix hypothesis

Density matrices should remain an experimental representation, not a protected assumption.

If a context-aware encoder, independently audited labels and stronger baselines still show no reproducible advantage, FVSC should retain the evidence ledger, provenance, voice capture and operator architecture while demoting density matrices to an optional backend rather than the defining core.
