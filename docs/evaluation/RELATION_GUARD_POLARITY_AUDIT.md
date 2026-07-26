# S6 polarity and modality audit

Status: fixtures and intervention preregistered; baseline not yet run.

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
