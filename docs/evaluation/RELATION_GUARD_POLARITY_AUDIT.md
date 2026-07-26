# S6 polarity and modality audit

Status: completed; preregistered scope intervention passed.

## Risk

`S6` currently recognizes explicit English relation cues. A surface cue does not
establish its relation when locally negated or presented only as a modal possibility.
Without a scope check, “not accepted” and “might replace” can become eligible support.

## Frozen audit

Eighteen source-only minimal pairs cover all six registered relations. Each relation
has one affirmative source, one locally negated source and one modal source. The
requirement and relation remain fixed within each triple.

The audit passes only if all six affirmative sources are eligible and all twelve
negated/modal sources are ineligible.

## Preregistered intervention

For each matched source cue:

1. inspect only the text from the previous clause boundary through the cue;
2. reject the match when `not`, `never` or `no` occurs in that local prefix;
3. reject the match when `may`, `might`, `could`, `would` or `possibly` occurs in the
   four tokens immediately before the cue;
4. accept the source if at least one cue match survives;
5. retain the existing fail-closed behavior for unknown requirement relations.

Clause boundaries are `.`, `;`, `:`, `!`, `?` and line breaks. The intervention does
not add relation cues, infer entities, or handle reported speech. Any failed
affirmative case or accepted negative/modal case rejects it. The baseline result is
recorded before implementation.

## Results

The unchanged baseline passed `12/18`. It incorrectly admitted six locally
negated/modal cues: `not confirmed`, `may be confirmed`, `may become subject to`,
`not retained`, `would be retained`, and `has not replaced`.

Four other negative/modal controls happened to pass because their inflected verbs did
not match the registered surface cue. They remain in the audit and are not treated as
evidence of scope awareness.

The preregistered local-prefix filter then passed `18/18`: all six affirmative cases
remained eligible and all twelve negated/modal cases became ineligible. The prior
twelve-case S6 relation gate also remains green.

## Decision

Promote the local polarity/modal filter as part of `S6`. Its scope is deliberately
bounded: it does not resolve reported speech, cross-clause negation, double negation,
conditionals about the relation itself, or non-English morphology. Those phenomena
require new frozen audits rather than cue changes on this set.
