# Explicit owner-attribution gate v1

Frozen before implementation on 2026-10-11. This is a bounded annotation-consuming
operation, not a natural-language attribution extractor.

## Contract

Add explicit `attribution_scope="direct_owner"` to frozen question requirements.
The default `source` retains existing S6 behavior. Never infer this scope from
English question wording. Return source decisions with inclusion/abstention reasons.
Missing or unresolved authorship must not count as owner evidence. Adoption or
endorsement must not substitute for authorship. Forwarded content is not treated as
direct owner evidence. Mixed/unresolved text requires verified owner-authored spans;
external and unresolved spans must remain excluded. Relation cues and their polarity
must be evaluated inside eligible text, never joined across disjoint spans.

Preserve explicitly annotated external expressions as source-bound reported units
with their endorsement status. An unknown speaker remains unknown; no parser or
identity inference is introduced. Nested reports without annotations remain opaque.
The units describe annotations, not independently verified semantic truth.

## Evaluation

The companion `owner_attribution_v1_cases.json` is frozen with this protocol before
implementation. It contains English and Russian F1 cases and two coverage challenges.
The mandatory annotation-consuming gate requires all contract cases to pass, zero
false positives and exact preservation of annotated expression/stance counts.
Coverage challenges test desired owner statements in mixed text without explicit
owner spans. Preserve their failures; do not relax the boundary to pass them.

Run the previous 48-case diagnostic through an explicit direct-owner adapter as a
regression comparison. Do not overwrite its original artifact or claim that its
untyped plan automatically activates the new scope. Keep the original source-scope
operation unchanged. Report lost eligibility as well as corrected false positives.

Unit tests must exercise stale span hashes, invalid scope, contradictory span
metadata, agreement versus adoption, source isolation, separated spans, and S6
polarity. These are public synthetic tests, authored by the implementer and visible
during implementation; they are not blind held-out or production accuracy estimates.
No private Q07 evaluation or model generation is authorized by this protocol.
