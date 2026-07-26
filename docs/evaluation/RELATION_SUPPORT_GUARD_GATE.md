# Typed relation-support guard gate

Status: public gate passed; guard promoted only for the six registered relation types.

## Motivation

The rejected referent-aware prompt preserved positive recall but weakened the boundary
between an entity and the relation requested of it. Tests became acceptance, lower
price became rejection, and chronology became conditionality. The next candidate
therefore validates relation support independently of entity nomination.

## Candidate

The candidate is a narrow, deterministic English derived view over already compiled
answer slots. It registers six relation types:

- `confirmed`;
- `conditional`;
- `accepted`;
- `declined`;
- `retained`;
- `replaced`.

Each type has a small explicit source-cue set. A source label becomes eligible for a
slot only when its text contains a cue for that slot's requested relation. Generated
claims citing an ineligible label are deterministically demoted to unsupported before
answer rendering. Unknown or multiply identified relation types fail closed.

The guard neither chooses an entity nor generates prose. It does not claim
language-general semantic entailment. It is a replaceable high-precision control for
this public English gate.

## Frozen gate

Twelve new cases are frozen before generation:

- six positive cases, two each for confirmed/conditional, accepted/declined and
  retained/replaced;
- six full-abstention controls covering passed tests, price, surveys, chronology,
  availability, dry runs, budgets, pending votes and future implementation.

The v1 model generates once per case. The raw and guarded arms share the exact same
generation and telemetry; the only arm difference is deterministic eligibility
enforcement. This removes sampling and warm-cache variance.

## Preregistered decision

Promote the guard for these registered relation types only if:

- neither arm has a schema error;
- guarded macro required-facet recall equals v1 and is `1.000`;
- guarded citation correctness is `1.000`;
- guarded abstention accuracy is `1.000`;
- guarded unsupported-facet rate is `0`;
- guarded prohibited and role violations are zero;
- the guard corrects at least one v1 safety error.

Any positive claim demoted by the guard rejects the candidate. Tokens and latency are
reported once because generation is shared. The old referent and private Q07 fixtures
are excluded. Do not widen the cue lexicon after observing the run.

## Frozen result

The run used `qwen2.5:14b-instruct-q4_K_M`, digest
`7cdf5a0187d5c58cc5d369b255592f7841d1c4696d45a8c8a9489440385b22f6`,
temperature zero and seed 42.

| Metric | v1 | Relation guard |
|---|---:|---:|
| Macro required-facet recall | 1.000 | 1.000 |
| Citation correctness | 1.000 | 1.000 |
| Unsupported-facet rate | 0.250 | 0.000 |
| Abstention accuracy | 0.750 | 1.000 |
| Prohibited violations | 4 | 0 |
| Schema errors | 0 | 0 |

All six positive answers were unchanged. The guard corrected all three raw-v1
negative-case failures: test/price interpreted as acceptance/rejection, permit
chronology interpreted as conditionality, and room availability interpreted as
confirmation. Because arms share the same twelve model generations, tokens and latency
are identical and are not attributed to the guard.

## Decision

Promote the guard as a high-precision control only for `confirmed`, `conditional`,
`accepted`, `declined`, `retained` and `replaced` in the registered English operation.
This is not a general entailment layer and does not authorize silent cue expansion.
New relations or paraphrastic cues require their own held-out positive and adversarial
gate. The next step is integration at the planned-slot boundary behind explicit
operation registration, followed by regression tests proving unregistered slots still
fail closed.
