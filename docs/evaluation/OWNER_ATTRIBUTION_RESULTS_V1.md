# Explicit owner-attribution v1: implementation and results

2026-10-11. Protocol and public inputs frozen at `2f28378`; implementation and
runner committed at `e0cc41e` before the diagnostic run.

## What changed

`PlannedRequirement.attribution_scope="direct_owner"` explicitly requests owner
evidence. F1 supplies eligible character regions with abstention reasons; S6 then
requires an affirmed relation cue inside one such region. It preserves its previous
polarity context and never concatenates disjoint spans. Duplicate source labels are
rejected in this mode. The planned-slot runner enforces the resulting label filter
even without an optional caller-supplied guard; an external allowlist cannot override
an owner-attribution rejection.

Owner transport authorship is required. Missing authorship, forwarding and external
origin abstain. Mixed/unresolved origin requires verified `owner_commentary` spans
with `origin_status="owner"` and `owner_relation="authored"`. Owner-origin text
excludes spans with external, unresolved or conflicting metadata. Adoption does not
authorize direct authorship.

`reported_expressions` exposes explicitly annotated external expressions in a
separate transient view. Each unit retains its original expression span, source
label, whole-source hash and annotated endorsement status. Speaker is unresolved
(`None`); adoption alone does not imply agreement. These are annotation-preserving
units, not automatic reported-speech extraction or generated claims. No source
text or canonical EvidenceLedger record is rewritten.

## Measured result

| Evaluation | Correct | False positives | False negatives |
|---|---:|---:|---:|
| New annotation-consuming contract | 20/20 | 0 | 0 |
| New unannotated owner-restatement challenges | 0/2 | 0 | 2 |
| Previous public set, explicit owner scope | 42/48 | 0 | 6 |
| Previous public set, original source scope | 24/48 | 24 | 0 |

All 24 previous false positives are excluded in explicit owner scope. Its six
remaining failures are `owner_restatement`: the old fixture annotates the quotation
but not the owner's restatement outside it. Treating every unannotated part of mixed
text as owner-authored would bypass the boundary; this implementation abstains.
The two new coverage challenges expose the same remaining limitation in English
and Russian. The expanded capability still does **not** pass the original 48/48 gate.

The [full artifact](owner_attribution_v1_results.json) records inputs, decisions,
reported units, per-case old/new scope results and nine LF-normalized file hashes.
The [original 48-case artifact](reported_attribution_v1_results.json) is unchanged.

Targeted regression suite: **47 passed** across owner-attribution, planned-slot,
relation guard and source-provenance tests. Checks include stale hashes, source
isolation, conflicting metadata, polarity, duplicate labels, disjoint spans,
endorsement versus adoption and enforcement in the generation runner using a fake
backend. `scripts/check_no_legacy_imports.py` also passes. No full-suite claim is made.

## Scope and remaining work

- The new mode is explicit. Existing plans default to `source`; wording alone does
  not activate it. Automatic selection of owner/report/endorsement scope by a
  question planner is not implemented or evaluated.
- English and Russian cases test F1 metadata/span policy. S6 still supports only
  its six registered English relation types; this adds no Russian relation parser.
- Span hashes establish text binding, not the correctness of supplied attribution.
  An incorrectly owner-labeled envelope can still admit reported speech. Nested
  reports, implicit endorsement and unannotated speaker boundaries are unresolved.
- The source-label guard does not prove the exact generated proposition or prevent
  misuse of another fragment in an otherwise eligible source. Claim-to-span checking
  remains necessary before broader answer-quality claims.
- These small synthetic cases were authored by the implementer and visible during
  development. They demonstrate the bounded contract, not blind generalization.

Next: freeze a span-level extraction evaluation for speaker, report cue, content,
owner restatement and explicit stance. Measure both false attribution and lost
owner coverage. Then connect verified extraction outputs to this boundary; retain
abstention for unresolved cases. Do not reuse these cases as unseen test evidence.

Reproduce from repository root with `PYTHONPATH=src` and a new output path:

```text
python scripts/audit_owner_attribution.py --output <new-result.json>
```

Exit 0 refers only to the mandatory 20-case annotation contract. Challenge failures
and the old set's remaining six false negatives are intentionally retained.
