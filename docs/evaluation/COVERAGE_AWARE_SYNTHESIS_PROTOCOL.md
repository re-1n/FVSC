# Coverage-aware synthesis: public synthetic gate

Status: preregistered protocol; no result recorded yet.

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
