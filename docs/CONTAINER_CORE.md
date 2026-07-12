# Explicit Container Core v1

## Status

`ContainerCore v1` is an experimental, explicit implementation of the original FVSC
hypothesis: personal semantics are represented as recursively nested containers with
independent directed embeddings.

It is implemented for falsifiable comparison. It is **not** yet evidence that the
container hypothesis is superior on natural language or useful in personal practice.

## Architectural boundary

The append-only `EvidenceLedger` remains the canonical memory:

```text
source text / reviewed owner speech
  -> immutable EvidenceEvent history
  -> active evidence view
  -> explicit container materializer
  -> context activation and benchmark scores
```

A container snapshot is always rebuildable. Containers and density states are derived
representations and cannot replace provenance, timestamps, speaker attribution,
retractions or supersessions.

## Formal model

A semantic container is represented as:

\[
C_i = (L_i, F_i, E_i, P_i)
\]

where:

- `L_i` is the local semantic state derived from evidence contributions;
- `F_i` is the set of outgoing evidence-backed facets;
- `E_i` is the set of directed container embeddings;
- `P_i` is the set of supporting evidence identifiers.

A directed embedding is:

\[
e_{i \leftarrow j} =
(i, j, r, c, w, \pi, T, P)
\]

where:

- `i` is the parent container;
- `j` is the child container;
- `r` is the semantic role or relation;
- `c` is a bounded context-key set;
- `w` is evidence strength;
- `pi` is polarity;
- `T` is the child-to-parent projection operator;
- `P` is provenance.

The reverse embedding is never inferred:

\[
e_{A \leftarrow B} \ne e_{B \leftarrow A}
\]

Both directions may exist, but only when independently supported by evidence.

## Data contracts

### `ContainerContribution`

One local contribution to one container:

- content-addressed contribution identifier;
- container identifier;
- source `event_id`;
- semantic role;
- non-negative weight;
- normalized positive-semidefinite operator.

The contribution identity includes the event, term and role. This permits one evidence
event to affect several legitimate roles while preventing the same role contribution
from being counted repeatedly through a recursive cycle.

### `ContainerEmbedding`

One evidence-backed directed projection:

- `parent_id` and `child_id`;
- relation role;
- normalized context keys;
- weight and polarity;
- deterministic projection operator;
- evidence identifiers.

V1 uses deterministic orthogonal operators. This makes order-sensitive composition and
asymmetric projection testable without introducing model downloads. These operators
are a baseline, not learned semantic transformations.

### `SemanticContainer`

Contains:

- local density state;
- immutable local contributions;
- outgoing facets grouped by child and role;
- evidence references.

The child state is not copied into the parent. The parent stores only a reference and a
projection operator.

### `ContainerSnapshot`

Contains all explicit containers and directed embeddings for one ledger state. It
provides:

- direct embedding lookup;
- bounded recursive path search;
- structure-only containment score;
- context-dependent activation;
- child-to-parent state projection;
- projected-density containment score;
- structure+density hybrid score.

## Recursive activation

For a path

\[
C_0 \leftarrow C_1 \leftarrow \dots \leftarrow C_k
\]

V1 composes operators as:

\[
T_{0 \leftarrow k}
= T_{0 \leftarrow 1} T_{1 \leftarrow 2} \dots T_{k-1 \leftarrow k}
\]

Path strength is the product of:

- positive embedding weights;
- context affinity;
- a per-depth decay coefficient.

Activation is bounded by `max_depth`. A container already present in the current path
cannot be entered again, which prevents path cycles.

If the same contribution is reachable through multiple paths, only its strongest path
is used. This prevents cyclic or redundant path multiplication from increasing evidence
mass.

## Context gating

Embedding context keys are extracted deterministically from:

- event context;
- event provenance;
- relation;
- source identifier.

A query context changes path strength and therefore the activated density state. A
small configurable floor prevents a single missing keyword from deleting otherwise
supported structure.

The current gate is lexical and deliberately simple. Learned or calibrated context
gates are future candidates.

## Polarity

Negative-polarity embeddings remain in the snapshot and retain provenance, but they do
not create positive containment mass in V1.

This is conservative. A later version may introduce separate inhibitory channels or
signed factor representations, but it must not subtract directly from a PSD state and
silently violate density-state invariants.

## Scores and ablation

`core/container_benchmark.py` compares these representations on one frozen
chronological split:

| Model | Tested component |
|---|---|
| `direct_graph` | Raw directed edge counts |
| `conditional_graph` | Row-normalized directed graph |
| `ppmi_graph` | Directed PPMI |
| `fvsc_density_shape` | Current density state without explicit containers |
| `container_structure` | Recursive directed container paths without density geometry |
| `container_density` | Child state projected through container operators |
| `container_hybrid` | Equal-weight structure and projected-density score |
| `random` | Deterministic control |

This ablation answers separate questions:

1. Does explicit recursive structure add value over a flat graph?
2. Does density geometry add value without explicit containers?
3. Does density geometry add value after the container relation is explicit?

The canonical evidence ledger is not part of this competition.

## Verdict rules

The benchmark reports:

- ROC AUC;
- average precision;
- pairwise comparison count;
- known-positive coverage;
- paired document-bootstrap confidence interval;
- rate of positive pairs whose forward and reverse container scores differ.

Possible verdicts:

- `insufficient_data`;
- `container_model_leads`;
- `simpler_backend_preferred`;
- `container_model_competitive`;
- `inconclusive`.

A container model is not considered superior merely because it produces asymmetric or
non-zero scores. It must beat the strongest non-container backend with a positive
paired confidence interval.

## Current automated coverage

The registered tests verify:

- independent mutual embeddings;
- distinct forward and reverse operators;
- context-sensitive activation;
- bounded recursion and cycle protection;
- contribution deduplication;
- indirect containment projection;
- absence of invented reverse containment;
- retraction removal;
- conservative negative-polarity behavior;
- semantic order-independence for assertion-only materialization;
- deterministic ablation reports.

## Remaining scientific gates

The model is implemented, but the hypothesis remains unproven. Required experiments:

1. Run the container ablation on the frozen Workplace corpus.
2. Repeat it after blinded audit of at least 100 parser-derived relations.
3. Run on at least two different discourse domains.
4. Test contextual polysemy using human-labelled context pairs.
5. Replace deterministic projection operators with learned or calibrated alternatives.
6. Compare maximum-path, evidence-disjoint path and probabilistic-path aggregation.
7. Run the same ablation on the owner's real vault with explicit usefulness ratings.

## Stop conditions

Do not promote ContainerCore to the default semantic backend when any of these remain
true:

- it loses reliably to a simpler graph on audited labels;
- its gains disappear when density is removed;
- recursive paths produce unstable rankings under small evidence changes;
- explanations cannot identify the evidence and path behind a score;
- runtime cost prevents ordinary local use;
- personal review usefulness does not improve.

## Current interpretation

The implementation now permits a real test of the original proposal. It does not
retroactively validate the proposal.

The strongest current architecture hypothesis is:

```text
append-only evidence ledger
  + explicit asymmetric recursive containers
  + replaceable local state backend
  + context-dependent projection operators
```

Density matrices remain one candidate local-state backend within this architecture.
