# Typed relation-support guard gate

Status: public gate preregistered; generation not yet run.

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
