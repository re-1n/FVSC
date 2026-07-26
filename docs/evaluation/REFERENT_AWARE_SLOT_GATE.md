# Referent-aware support inside fixed answer slots

Status: public paired gate completed; candidate failed and was not promoted.

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

## Frozen result

The run used `qwen2.5:14b-instruct-q4_K_M`, digest
`7cdf5a0187d5c58cc5d369b255592f7841d1c4696d45a8c8a9489440385b22f6`,
temperature zero and seed 42.

| Metric | v1 | Referent-aware |
|---|---:|---:|
| Macro required-facet recall | 1.000 | 1.000 |
| Citation correctness | 1.000 | 1.000 |
| Unsupported-facet rate | 0.125 | 0.250 |
| Abstention accuracy | 0.875 | 0.750 |
| Prohibited violations | 0 | 2 |
| Prompt tokens | 2,084 | 2,844 |
| Output tokens | 602 | 653 |

Both arms completed all six positive cases. V1 wrongly treated a tasting scheduled
before a catering decision as something that “remains conditional.” The candidate
made the same error and additionally converted a colour-fastness test into acceptance
and lower cost into rejection in the adversarial mural case.

## Decision

Reject the candidate. It repaired no v1 miss, reduced abstention accuracy, doubled the
mean unsupported-facet rate and introduced two prohibited relation assertions. The
failure confirms that broader entity-role resolution in the prompt weakens the
relation boundary. The next candidate must validate the requested relation separately
from entity nomination, with negative controls for tests, prices, plans, chronology
and pending decisions. Do not tune another referent prompt on these cases.
