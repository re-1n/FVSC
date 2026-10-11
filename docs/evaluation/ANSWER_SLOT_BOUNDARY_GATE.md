# Deterministic answer-slot boundary gate

Status: public v1 passed; licensed for a new held-out planner-plus-slot gate.

## Question

Can explicit multi-part answer obligations be compiled from question grammar without
letting a generation model decide which planning steps count as answer requirements?

## Operation

The compiler receives only the question. It emits contiguous `R1..Rn` slots for four
registered boundary classes:

- former/current states requested by an explicit change question;
- separately requested clauses;
- a primary request plus an explicit condition, constraint, reason or rationale;
- explicitly requested two-step or two-stage roles.

It sees no source, answer, source identifier, retrieval state or QDMR output. It does
not infer support or formulate prose. Questions outside the registered grammar fail
closed instead of collapsing to one guessed requirement.

Validated plans adapt directly to the existing `FrozenQuestionPlan` contract. QDMR-like
steps may be added later as internal dependency structure, but they cannot create,
merge or suppress the deterministic answer slots.

## Frozen public gate

`PUBLIC_ANSWER_SLOT_GATE_FIXTURES` contains twelve new question-only cases: three
temporal pairs, three primary/coordinated requests, three explicit contrast clauses
and three ordered two-role requests. They are distinct from the reused v1 planner
development questions.

Run:

```powershell
$env:PYTHONPATH = "src"
python scripts/run_answer_slot_boundary_gate.py
```

Result: **12 / 12 exact boundary-kind and ordered-role matches**. Four unregistered
single-slot or ambiguous questions also failed closed in unit tests.

As a diagnostic only, the compiler covers all eight earlier positive synthesis
questions except the accept/decline wording; all four earlier negative single-slot
questions fail closed. Those reused cases are not promotion evidence and were not used
to change the frozen v1 result.

## Decision

The boundary compiler passes its narrow gate. It does not establish semantic parsing
or end-to-end answer quality. The next experiment must freeze new sources and facet
Gold, compile slots before source access, fill exactly those slots with the existing
planned-slot operation, and score slot recall, support status, citations, prohibited
relations, abstention, latency and tokens. Do not rerun private Q07.

## Diagnostic boundary-plus-slot transfer

A twelve-case source set was constructed for the frozen questions: ten supported
two-slot cases and two cases where neither requested step was established. The
existing planned-slot prompt ran with the same frozen Qwen model digest and seed.
Because this source fixture tranche had not yet been committed when generation began,
the result is explicitly diagnostic and cannot promote the combined operation.

| Metric | Result |
|---|---:|
| Macro required-facet recall | 0.950 |
| Citation correctness | 1.000 |
| Unsupported-facet rate | 0.000 |
| Abstention accuracy | 1.000 |
| Prohibited / role violations | 0 / 0 |
| Schema errors | 0 |

Nine positive cases were complete, both negative cases abstained, and one positive case
was partial. The preserved `R2` slot asked what remained conditional, but the filler
did not link that implicit referent to the source-supported second delivery. This is no
longer a slot-boundary loss. It localizes the next public task to referent-aware
relation support inside an already fixed slot. Do not alter the v1 question, source,
prompt or review after observing this result.
