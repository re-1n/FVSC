# FVSC daily-life pilot

This protocol tests whether FVSC is useful in ordinary note-taking before adding
more speculative operators. It separates three questions:

1. **Does the software work reliably?**
2. **Are its outputs useful to the vault owner?**
3. **Does the density-matrix shape add predictive value over simpler baselines?**

A positive result on one question does not imply a positive result on the others.

## Pilot data and privacy

The pilot is local-first. Its state is stored inside the configured Obsidian
vault:

```text
.fvsc/pilot-state.json
.fvsc/heldout-evaluation-latest.json
```

The first file contains the append-only evidence ledger and feedback records.
The second contains aggregate evaluation metrics. Both directories are excluded
from semantic ingest. The generated review folder is also excluded:

```text
_fvsc_review/
```

Do not publish these files unless the vault owner has reviewed their contents.

## Initial setup

1. Build or install the Obsidian plugin from the current FVSC branch.
2. Start Obsidian and confirm the status bar shows `FVSC: up`.
3. Open the command palette and run:

   ```text
   FVSC Antourage: Pilot: rebuild semantic ledger
   ```

4. The backend scans eligible Markdown notes, creates immutable evidence events,
   materializes normalized semantic states, and writes
   `.fvsc/pilot-state.json`.
5. Ordinary note edits are then mirrored into the ledger automatically. Source
   replacement retracts old evidence before adding the new revision.

## Daily workflow

Run this command once per day or after a meaningful writing session:

```text
FVSC Antourage: Pilot: create daily semantic review
```

It creates or updates:

```text
_fvsc_review/FVSC Daily Review.md
```

For each reviewed concept, mark at most one checkbox:

```markdown
- [x] Полезно / точно
- [ ] Неточно / случайно
```

or:

```markdown
- [ ] Полезно / точно
- [x] Неточно / случайно
```

The watcher sends checked items to `/pilot/review-feedback`. The review note is
never ingested into the semantic map. Marking both choices is treated as
ambiguous and ignored. Re-saving the same marked item is idempotent.

## Held-out predictive test

The API endpoint below sorts notes by modification time, trains on the earlier
fraction, and evaluates relations in later notes:

```http
POST /pilot/evaluate
Content-Type: application/json

{
  "train_fraction": 0.8,
  "bootstrap_samples": 1000,
  "max_files": 5000
}
```

The report compares:

- `fvsc_shape`: shape-only operator inclusion;
- `direct_graph`: directed relation frequency from the training notes;
- `trace_mass`: scalar evidence-mass difference;
- `random`: deterministic random ranking.

The report is written to:

```text
.fvsc/heldout-evaluation-latest.json
```

The evaluation never trains on its held-out period. It reports
`insufficient_data` instead of claiming success when coverage or comparison
counts are too low.

## Readiness gate

Current pilot readiness is available at:

```http
GET /pilot/readiness
```

The gate requires all of the following before a stronger claim:

| Gate | Minimum |
|---|---:|
| Human-reviewed concepts | 30 |
| Useful-rate | 0.65 |
| Mean rating | 3.5 / 5 |
| Held-out pairwise comparisons | 100 |
| Known-positive coverage | 0.50 |

Possible states:

- `setup_required` — no usable map exists;
- `collecting_human_feedback` — daily review sample is too small;
- `not_practically_useful_yet` — enough ratings exist but usefulness is low;
- `useful_but_predictive_test_inconclusive` — human value is visible but
  held-out data are insufficient;
- `practically_useful_without_unique_model_value` — useful to the owner, but
  FVSC does not beat the best simple baseline;
- `promising_for_extended_pilot` — human-usefulness gates pass and FVSC beats
  the best baseline with a positive paired bootstrap interval.

## Minimum pilot duration

Use the system normally for at least 7–14 days before interpreting the results.
A useful initial target is:

- at least 30 rated review concepts;
- at least 20 parseable dated notes in the held-out corpus;
- several edits, renames and deletions to exercise source lifecycle handling;
- at least one backend restart to verify deterministic restoration.

Do not change model thresholds during this collection period. Record defects and
usability issues separately from semantic ratings.

## Practical success criteria

The pilot is **operationally ready** when:

- rebuild completes without unrecoverable errors;
- live note updates survive a restart;
- generated review notes never re-enter the map;
- daily review can be completed without terminal use;
- feedback is persisted and deduplicated;
- Python end-to-end tests and Obsidian typecheck/build remain green.

The pilot is **practically useful** when the human-feedback gate passes.

The density-matrix implementation shows **unique added value** only when the
held-out FVSC score exceeds the best direct-graph, trace-mass or random baseline
and the lower bound of the paired bootstrap confidence interval is above zero.

## Known limitation of the current pilot

The current encoder remains a deterministic role-based baseline. It makes the
new ledger, state, snapshot and evaluation contracts testable, but it is not yet
a learned contextual semantic encoder. A failed unique-value test therefore
motivates replacing the encoder; it does not invalidate density-matrix semantics
as a research direction.
