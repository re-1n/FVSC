# Answer–claim consistency and missing-link abstention

Status: public synthetic gate passed.

## Failure classification

The first public coverage gate exposed a downstream failure that required-facet recall
does not describe. In the insufficient-evidence coating case, both arms asserted in
`answer` that zinc had been selected. Their only structured claim stated merely that
zinc passed a salt-spray test. Thus:

1. the free-form answer contained a proposition absent from the cited claims; and
2. the cited claim described candidate evidence but did not resolve the relation
   requested by the question (`selected`).

This is an answer/claim consistency and missing-link abstention failure. It is not a
retrieval failure: all supplied sources were present, and none stated a selection.

## Frozen public fixture family

`PUBLIC_CONSISTENCY_FIXTURES` contains eight invented cases:

- four positive controls with an explicit target relation plus a second required
  facet;
- four insufficient-evidence cases where nearby evidence must not be promoted into
  selection, causation, approval, or completion;
- matched distractors involving test success, temporal proximity, lower cost,
  budgeting, available parts, and future plans.

The texts do not derive from the private dialogue. Case order, source order, questions
and facet Gold are frozen before an intervention is specified or run.

## Next registered design task

Compare the current baseline with one claim-first consistency operation. The operation
must satisfy both invariants:

- every proposition rendered in the user-facing answer is represented by a cited
  structured claim or by an explicit abstention status;
- evidence about a candidate, precursor, plan, test, or temporal neighbour is not
  treated as evidence for the target relation unless a source states that relation.

The implementation should prefer deterministic rendering from validated claims over
duplicating independently generated prose. A self-reported model confidence or
`answers_question=true` flag is insufficient by itself.

Before generation, freeze the exact output schema, renderer, model digest, seed,
sampling settings, scoring and gate. Report positive-control facet recall, prohibited
relation violations, abstention accuracy, citation correctness, tokens and latency.
Do not repeat private Q07 unless this public gate passes.

## Frozen run configuration

- model: `qwen2.5:14b-instruct-q4_K_M`;
- digest: `7cdf5a0187d5c58cc5d369b255592f7841d1c4696d45a8c8a9489440385b22f6`;
- temperature: `0`;
- seed: `42`;
- context: `8192`;
- maximum output: `768`;
- paired case order with alternating arm order.

The model receives identical question/source JSON in each pair. The baseline returns
its existing independent `answer` and claims. The claim-first arm returns only
`status` and claims; its answer is rendered after schema validation.

## Result — public claim-first gate v1

| Metric | Baseline | Claim-first |
|---|---:|---:|
| Macro required-facet recall | 1.000 | 1.000 |
| Mean unsupported-facet rate | 0.375 | 0.000 |
| Mean citation correctness | 1.000 | 1.000 |
| Abstention accuracy | 0.625 | 1.000 |
| Prohibited relation violations | 2 | 0 |
| Schema errors | 1 | 0 |
| Prompt tokens | 1,447 | 1,791 |
| Output tokens | 488 | 264 |
| Mean wall seconds | 4.85 | 3.27 |

The gate **passed**. Claim-first preserved all positive-control required facets and
citations while abstaining on all four missing-link cases. The baseline asserted zinc
selection and north-proposal approval without source evidence, and separately stated
that no valve replacement was complete when the sources did not establish that
conclusion. One baseline output also combined `free_generation` with a citation and
was retained as a schema error rather than normalized.

The intervention increases prompt cost by 344 tokens across the eight cases and
reduces output by 224 tokens. Latency remains descriptive because local cache and
model-load effects are not eliminated by arm alternation.

This is one public synthetic fixture family, one model, and one seed. It validates a
single private Q07 diagnostic under the frozen claim-first operation; it does not
establish general superiority or authorize rewriting the private Gold.
