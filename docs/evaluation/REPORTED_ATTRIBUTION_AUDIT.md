# Public reported-attribution diagnostic v1

Status: protocol frozen before execution, 2026-10-11.

## Question and scope

Can the current registered F1/S6 composition safely select evidence for a question
about what the owner **directly states**, when attribution varies? This extends the
previous verified-expression-span audit into documented unsupported territory. It is
a diagnostic capability test, not a promotion gate or an end-to-end user-answer test.
S6 returns candidate source labels, not identified speakers or generated claims. A
false positive here is unsafe eligibility for the requested scope, not an observed
hallucinated answer. No language model or private source is used.

## Frozen cases and gold

48 authored public synthetic cases: six existing English relation types crossed with
eight attribution families. Each relation uses identical proposition wording across
families. The texts concern fictional workshop, council and transport arrangements.

| Family | Direct owner eligibility | Reason |
|---|---|---|
| owner_direct | true | Owner authored the proposition |
| annotated_quote | false | Verified external wording; selection is not authorship |
| endorsed_quote | false | Owner agrees, but the proposition's wording remains attributed to Mira |
| owner_restatement | true | Owner explicitly repeats the proposition outside the external span |
| indirect_report | false | Owner reports Mira's assertion, without adopting it as a direct assertion |
| unannotated_quote | false | Explicitly reported wording but no supplied expression annotation |
| unknown_author | false | Metadata leaves authorship unresolved |
| non_owner_author | false | Metadata identifies a different author |

Endorsement is a separate answer type: the endorsed-quote gold does not deny owner
agreement. This test asks for direct owner assertions only. Holder/endorsement
extraction and usefulness of a future reported-claim operation are not measured.
All source metadata is synthetic oracle input; no attribution extractor is evaluated.

## Procedure and acceptance criteria

1. Commit this protocol, fixture builder and runner before execution.
2. Run unchanged `PUBLIC_RELATION_SUPPORT_GUARD.compile` on one source per case and a
   frozen direct-owner requirement. Gold labels stay outside the operation input.
3. Verify every annotated span, case identity and balanced family counts.
4. Record every prediction, the full public inputs, per-family totals, false positives,
   false negatives, source commit and hashes normalized to LF.
5. The expanded capability passes only at 48/48 with zero false positives and zero
   false negatives. No aggregate improvement can excuse an attribution violation.
6. Preserve the result regardless of outcome. Do not modify cues or gold on this set
   to make it pass; any intervention needs a separate frozen evaluation.

Run from repository root with `PYTHONPATH=src`:

```text
python scripts/audit_reported_attribution.py --output docs/evaluation/reported_attribution_v1_results.json
```

Exit code 1 means the capability gate failed; schema/span errors raise separately.
The result file is created exclusively and never overwritten.

Rationale: [academic review](../research/ACADEMIC_PRIOR_ART_2026-10.md),
[prior F1/S6 audit](RELATION_GUARD_ATTRIBUTION_AUDIT.md), and
[bounded S6 polarity audit](RELATION_GUARD_POLARITY_AUDIT.md).
