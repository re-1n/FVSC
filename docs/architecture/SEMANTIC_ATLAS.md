# Provenance-grounded semantic atlas

> **Status:** accepted architectural direction; individual semantic views remain
> experimental until promoted by owner-gold evaluation. See [ADR-007].

## The corrected hypothesis

The original FVSC hypothesis survives in a more precise form:

> Human-expressed personal meanings can be mapped into compact mathematical
> representations that make selected relations cheap to search and compare. There is
> currently no evidence that one coordinate system, one object type, or one universal
> distance preserves every relation that matters.

FVSC therefore seeks a computable **semantic atlas**, not a single mandatory semantic
space. Each view is a coordinate chart for a declared family of operations. The common
identity underneath every chart is canonical evidence and provenance.

This distinction is about inductive bias, not raw encoding capacity. A sufficiently
large matrix or tensor can encode arbitrary finite data. That fact does not make its
geometry, axes, eigenvectors, or multiplication semantically useful. A representation
earns a role only when its operations recover owner-validated relations better or more
cheaply than a simpler baseline.

## What the whitepaper already contributed

The atlas starts from the whitepaper rather than discarding its work unread. This is
not a compatibility promise: every construct below is retained, translated, replaced,
or retired according to a registered comparison.

| Existing whitepaper construct | Retained or translated role | Correction |
|---|---|---|
| Exact `S -> V -> O` plus quality, modality, intensity, time, condition | Typed relational trace and common input to views | The trace and its source span are more stable than any coordinate encoding |
| Concept as a container of usages and relations | Explicit directed-container view; operational account of personal use | A container is one lens on meaning, not an exhaustive definition of a concept |
| Verb as relation and reified concept | Multi-relational graph plus evidence-backed relation object | Relation identity must not be collapsed into a generic similarity score |
| Mutual asymmetric nesting | Two separately evidenced directed relations | It need not be literal mutual set inclusion inside one geometry |
| Role-dependent rotations and `transform(rho, relation)` | Relation-conditioned transformations | Hash-derived QR rotations are deterministic baselines, not learned or justified semantics |
| Density operator from weighted projectors | Local mixture/uncertainty/ambiguity view | The operator is optional; its spectrum is not self-interpreting |
| Eigenvectors as facets | Candidate principal directions linked back to contributing usages | A direction becomes a named facet only after evidence attribution and validation |
| `H_semantic x H_relational x H_contextual` | Factorized chart and query projection | A tensor product is one candidate chart, not proof of a universal space |
| Graph as a view | Exact and derived traversal view | It can be materialized directly from the ledger, not only from density overlap |
| Recursive deepening | Bounded, relation-conditioned propagation over explicit paths | Convergence needs a contractive update; self-similarity alone does not establish fractality |
| Contradiction and time/decay/consolidation | Temporal event view and trajectories | Historical evidence is never decayed out of the ledger; decay affects query state only |
| L0–L3 spectrum | Epistemic policy dimension for every view and result | Higher layers remain defeasible and cannot silently become owner evidence |
| Metaphor mappings | Evidence-linked source-to-target mapping proposals | Detection and interpretation are separate, owner-reviewable operations |
| Hyperbolic space as a future direction | Candidate hierarchy chart | It is evaluated only on hierarchy-specific tasks |

The central surviving insight is **structured plurality under provenance**: the same
utterance may participate in a temporal trajectory, a metaphor mapping, a directed
relation, and a contextual similarity neighborhood without any one of those becoming
the whole meaning of the utterance.

## Formal contract

Let `E` be one immutable active projection of the append-only EvidenceLedger. A semantic
atlas is a family of materialized views:

```text
A(E) = { V_i(E; version_i, parameters_i) }
```

Every `V_i` declares:

- the concepts/usages and evidence revisions in its domain;
- the relation or query families it supports;
- its coordinate/state type and valid operators;
- its context, time, author, and interpretation-layer policy;
- its materializer version and parameters;
- how every material result resolves to evidence and derivation steps;
- the benchmark and baseline that can falsify its usefulness.

For a requested relation `r`, FVSC computes a score or constraint:

```text
s_r(A, B | context, time, author, layer)
```

