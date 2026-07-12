# FVSC core representation bakeoff

_Last updated: 2026-07-12_

## Question

What mathematical structure should sit at the center of a personal semantic system
that must preserve evidence, represent polysemy and uncertainty, update over time,
explain its conclusions and support operators such as tracing, safeguard and
scenario simulation?

The answer must not be selected by elegance alone.  Candidate representations must
receive the same evidence and be compared on frozen tasks with registered baselines.

## Two different meanings of “core”

A single object should not be forced to solve two different problems.

### 1. Canonical evidence core

This layer must preserve:

- exact source and source revision;
- time;
- speaker and attribution;
- assertion, correction, supersession and retraction;
- modality, confidence and polarity;
- multi-party and multi-concept relations;
- access policy and retention;
- deterministic reconstruction.

The provisional choice is an append-only typed temporal evidence graph.  A relation
with source, speaker and context is logically a hyperedge/event, even when a parser
currently projects it into a simple pair.  This layer is representation-neutral and
must survive replacement of the semantic backend.

### 2. Derived semantic-state core

This layer answers questions such as:

- how similar or different are two meanings;
- does one meaning include another;
- which facet is active in this context;
- how uncertain or internally mixed is a concept;
- how should context transform the current state;
- which candidate relation should be ranked first?

Density matrices, sparse distributions, graphs, vector embeddings and explicit
mixture models compete here.

## Why density matrices remain a serious candidate

Density operators have properties directly relevant to FVSC:

- a mixed state can represent several weighted facets without collapsing them into
  one vector;
- eigenvalues provide a natural mixture spectrum and entropy;
- positive operators support graded inclusion/entailment measures;
- context can be represented as a state transformation or measurement;
- composition can be expressed with linear or completely positive maps.

Published work has used density matrices for lexical ambiguity and graded
entailment, including models that outperform vector compositional baselines on
sense-discrimination tasks.  This justifies testing the formalism.  It does not
justify the current hash-based basis or the current FVSC scoring rule.

References:

- Balkir, Sadrzadeh, Coecke — Distributional Sentence Entailment Using Density
  Matrices: https://arxiv.org/abs/1506.06534
- Bankova, Coecke, Lewis, Marsden — Graded Entailment for Compositional
  Distributional Semantics: https://arxiv.org/abs/1601.04908
- Meyer, Lewis — Modelling Lexical Ambiguity with Density Matrices:
  https://arxiv.org/abs/2010.05670

## Competing representations

### Directed typed graph / hypergraph

Strengths:

- explicit direction and relation types;
- direct provenance and auditability;
- natural incremental updates and retractions;
- efficient sparse storage;
- easy rule and path operations.

Weaknesses:

- uncertainty and polysemy require additional structures;
- context activation is not inherent;
- graph topology alone may overfit parser artifacts.

A semantic hypergraph is a relevant structural comparison because it preserves
recursive, inspectable relations rather than compressing them immediately into an
opaque state: https://arxiv.org/abs/1908.10784

### Sparse distributional representations

Examples: conditional edge probabilities, PPMI and sparse context inclusion.

Strengths:

- transparent and inexpensive;
- strong distributional baselines;
- naturally derived from observed counts;
- easy to inspect and debug.

Weaknesses:

- weak composition;
- poor handling of genuinely incompatible senses unless an explicit mixture is
  added;
- dimensionality grows with vocabulary.

### Dense vectors and vector-symbolic architectures

Strengths:

- efficient similarity and retrieval;
- binding and bundling operations;
- mature learned encoders;
- good scalability.

Weaknesses:

- a single vector can blur incompatible facets;
- provenance is external;
- approximate binding/unbinding introduces capacity and recovery trade-offs.

A broad comparison of vector-symbolic architectures is available at:
https://arxiv.org/abs/2001.11797

### Explicit mixture / latent-facet model

Strengths:

- directly represents multiple senses;
- components remain interpretable if anchored to evidence;
- probabilistic updating is straightforward.

Weaknesses:

- facet count and identity must be managed;
- composition and relation direction need separate machinery;
- component collapse and unstable relabeling are common practical risks.

