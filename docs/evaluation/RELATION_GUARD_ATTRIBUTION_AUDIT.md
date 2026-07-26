# F1/S6 expression-boundary audit

Status: completed; preregistered F1 composition passed.

## Risk

A relation cue inside a verified quotation, lyric, AI output or translated external
span establishes at most what that expression says. The current planned-slot claim
contract has no typed reported-speech relation, so flattening such a cue into a direct
`evidence_bound` claim loses F1 attribution.

Plain text without a typed expression span remains unresolved and is not automatically
classified as quoted or external.

## Frozen audit

Twelve cases pair the same six registered S6 relations:

- one cue in ordinary source text;
- the same cue inside a verified external `ExpressionSpan(kind="quotation")`.

All six ordinary cases must remain directly eligible. All six expression-bound cases
must be ineligible for a direct claim. Every span is content-addressed and verifies
against the exact source text.

## Preregistered intervention

Extend cue evaluation with existing F1 spans:

1. verify every supplied span against the source text;
2. preserve the current polarity/modality test;
3. reject a surviving cue when its match overlaps any span whose kind is not
   `owner_commentary`;
4. retain cues outside spans and cues inside explicit `owner_commentary`;
5. do not infer new spans from punctuation or reporting verbs.

This only controls direct claim eligibility. It does not discard the source or deny
that a quoted assertion exists. A future typed reported-claim operation may expose
that distinction separately.

## Results

The surface baseline passed `6/12`: all six ordinary cues were eligible, but the same
six cues inside verified external quotation spans were also incorrectly eligible for
direct claims.

The preregistered F1 overlap filter passed `12/12`. It preserved all ordinary cues and
blocked all expression-bound cues. Unit coverage additionally verifies that:

- every span digest is checked against the exact source text;
- explicit `owner_commentary` remains directly eligible;
- the registered `S6` operation consumes the existing `SourceAttribution` envelope
  carried by prompt sources rather than a parallel authorship model.

## Decision

Promote verified expression-boundary exclusion as the `F1 → S6` composition for direct
claims. Quoted/external cues remain available to a future typed reported-claim
operation; they are not silently discarded or rewritten as owner statements. Plain
unannotated text remains unresolved, and punctuation is not used to invent spans.