`s_r` is deliberately not named `distance`. Similarity may be symmetric; implication,
containment, causation, metaphor mapping, and continuation are normally directed.
Contradiction may depend on modality and time. Some query families return paths or
logical constraints rather than a scalar.

The evidence-grounded identity of a concept is better described as:

```text
C = (usages, typed relations, contexts, temporal trace, provenance, owner review)
```

A view may assign `C` a point, region, distribution, matrix, subspace, or trajectory,
but that coordinate object is disposable and versioned.

## Candidate views by operation

This table is a research menu, not an implementation checklist.

| Operation | Lowest-cost current view | Candidate richer view | Required evaluation |
|---|---|---|---|
| Exact attribution and relation lookup | Evidence/Judgment index | typed multi-relational graph | span/citation precision, owner relation validity |
| Lexical and paraphrase candidate retrieval | character n-grams | contextual usage embeddings | recall, forbidden hits, latency, corpus-size scaling |
| Directed inclusion or entailment | explicit directed edges | regions, order embeddings, operator inclusion | direction accuracy, transitivity cases, abstention |
| Hierarchy | explicit paths | hyperbolic chart | hierarchy reconstruction and generalization |
| Relation patterns | typed edges | relation-specific transforms or complex rotations | symmetry, antisymmetry, inversion, composition |
| Ambiguity and contextual mixture | evidence clusters | distributions or density operators | owner-labeled sense/context separation and ablations |
| Temporal change | timestamped ledger slices | trajectories/change-point views | ordering, phase boundary, contradiction attribution |
| Metaphor | cited mapping proposal | source/target relational subgraphs | owner meaning fidelity, literal/metaphoric separation |
| Logical multi-hop query | exact constrained traversal | query embeddings or symbolic algebra | answer set, negation, forbidden composition, proof path |

The whitepaper density backend remains especially relevant to ambiguity, local state,
and possible non-commutative order effects. Hyperbolic, box/order, and complex relation
models are examples of useful inductive biases demonstrated in neighboring research;
none is assumed to solve personal semantics without FVSC-specific evidence.

## Query execution

A query is compiled into a small plan rather than answered by one universal nearest
neighbor operation:

1. **Scope** — resolve author, time interval, source kind, interpretation layer, and
   whether adopted external wording is allowed.
2. **Nominate** — lexical or contextual views retrieve a high-recall candidate set.
3. **Expand** — exact reply/time/discourse or typed semantic paths add bounded context.
4. **Verify** — relation-specific views and forbidden-composition constraints score or
   reject candidate paths.
5. **Resolve** — every surviving claim is attached to exact source revisions/spans.
6. **Unfold** — an LLM may verbalize the result as a cited, defeasible proposal.
7. **Review** — owner assessment calibrates the view without rewriting source history.

This makes computational economy measurable. Expensive models operate on tens of
cited candidates rather than the entire corpus, while deterministic indexes retain a
reproducible floor.

## Cross-view composition rules

- Shared evidence ids and revision hashes establish identity across views.
- Context is never inferred merely from adjacency; reply and time nominate context but
  do not prove semantic composition.
- A score from one view cannot silently become an edge in another. Promotion requires
  a typed derivation event or owner-reviewed proposal.
- View-specific uncertainty remains attached to the view; scores with different
  meanings are not averaged without a registered fusion rule.
- A generated explanation cites source evidence, not a coordinate as if it were an
  utterance.
- Removing or replacing a view cannot destroy the ledger or owner assessments.

## Mathematical cautions carried into implementation

1. The legacy overlap ratio
   `Tr(rho_A rho_B) / Tr(rho_A)` is not guaranteed to lie in `[0, 1]` for arbitrary
   unnormalized positive semidefinite operators. Its numerator is symmetric and part
   of its directional effect comes from evidence mass. It must not be documented as a
   universal bounded containment probability.
2. Operator inclusion and relative-entropy scores in `semantic/metrics.py` are better
   specified shape comparisons, but they remain hypotheses until a relation-specific
   benchmark validates them.
3. Spectral entropy measures mixture in the constructed state. Calling it polysemy
   requires evidence that the mixture corresponds to owner-recognized senses rather
   than parser noise, relation mixing, or arbitrary basis construction.
