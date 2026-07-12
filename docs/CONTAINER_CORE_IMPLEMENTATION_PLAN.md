# ContainerCore v1 implementation plan

## Objective

Implement and falsifiably test the original FVSC hypothesis:

> Personal semantics are an evidence-backed system of asymmetric, recursively nested containers. Density matrices are optional local container state, not the canonical memory.

The work must distinguish the value of explicit container structure from the value of density geometry.

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

- materialization is deterministic and input-order independent;
- retracted evidence disappears from the derived snapshot;
- provenance survives every derived object.

Status: implemented and unit-tested.

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

Status: implemented and unit-tested.

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
- runtime is suitable for the frozen public corpus.

Status: raw bounded traversal is implemented. Cached context-preserving query index is the next code change.

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

Status: projection and activation exist; context preservation and explicit path explanations are being completed.

### C4 — Falsifiable ablation

Compare on one frozen chronological split:

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

Decision rule:

- promote containers only when the best container backend beats the strongest non-container baseline with a positive paired CI;
- retain as experimental when competitive but not superior;
- prefer the simpler backend when the paired CI is entirely negative.

Status: benchmark exists, but the first full live run exceeded the workflow budget. The cached query index and bounded deterministic pair sampling must make C4 complete successfully.

### C5 — Strong-hypothesis tests

The relation-ranking benchmark is not sufficient to establish the main theoretical advantage. Follow with:

- human-labelled contextual polysemy;
- order-sensitive context updates;
- personal-vault episodic reconstruction;
- explanation usefulness ratings;
- learned/calibrated projection operators versus deterministic operators.

## Commit sequence

1. `docs: record container core implementation plan`
2. `feat(core): add cached context-preserving container query index`
3. `test(core): cover container explanations and context gating`
4. `perf(benchmark): use cached container queries and bounded pair controls`
5. `bench: register frozen container ablation result`

Each commit is independently useful and leaves the branch recoverable after an interrupted session.

## Stop conditions

Do not make ContainerCore the default when any of these hold:

- the full benchmark cannot complete within the local/CI resource budget;
- audited relation labels favour a simpler graph;
- context changes do not materially change activation;
- explanations cannot recover provenance and path structure;
- rankings are unstable under small evidence perturbations;
- personal daily-review usefulness does not improve.
