# ADR-006: Semantic compression is referentially reversible, not text-invertible

- **Status:** Accepted (2026-07-14)
- **Deciders:** Rein

## Context

FVSC compresses personal discourse into structures that are cheap to traverse and
compare: evidence events, Judgments, graphs, containers, density states, and cited
interpretation proposals. The word *reversible* is ambiguous here. It can mean either:

1. reconstruct the original wording from the compressed map alone; or
2. trace every material semantic claim back to the exact source evidence that licensed
   it.

These are different requirements. A semantic map deliberately discards surface-form
details that are irrelevant to a particular computation. In general, many different
texts can express the same mapped relation, so the compression function is many-to-one
and has no unique textual inverse.

## Decision

FVSC requires **referential reversibility**, not **text invertibility**.

- Original sources and their revision history remain canonical and are stored outside
  replaceable semantic projections.
- Every material map element must retain enough provenance to resolve its evidence:
  source id, revision, locator or character span, integrity hash, and derivation chain
  where applicable.
- The semantic map is not required to contain enough information to reconstruct the
  original bytes or wording by itself. Requiring that would turn the map into a
  lossless archive and defeat its role as computational meaning compression.
- Rendering a map back into natural language is **generative unfolding**: a new,
  source-cited, defeasible explanation. It must never be represented as the recovered
  original text.
- If a portable standalone export must reproduce source text without access to the
  source vault, it may carry a separate content-addressed source pack. That pack is an
  archive paired with the map, not part of the semantic representation.

Formally, for sources `S`, map `M = C(S)`, and provenance index `P`, FVSC does not
require an inverse `C^-1(M) = S`. It requires a resolver
`resolve(M_element, P, S) -> cited source spans` while the referenced source revision is
retained.

## Consequences

- Semantic backends can remain compact, task-specific, and replaceable.
- The system can always distinguish quoted source text from generated paraphrase.
- A missing or deleted source must produce an explicit unresolved citation or
  abstention, never an invented reconstruction.
- Revision and span hashes prevent a newer source body from being presented as the
  evidence for an older map element.
- Evaluation tests citation resolution and meaning fidelity; verbatim regeneration is
  not a semantic-quality metric.