4. Eigendecompositions are not uniquely oriented inside degenerate eigenspaces. Facet
   explanations must therefore cite contributing usages instead of naming an axis by
   inspection alone.
5. Recursive propagation converges only under stated bounds on the complete update
   operator. `0 < alpha < 1` is not a standalone proof if aggregation or transforms can
   amplify state.
6. Deterministic materialization still contains inductive bias: extraction rules,
   seed vectors, weights, thresholds, and owner feedback are design and calibration
   signals even when no gradient training occurs.
7. A stored sum of projectors has provenance only because FVSC separately stores its
   contribution records. A matrix decomposition by itself is generally not a unique
   recovery of the original Judgments.

## Incremental migration

No canonical data migration is required.

1. Keep EvidenceLedger, SourceDocument, Judgment, citation, owner-review, lexical, and
   exact-relation contracts unchanged.
2. Rename the architecture's singular ContainerCore layer to **Derived semantic atlas**;
   keep ContainerCore and density below it as experimental views.
3. Register every existing view with operation, version, parameters, and evaluation
   status before adding a new representation.
4. Run the owner-scored cited-interpretation test already planned for Stage 4h.
5. Use its error classes to choose **one** next view experiment. Do not implement the
   entire research menu.

The concrete operation inventory, candidate structures and promotion gates are kept in
the [semantic operation registry](SEMANTIC_OPERATION_REGISTRY.md). Stage 4h owner
review selected a source-boundary foundation correction before any new view experiment;
see [Stage 4h.1](STAGE_4H1_SOURCE_BOUNDARIES.md).

## View replacement and retirement

Whitepaper ancestry is not a promotion criterion. For the same registered query
family, compare an incumbent view and its proposed replacement on an identical frozen
corpus, candidate budget, owner-gold set, citation policy, and hardware envelope. The
decision records at least semantic quality, citation precision/recall, false
composition and false-attribution rates, abstention, latency, update cost, storage,
and implementation complexity.

- **Promote** the replacement when it yields a material, repeatable task-level gain
  without violating provenance or privacy invariants.
- **Keep both** only when they win on different declared operations or cost envelopes.
- **Keep the simpler incumbent** when quality is tied within uncertainty.
- **Deprecate** a consistently dominated view and remove it from active query plans.
- **Retire** implementation code only after its fixtures, benchmark result, and design
  history remain reproducible; canonical evidence never depends on that code.

No single metric decides every comparison. A quality gain can justify additional cost
only if the target use case declares that trade-off in advance. Conversely, lower cost
does not justify a measured loss of owner meaning or citation correctness.

## Falsification and publication threshold

The atlas hypothesis gains support only if a registered structural view improves an
owner-validated semantic operation over lexical/exact/LLM-context baselines while
retaining citation correctness and acceptable cost. A compelling explanation written
by a strong LLM is not evidence that the underlying view worked unless the candidate
and ablation path is recorded.

For a research paper, FVSC needs at minimum:

- a frozen private protocol plus a publishable de-identified or consented evaluation
  set;
- relation-specific tasks and baselines;
- view ablations, confidence intervals, latency, storage, and update cost;
- claim-level owner agreement and citation/forbidden-link metrics;
- negative results, including the current density/container and Gold retrieval results.

Until then, the semantic atlas is a coherent, falsifiable research program and an
engineering architecture—not a demonstrated universal representation of meaning.

## Research anchors

- [Poincare embeddings for hierarchical representations](https://arxiv.org/abs/1705.08039)
- [Multi-relational Poincare graph embeddings](https://arxiv.org/abs/1905.09791)
- [Probabilistic box embeddings for entailment](https://aclanthology.org/P18-1025/)
- [RotatE relation-pattern embeddings](https://openreview.net/forum?id=HkgEQnRqYQ)
- [Beta embeddings for multi-hop logical queries](https://arxiv.org/abs/2010.11465)
- [Contextualized word-representation geometry](https://aclanthology.org/D19-1006/)
- [Density matrices for lexical ambiguity](https://aclanthology.org/2020.conll-1.21/)

[ADR-007]: ../adr/ADR-007-semantic-atlas-uses-relation-conditioned-views.md
