# ADR-007: Semantic computation uses a provenance-grounded atlas of relation-conditioned views

- **Status:** Accepted (2026-07-15)
- **Deciders:** Rein

## Context

The whitepaper does not describe only one matrix. It already separates typed
`S -> V -> O` Judgments, directed containment, relation-dependent transforms,
tensor factors, graph projection, contextual facets, temporal traces, metaphor
mappings, and the L0–L3 interpretation spectrum. Its density-matrix proposal tried
to make all of those operations coexist in one compact algebraic object.

That unification has not been validated. Current evidence shows three different
limits:

- density and ContainerCore have not beaten simpler baselines on their registered
  tasks [ADR-002, ADR-003];
- private Gold 001–015 retrieval favors the lexical floor over exact and fusion
  arms;
- different semantic relations require different inductive biases. Similarity,
  directed implication, hierarchy, temporal change, contradiction, and uncertainty
  do not in general share one useful metric.

This does **not** prove that matrices, tensors, containers, or a unified mathematical
space cannot encode the data. It shows that representational capacity alone is not a
reason to privilege one coordinate system or one scoring operation. The missing
question is which representation improves which owner-validated operation.

## Decision

FVSC treats its computational meaning map as a **provenance-grounded semantic
atlas**: a versioned family of replaceable, relation-conditioned views materialized
from the same canonical EvidenceLedger.

1. **Evidence remains canonical.** Source revisions, EvidenceEvents, exact Judgments,
   lifecycle, and provenance are the common substrate [ADR-001, ADR-006].
2. **No derived representation is universally privileged.** Graph, explicit
   containers, contextual vectors, regions/order embeddings, hyperbolic coordinates,
   distributions, density operators, temporal trajectories, and future backends are
   candidate views, not competing sources of truth.
3. **Scores are relation-conditioned.** FVSC may compute
   `s_r(A, B | context, time, layer)` for a declared relation or query family `r`.
   The score need not be a mathematical distance: it may be asymmetric, typed,
   non-transitive, or constraint-valued.
4. **A concept is not canonically one point or one matrix.** It is identified by its
   evidence-backed usages, typed relations, contexts, temporal history, and owner
   review. A view may assign it a point, region, distribution, operator, or trajectory
   for a specific operation.
5. **Views compose through evidence identity and typed contracts.** They do not need
   a lossy conversion into one another. Every result carries view/version, parameters,
   evidence ids, and a derivation chain.
6. **A query is an operator plan.** Cheap views nominate candidates; explicit
   relations and constraints verify or reject paths; an LLM may verbalize only the
   selected cited evidence. The LLM is not the atlas and does not become owner
   evidence [ADR-004].
7. **Density keeps a narrower, legitimate role.** It remains an optional view for
   context-local mixture, uncertainty, ambiguity, and future order-effect tests. An
   eigenvector is a principal direction of a constructed state, not automatically an
   interpretable facet. A spectral entropy is a state-mixture statistic, not by itself
   proof of human polysemy.
8. **Container semantics remain an explicit directed view.** Mutual relations are
   represented as two independently evidenced directed relations. Recursive
   propagation is a query/materialization operation, not proof that the stored object
   is mathematically fractal.

The term *atlas* is an engineering and mathematical analogy: different charts expose
different computable structure while retaining stable identity. This ADR does not
claim that personal meaning is a smooth manifold or that transition maps between all
views already exist.

## Reuse and replacement of whitepaper work

This decision begins with the whitepaper's existing work rather than restarting from
an empty design. It does not grant any historical construct permanent status:

- the Judgment and provenance contracts survive unchanged;
- exact verbs, negation, modality, intensity, conditions, authorship, time, and
  interpretation layer remain first-class;
- directed containers, relation transforms, tensor factorization, graph views,
  recursive propagation, temporal decay/consolidation, and metaphor mappings enter
  the atlas as candidate operations and may be corrected, replaced, or retired;
- the whitepaper's `H_semantic x H_relational x H_contextual` proposal becomes one
  possible factorized chart rather than the mandatory universal substrate;
- the existing density and ContainerCore implementations remain available for
  controlled comparison.

## Promotion rule

A new view is implemented and promoted only for a registered query family with:

1. an explicit hypothesis and supported operations;
2. a simple baseline and an ablation;
3. owner-gold positive, context, negative, and forbidden-composition evidence;
4. citation resolution and abstention checks;
5. measured quality, latency, update cost, and storage cost;
6. a materializer version and a complete route back to canonical evidence.

Failure to beat the baseline is a valid result. It does not trigger a rewrite of the
ledger and does not justify adding all other candidate geometries.

For an incumbent and replacement evaluated on the same frozen protocol:

- promote the replacement only for the operation and cost envelope it demonstrably
  improves;
- retain both only when each has a distinct measured use;
- prefer the simpler implementation when results are tied within uncertainty;
- deprecate a dominated view from active query plans while preserving its benchmark,
  fixtures, and decision history.

Whitepaper provenance is a reason to test a construct carefully, not a reason to keep
it after controlled evidence favors a better design.

## Consequences

- `ContainerCore` is no longer described as the singular semantic-structure layer.
- The lexical floor and exact graph can remain production views while richer views are
  evaluated independently.
- A universal `distance(A, B)` or `rho(concept)` is not part of the core contract.
- Research can test hyperbolic, region/order, relation-transform, distributional, or
  operator views without migrating canonical memory.
- Claims of uniqueness, universal semantic capture, or superiority require direct
  comparative evidence and are prohibited before it exists.

## Rejected alternatives

- **One Euclidean embedding for every relation:** compact, but its symmetric geometry
  is not an adequate contract for all directed and logical operations.
- **One density operator as the definition of every concept:** retains useful mixture
  operations but overstates what the current construction and metrics establish.
- **ContainerCore as the privileged semantic layer:** preserves directed structure but
  does not subsume similarity, uncertainty, temporal change, and open interpretation.
- **Run an LLM over the complete corpus for every query:** loses the intended cheap
  index, deterministic floor, and localized error analysis.

[ADR-001]: ADR-001-evidence-ledger-is-canonical.md
[ADR-002]: ADR-002-containercore-is-experimental.md
[ADR-003]: ADR-003-density-is-optional-local-state.md
[ADR-004]: ADR-004-antourage-outputs-are-not-owner-evidence.md
[ADR-006]: ADR-006-semantic-compression-is-referentially-reversible.md
