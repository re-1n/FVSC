# ContainerCore v1 implementation plan

## Objective

Implement and falsifiably test the original FVSC hypothesis:

> Personal semantics are an evidence-backed system of asymmetric, recursively nested containers. Density matrices are optional local container state, not the canonical memory.

The work must distinguish the value of explicit container structure from the value of density geometry.

## Current checkpoint

ContainerCore v1 is implemented as an experimental backend and has completed its first resource-bounded real-language ablation.

Validated checkpoint:

```text
source experiment commit: e05e923f2f13ac3d8f11a0c75a205629c1d8f7f6
GitHub Actions tests:      29193677444
GitHub Actions live run:   29193677480
```

Engineering checks at that experiment checkpoint:

- 145 Python tests passed;
- 12 integration/live tests were intentionally deselected by the unit profile;
- controlled viability benchmark passed;
- TypeScript typecheck and production Obsidian build passed;
- the bounded real-language container ablation completed in 39.71 seconds.

Registered result:

```text
best container:      container_structure  AUC 0.5637
best non-container:  direct_graph         AUC 0.5716
delta:                                    -0.007891
paired CI95:                              [-0.04890625, 0.02907617]
verdict:                                  container_model_competitive
```

The result is stored in:

- `benchmarks/results/container-core-workplace-2025-80threads-v1.json`;
- `benchmarks/results/container-core-workplace-2025-80threads-v1.md`.

## Architectural invariants

1. `EvidenceLedger` remains the canonical append-only memory.
2. Every container, embedding, projection and explanation must reference evidence identifiers.
3. `A <- B` and `B <- A` are independent; reverse embeddings are never inferred.
4. A parent stores a child reference and projection operator, never an uncontrolled copy.
5. Recursive activation is bounded, cycle-safe and deterministic.
6. The same evidence contribution cannot gain mass merely by being reachable through multiple paths.
7. Negative evidence is retained but cannot silently subtract from a PSD state.
8. Container snapshots are derived and fully rebuildable from active evidence.

## Milestones

### C0 — Contracts and evidence boundary

Deliverables:

- immutable container/contribution/embedding contracts;
- versioned snapshot identity;
- ledger-to-container materializer;
- retraction and supersession compatibility.

Acceptance:

- materialization is deterministic for the same active assertion set;
- append-only history identity remains separately order-sensitive;
- retracted evidence disappears from the derived snapshot;
- provenance survives every derived object.

Status: **implemented and unit-tested**.

### C1 — Explicit asymmetric nesting

Deliverables:

- independent directed embeddings;
- typed roles and bounded context keys;
- local facets grouped by child and role;
- deterministic projection operators.

Acceptance:

- mutual embeddings retain different roles, strengths and operators;
- a missing reverse embedding is never invented;
- direct and indirect containment are distinguishable.

Status: **implemented and unit-tested**.

### C2 — Safe recursive traversal

Deliverables:

- branch and depth limits;
- path-cycle protection;
- repeated-evidence aggregation;
- deterministic strongest-path selection;
- cached path index for practical local queries.

Acceptance:

- traversal terminates on cyclic input;
- branch count is bounded independently of corpus repetition;
- repeated routes do not multiply contribution mass;
- path queries are cached by root, context and traversal parameters.

Status: **implemented and unit-tested** through `core/container_query.py`.

### C3 — Contextual local state and explanations

Deliverables:

- context-sensitive path gating;
- child-state projection into parent space;
- activated parent state;
- structure-only, density-only and hybrid scores;
- path explanations with container sequence, edge IDs and evidence IDs.

Acceptance:

- matching contexts produce stronger activation than mismatched contexts;
- explanations identify the exact path and supporting evidence;
- density state is replaceable without changing container topology.

Status: **implemented and unit-tested**.

### C4 — Falsifiable ablation

Compared on one frozen chronological split:

1. direct graph;
2. conditional graph;
3. PPMI graph;
4. current density-only FVSC;
5. explicit container structure;
6. explicit container projected density;
7. explicit container hybrid;
8. deterministic random control.

Metrics:

- ROC AUC;
- average precision;
- paired document bootstrap CI95;
- known-positive coverage;
- asymmetric forward/reverse score rate;
- wall-clock runtime and sampled pair count.

Resource-bounded first run:

- available corpus: 1,068 records / 194 threads;
- deterministic chronological selection: first 80 threads;
- train/test: 64 / 16;
- semantic dimension: 16;
- recursion depth: 2;
- sampled positives/negatives: 320 / 320;
- 6,400 pairwise comparisons per model;
- known-positive coverage: 0.7821;
- runtime: 39.71 seconds.

Decision rule:

- promote containers only when the best container backend beats the strongest non-container baseline with a positive paired CI;
- retain as experimental when competitive but not superior;
- prefer the simpler backend when the paired CI is entirely negative.

Status: **completed for the bounded real-language slice**.

Interpretation:

- explicit container structure is statistically competitive with the direct graph on this slice;
- superiority is not demonstrated because the delta is negative and the interval crosses zero;
- projected density and hybrid scoring did not improve over structure-only containers;
- the current evidence therefore supports continued testing of explicit asymmetric structure, but not promotion of the matrix component.

The full 194-thread run remains a scale-up gate. Earlier dense implementations exceeded the workflow budget; this is recorded rather than hidden by increasing timeout.

### C5 — Strong-hypothesis tests

Relation ranking does not directly test the strongest theoretical claims. Continue with:

- human-labelled contextual polysemy;
- order-sensitive context updates;
- personal-vault episodic reconstruction;
- explanation usefulness ratings;
- learned or calibrated projection operators versus deterministic operators;
- alternative path aggregation: strongest, evidence-disjoint and probabilistic.

Status: **next research milestone**.

## Implemented modules

| Module | Purpose |
|---|---|
| `core/container_core.py` | Explicit containers, embeddings, activation and projections |
| `core/container_query.py` | Context-preserving cached paths and provenance explanations |
| `core/container_materializer_fast.py` | Deterministic signed-permutation operator baseline |
| `core/container_benchmark_cached.py` | Resource-bounded graph/container/density ablation |
| `core/container_benchmark_fast_cli.py` | Dimension-controlled public-corpus runner |

## Completed commit sequence

1. `2999a581` — plan and acceptance criteria;
2. `ab9c30c7` — cached context-preserving query index;
3. `07b186df` — context, cycle and explanation tests;
4. `43000f75` — cached ablation implementation;
5. `4a2ca1dd` — signed-permutation materializer;
6. `e05e923f` — bounded live experimental protocol;
7. aggregate result under `benchmarks/results/`.

Each stage was committed independently, so an interrupted session does not erase the implementation checkpoint.

## Stop conditions

Do not make ContainerCore the default when any of these hold:

- the full benchmark cannot complete within the local resource budget;
- audited relation labels favour a simpler graph;
- context changes do not materially change activation;
- explanations cannot recover provenance and path structure;
- rankings are unstable under small evidence perturbations;
- personal daily-review usefulness does not improve.

At the current checkpoint, ContainerCore remains an **experimental competitive backend**, not the production default.
