# Referent-aware support inside fixed answer slots

Status: public paired gate preregistered; generation not yet run.

## Frozen diagnosis

The deterministic boundary compiler preserved the missed `R2` obligation in the
diagnostic boundary-plus-slot transfer. The v1 filler nevertheless marked it
unsupported because “what remains conditional” named a role but not the source-side
entity occupying that role. This separates implicit-referent support from answer-slot
discovery.

The diagnostic question and sources are frozen and excluded from this gate.

## Candidate

Both arms receive identical compiled `R1/R2` requirements and sources. The candidate
adds one bounded instruction: resolve the explicit or implicit requested role, and
accept a source-named entity only when that source explicitly states the requested
relation. Topic, chronology, proximity, proposals and plausible candidates remain
insufficient. No question, source or answer text is rewritten and no QDMR step may
create or remove a slot.

## Frozen public fixtures

Eight new cases cover conditional, accepted/declined and retained/replaced implicit
referents. Six cases support both slots. Two adversarial cases mention plausible
entities without establishing either requested relation and require full abstention.
The old v1 and diagnostic fixtures are not reused.

The frozen Qwen digest, temperature zero and seed 42 are unchanged. Arm order
alternates per case.

## Preregistered decision

Promote the referent instruction only if all conditions hold:

- no schema error in either arm;
- candidate macro required-facet recall is at least v1 and at least `0.917`;
- candidate citation correctness is `1.000`;
- candidate abstention accuracy is `1.000`;
- candidate unsupported-facet rate is `0`;
- candidate has zero prohibited and role violations.

The recall floor permits at most one missed required facet among the six positive
two-slot cases after macro averaging. Latency and tokens are reported but do not decide
this small gate. A tie retains v1 unless the candidate repairs at least one v1 miss
without a safety regression.

Run and review artifacts remain ignored under `.fvsc/`. Do not run private Q07 from
either outcome.
