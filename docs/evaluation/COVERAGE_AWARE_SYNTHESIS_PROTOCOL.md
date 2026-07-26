# Coverage-aware synthesis: public synthetic gate

Status: public synthetic gate completed; coverage contract rejected.

## Question

When retrieval already supplies several independently relevant, source-cited facets,
does one minimal coverage instruction improve required-facet recall over the current
one-shot instruction without increasing unsupported claims, citation errors, or
incorrect promotion of guards and alternatives?

This gate evaluates synthesis, not retrieval. Both arms receive the same frozen
question and the same source order. Gold facet roles are scorer-only data and are
never rendered into either prompt.

## Arms

- `baseline`: answer briefly from the supplied sources, cite supported claims, and
  abstain when evidence is insufficient.
- `coverage`: additionally perform a silent pre-answer check for distinct,
  independently relevant source-supported points. Preserve caveats, guards and
  alternatives in their proper role.

The exact strings are constants in `fvsc.evaluation.synthesis`. No chain of thought is
requested or stored.

## Public fixture requirements

The frozen set must contain only invented text and must not derive names, phrases or
events from the private dialogue. Every positive case has two or three independent
required facets. Across the set, include:

- optional context that is useful but not required;
- a conditional alternative that must not become the asserted outcome;
- a guard or correction that constrains a required facet;
- a plausible but unsupported prohibited facet;
- at least one insufficient-evidence case where abstention is correct.

Each facet has a stable id, role and acceptable source labels. Annotation of generated
answers records expressed facet ids and citations. It does not use lexical overlap as
a truth oracle.

## Metrics and gate

Report paired per-arm:

- macro required-facet recall;
- unsupported-facet rate;
- citation correctness;
- prohibited and role-promotion violations;
- abstention accuracy;
- prompt tokens, output tokens and latency.

Advance to the private Q07 diagnostic only if coverage improves macro required-facet
recall, introduces zero prohibited or role-promotion violations, does not reduce
citation correctness, and does not reduce abstention accuracy. Token and latency
changes are reported, not hidden. A failed gate is retained as a negative result; the
prompt is not tuned against individual private answers.

## Boundaries

Optional facets do not enter the required-recall denominator. Merely mentioning an
alternative or guard as ordinary positive prose is a role violation. Retrieval,
budgets, source order, model digest, seed and sampling options remain fixed between
arms. The frozen private Gold and its parent census are not modified.

## Runner

The paired public generation runner is:

```powershell
$env:PYTHONPATH='src'
python scripts/run_synthesis_gate.py `
  --model '<exact-local-tag>' `
  --model-digest '<sha256-from-ollama>' `
  --host 'http://127.0.0.1:11434' `
  --output '.fvsc/public-synthesis-gate-v1.json'
```

It refuses an absent model, a digest mismatch, a missing output directory, or an
existing output file. Case order is frozen and arm order alternates by case to
distribute warm-cache bias. The artifact contains public generated prose, telemetry,
and an empty review template. Facet observations require explicit review; the runner
does not infer semantic truth from lexical overlap.

## Result — public synthetic gate v1

The frozen run used `qwen2.5:14b-instruct-q4_K_M`, digest
`7cdf5a0187d5c58cc5d369b255592f7841d1c4696d45a8c8a9489440385b22f6`,
temperature `0`, seed `42`, and six paired cases.

| Metric | Baseline | Coverage |
|---|---:|---:|
| Macro required-facet recall | 1.000 | 1.000 |
| Mean unsupported-facet rate | 0.167 | 0.167 |
| Mean citation correctness | 1.000 | 0.933 |
| Abstention accuracy | 0.833 | 0.833 |
| Prohibited violations | 1 | 1 |
| Role-promotion violations | 0 | 0 |
| Prompt tokens | 2,564 | 2,810 |
| Output tokens | 536 | 552 |
| Mean wall seconds | 14.43 | 5.61 |

The gate **failed**. Required-facet recall was already saturated in the baseline and
did not improve. Both arms incorrectly asserted that zinc coating had been selected
in the insufficient-evidence case. The coverage arm also mentioned the conditional
Thursday alternative in its answer without representing it as a separately cited
claim, reducing citation correctness.

Latency is descriptive only: local model loading and cache state remain plausible
contributors even with alternating arm order. No speed claim is made.

This result rejects this minimal coverage instruction for promotion. It does not show
that coverage-aware synthesis is impossible; it shows that the tested instruction
does not solve abstention and provides no recall gain on this fixture set. Under the
registered gate, private Q07 is not repeated and the prompt is not tuned against it.
