# FVSC semantic runtime roadmap

## Target

FVSC should become a local-first semantic runtime that can:

1. reconstruct a versioned personal semantic state from attributable evidence;
2. activate different facets under explicit context;
3. run auditable operators without mutating canonical state implicitly;
4. create reversible scenario branches for simulation;
5. translate meaning between people while disclosing uncertainty and information loss;
6. demonstrate predictive value on held-out data beyond simple mass, graph and embedding baselines.

Density matrices remain the representation of semantic shape. They are not used as a substitute for evidence count, confidence, provenance, policy or execution state.

## Non-negotiable invariants

- **Mass and shape are separate.** Evidence mass is a non-negative scalar. Semantic shape is a positive semidefinite operator with trace one when non-empty.
- **Evidence is append-only.** Aggregated matrices are materialized projections, not the source of truth.
- **Canonical state is immutable to operators.** Operators return proposed deltas or branch snapshots.
- **Every result is attributable.** Queries and generated interpretations expose evidence references, model version and uncertainty.
- **Speculation is typed.** Generated scenarios, dreams and simulations never become observed evidence automatically.
- **Privacy is local-first.** Export and cross-person alignment require explicit policy and minimum disclosure.
- **Scientific claims are gated.** A feature is not called validated until it beats registered baselines on held-out data.

## Target architecture

```text
sources
  -> evidence ledger
  -> materializer
  -> semantic snapshots (mass + normalized density state)
  -> context activation and relation channels
  -> auditable operator runtime
  -> scenario branches / alignment / applications
  -> evaluation and calibration
```

### 1. Evidence ledger

An immutable `EvidenceEvent` records source, timestamp, extracted relation, context, confidence, interpretation layer and provenance. Retraction is represented by a new event rather than destructive deletion.

### 2. Semantic state

A concept state contains:

- evidence mass;
- normalized PSD semantic operator;
- uncertainty and evidence count;
- stable facet descriptors;
- evidence references and materializer version.

The legacy unnormalised matrix remains available as `mass * shape` during migration.

### 3. Context and facets

Context activation produces a new normalized state from a base state through a validated channel. Context never overwrites the base state. Facets must be stable across rebuilds or explicitly versioned.

### 4. Relation channels

Relations evolve from deterministic rotations toward learned or calibrated positive maps. Each channel declares its training source, version and confidence. Deterministic transforms remain a baseline.

### 5. Operator runtime

A semantic operator receives an immutable snapshot plus an execution context and returns:

- a proposed state delta;
- explanations and evidence references;
- uncertainty;
- capability requirements;
- reproducibility metadata.

Initial operators:

1. `trace` — translate an utterance between two semantic maps;
2. `safeguard` — apply explicit user-authored boundaries and policies;
3. `persona_simulation` — produce labelled counterfactual responses;
4. `facet_sampler` — explore peripheral facets in a scenario branch.

### 6. Scenario sandbox

Scenarios are branchable snapshots with deterministic seeds, typed generated events and complete rollback. No scenario output is promoted to the canonical evidence ledger without explicit confirmation.

### 7. Alignment and federation

Cross-person alignment exposes only policy-approved summaries. Results separate shared anchors, divergent facets, translation hypotheses and uncertainty. Raw personal operators are not required to leave the device.

### 8. Evaluation

Every core mechanism has a simpler baseline:

- trace-only mass;
- direct relation graph;
- TF-IDF/PPMI;
- embedding cosine;
- deterministic random control.

Primary external-validity tests use temporal or folder-based held-out notes, mass-matched candidate pairs, blinded owner ratings, paired bootstrap intervals and calibration metrics.

## Delivery phases and gates

### Phase 0 — stabilize the current prototype

Deliverables:

- complete the security, persistence and provenance fixes already tracked in the draft PR;
- keep unit CI green;
- retain the controlled viability benchmark as a regression diagnostic.

Gate: current behavior is reproducible and no author-specific data paths remain.

### Phase 1 — separate mass from semantic shape

Deliverables:

- immutable `SemanticState` value object;
- conversion from and to legacy unnormalised matrices;
- explicit mass and shape accessors on concepts;
- shape-only similarity, entropy and facet APIs;
- trace-only controls retained in tests.

Gate: legacy matrices reconstruct within numerical tolerance; shape operations are invariant under positive scalar rescaling.

### Phase 2 — evidence ledger and materialization

Deliverables:

- versioned `EvidenceEvent` schema;
- append, retract and supersede operations;
- deterministic materializer;
- complete source provenance through consolidation;
- migration from legacy components.

Gate: rebuilding from the same ledger produces byte-equivalent metadata and numerically equivalent states; deleting or replacing one source affects no unrelated evidence.

### Phase 3 — immutable snapshots and deltas

Deliverables:

- content-addressed semantic snapshots;
- `StateDelta` schema;
- compare, apply, reject and rollback operations;
- no implicit mutation from read/query paths.

Gate: operator tests prove canonical snapshots cannot be mutated and all accepted changes are auditable.

### Phase 4 — contextual states and stable facets

Deliverables:

- explicit context descriptors;
- context-conditioned state activation;
- stable facet IDs and alignment across rebuilds;
- uncertainty propagation.

Gate: held-out facet selection beats context-free and frequency baselines.

### Phase 5 — relation channels and synchronous inference

Deliverables:

- relation-channel protocol;
- deterministic baseline channel;
- synchronous snapshot-based message passing;
- convergence and loop controls;
- optional learned channels with registered training data.

Gate: results are independent of dictionary iteration order and learned channels beat deterministic rotations on held-out directed relations.

### Phase 6 — operator runtime and scenario sandbox

Deliverables:

- capability-scoped operator protocol;
- immutable execution records;
- branchable scenarios;
- first validated operator: semantic tracing/translation.

Gate: tracing beats direct paraphrase and embedding retrieval in blinded pairwise ratings without mutating canonical state.

### Phase 7 — personal prediction study

Deliverables:

- temporal train/test split tooling;
- candidate association and note-retrieval tasks;
- mass-matched negative sampling;
- blinded rating interface;
- paired confidence intervals and effect sizes.

Gate: FVSC exceeds the strongest registered simple baseline with a positive lower confidence bound on at least one practically relevant task.

### Phase 8 — privacy-preserving multi-user alignment

Deliverables:

- disclosure policies;
- exportable alignment summaries;
- local comparison and optional secure aggregation;
- abuse, coercion and deanonymisation threat model.

Gate: useful alignment can be demonstrated without exchanging raw private evidence or full semantic states.

## Migration strategy

1. Add new types beside legacy matrices.
2. Expose adapters and dual-read APIs.
3. Move pure queries to normalized semantic shape.
4. Move persistence to versioned snapshots and ledgers.
5. Deprecate implicit unnormalised-matrix semantics only after compatibility tests pass.

No destructive state migration is performed automatically.

## Immediate implementation sequence

1. Add `core/semantic_state.py` with validated mass/shape separation.
2. Add unit tests for PSD, normalization, scalar invariance and round-trip reconstruction.
3. Expose `Concept.direct_state` and `Concept.deep_state` without changing existing `rho` properties.
4. Add shape-only comparison primitives and trace-matched tests.
5. Introduce the evidence-event schema and deterministic materializer.