### Density matrices

Strengths:

- mixture and geometry in one PSD object;
- spectrum, entropy and subspace inclusion;
- compatible with contextual operators;
- can interpolate between pure vectors and mixtures.

Weaknesses:

- quadratic storage without low-rank structure;
- results depend strongly on the basis and materializer;
- provenance and relation identity are not intrinsic;
- a poorly chosen score can reduce to mass or graph frequency;
- interpretability is weaker than an explicit evidence graph.

## Implemented bakeoff v1

`core/representation_bakeoff.py` compares, on one chronological split:

1. direct directed-edge weight;
2. conditional edge probability;
3. directed PPMI;
4. sparse context inclusion;
5. current FVSC normalized density shape;
6. trace-mass control;
7. deterministic random control.

All models receive only training-period documents.  All models score the same known
positive and negative pairs in later documents.  The evaluator reports ROC AUC,
average precision and a paired document-level bootstrap interval.

This v1 benchmark answers only:

> Does the current density materializer improve directed relation ranking over
> simple sparse structures?

It does not answer whether density matrices are best for contextual polysemy.

## Required benchmark families

### B1 — directed relation prediction

Data:

- frozen public discussion corpora;
- chronological personal-vault split;
- independently audited relation labels.

Candidate winner must beat direct graph, conditional graph, PPMI, sparse inclusion,
trace mass and random.

### B2 — contextual facet selection

Each ambiguous concept must appear in multiple independently labelled contexts.
Compare:

- centroid vector;
- nearest-context sparse vector;
- explicit mixture model;
- density matrix with context update;
- frozen contextual embedding.

Measures:

- facet selection accuracy;
- calibration;
- context sensitivity;
- stability under additional evidence;
- ability to preserve minority senses.

This is the benchmark on which density matrices have the strongest reason to win.

### B3 — contradiction and uncertainty

Test whether the representation distinguishes:

- two compatible facets;
- uncertainty between alternatives;
- explicit contradiction;
- reported speech versus owner belief;
- negation versus absence of evidence.

A scalar entropy value alone is not sufficient.  The system must preserve which
evidence caused the conflict.

### B4 — incremental lifecycle

Measure:

- update latency;
- exact retraction;
- deterministic restart;
- drift after repeated replacement;
- memory growth;
- whether unrelated concepts change after one source correction.

### B5 — practical operator value

Blindly compare backend outputs for:

- semantic tracing;
- daily review;
- retrieval;
- safeguard candidate generation;
- context-conditioned Antourage responses.

The user should rate usefulness without being shown which backend produced an
output.

## Decision rules

### Density matrices become the primary semantic backend only when

- they beat the strongest simple baseline on at least two independent corpora;
- the paired confidence interval has a positive lower bound;
- they beat explicit mixtures or vectors on contextual facet selection;
- the advantage survives independently audited labels;
- real-vault blind ratings show a practical gain;
- latency and storage remain acceptable.

### Density matrices remain an optional backend when

- they are competitive but do not produce a stable practical advantage;
- they are useful only for specific operators such as ambiguity or scenario state;
- a graph or mixture model is better for ordinary retrieval and relation ranking.

### Density matrices are demoted from the semantic core when

- a context-aware implementation still loses to sparse graphs and strong vector or
  mixture baselines;
- any apparent advantage disappears after label audit;
- the same result can be reproduced by trace, mass or direct edge frequency;
- complexity prevents reliable daily use.

## Provisional architecture

Until the bakeoff is complete:

```text
append-only typed temporal evidence graph
        ↓ deterministic materializers
  ┌───────────────┬──────────────────┬─────────────────┐
  │ sparse graph  │ density matrices │ vector/mixture  │
  └───────────────┴──────────────────┴─────────────────┘
        ↓ shared operator protocol and blind evaluation
```

The current leading hypothesis is therefore hybrid:

- **evidence graph/hypergraph as the canonical kernel**;
- **density matrices as an experimental contextual semantic state**;
- **operators depend on an interface, not on one protected representation**.

This preserves the strongest properties of density matrices without risking the
entire system on an unvalidated encoder or score.
