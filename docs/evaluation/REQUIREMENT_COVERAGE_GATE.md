# Requirement-to-claim coverage gate

Status: held-out public gate completed; candidate rejected.

## Motivation

Claim-first deterministic rendering passed a missing-link abstention gate but
over-abstained on paraphrastic positive relations in two coverage atlases. Atlas v2
did not select conditional scope or distributed rationale individually. Their shared
failure is relation normalization against a multi-part question.

## Candidate operation

The candidate decomposes each question into `R1…Rn`. Every requirement has:

- a description;
- `supported` or `unsupported` status;
- indices of structured cited claims that answer it.

Every claim must be evidence-bound and referenced by at least one supported
requirement. Unsupported requirements cannot reference claims. Overall
`answered/partial/insufficient` status is validated against the requirement statuses.
User-facing prose is rendered only from claims, with explicit partial/insufficient
markers.

Semantic paraphrase is allowed. Candidate evidence, tests, precursors, future plans,
lower cost and temporal proximity still do not establish selection, causation,
approval or completion.

## Held-out fixtures

Twelve new invented cases were frozen after atlas v2:

- eight positive multi-requirement cases spanning paraphrastic condition, rationale,
  temporal contrast, delayed action, acceptance boundary, transfer constraints,
  format and modality;
- four missing-link abstention cases for selection, causation, approval and
  completion.

No v1/v2 atlas text or private dialogue text is reused.

## Frozen run and gate

The run uses `qwen2.5:14b-instruct-q4_K_M`, digest
`7cdf5a0187d5c58cc5d369b255592f7841d1c4696d45a8c8a9489440385b22f6`,
temperature `0`, seed `42`, context `8192`, output limit `768`, identical source
payloads and alternating arm order.

The requirement arm passes only if:

- positive required-facet recall does not fall below baseline;
- all held-out case classifications, including four abstentions, are correct;
- prohibited and role-promotion violations are zero;
- citation correctness does not fall below baseline;
- schema errors are zero.

Tokens and latency are reported. The gate does not authorize private Q07 reuse.

## Result

| Metric | Baseline | Requirement coverage |
|---|---:|---:|
| Macro required-facet recall | 1.000 | 0.500 |
| Mean unsupported-facet rate | 0.250 | 0.000 |
| Citation correctness | 1.000 | 1.000 |
| Held-out classification accuracy | 0.750 | 0.417 |
| Prohibited violations | 2 | 0 |
| Schema errors | 0 | 6 |
| Prompt tokens | 2,014 | 4,030 |
| Output tokens | 872 | 1,164 |

The gate **failed**. The requirement arm remained conservative but emitted six
schema-invalid maps and seven wrong overall statuses. Effective positive recall fell
to 0.500. Several invalid outputs contained semantically correct claims but disagreed
on requirement status, claim linkage or overall status; fail-closed rendering
correctly withheld them.

The baseline again inferred selection and approval from test/review evidence and made
one unsupported no-completion statement.

The rejected candidate combined question decomposition, claim synthesis and indexed
many-to-many linkage in one model output. The next controlled ablation must isolate
these responsibilities: freeze answer requirements as input and request exactly one
supported/unsupported slot per requirement, with no model-generated indices. Such an
ablation tests synthesis capacity only and cannot promote an automatic planner.
