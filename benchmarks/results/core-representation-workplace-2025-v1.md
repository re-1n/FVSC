# FVSC core representation bakeoff — Workplace 2025 v1

## Scope

This experiment compares derived semantic backends on the same chronological directed-relation-ranking task. It does not compare canonical evidence stores and it does not test contextual word-sense disambiguation.

## Frozen data

- corpus SHA-256: `fb914a374bbf5c44688325d6588d175b995592b73bf2b7b2cea724b7ac074ecb`;
- records / threads: 1068 / 194;
- train / test threads: 155 / 39;
- evaluated test threads: 39;
- known-positive coverage: `0.8855`;
- pairwise comparisons per backend: 5 392 800.

## Results

| Backend | ROC AUC | Average precision |
|---|---:|---:|
| `conditional_graph` | 0.6025 | 0.8377 |
| `direct_graph` | 0.5935 | 0.8281 |
| `sparse_context_inclusion` | 0.5917 | 0.7941 |
| `ppmi_graph` | 0.5693 | 0.8154 |
| `fvsc_density_shape` | 0.5607 | 0.7934 |
| `random` | 0.4936 | 0.7749 |
| `trace_mass` | 0.3484 | 0.7201 |

Best non-density backend: `conditional_graph`.

Density-shape AUC delta: `-0.041771`.

Paired document-bootstrap CI95: `[-0.09947249393604646, 0.013899821813061567]`.

Registered verdict: **`inconclusive`**.

## Interpretation

- The conditional directed graph is the current leader for held-out relation ranking.
- The current density shape remains above deterministic random, but is below conditional graph, direct graph, PPMI and sparse context overlap.
- The cluster-aware confidence interval includes zero because there are only 39 independent test-thread clusters. The point estimate is negative, so there is no positive evidence for selecting the density backend here.
- This result tests the current deterministic hash-role materializer, not density matrices as a mathematical family.
- The bakeoff key `sparse_context_inclusion` is retained for reproducibility, but its v1 formula is histogram-intersection context overlap.

## Core decision after B1

1. Keep the append-only typed temporal evidence graph/hypergraph as the canonical kernel.
2. Use a conditional directed graph as the current default relation-ranking projection.
3. Keep density matrices as an experimental contextual-state backend.
4. Do not decide the density-matrix question until B2 tests contextual facet selection and minority-sense preservation against vectors and explicit mixtures.

## Required next experiment

Build a frozen contextual ambiguity benchmark using independently labelled same-word/different-context examples. Compare a centroid vector, sparse context model, explicit mixture, density state with context update and a frozen contextual embedding.

## Provenance

- GitHub Actions run: `29189404314`;
- artifact: `8259041180`;
- tested head: `c4140a6013ec51413a7bc0d0b22104b7bbff6c95`;
- artifact digest: `sha256:4a3de1c214978894c75f17e867f852b50524c3881ffc20d4545fe2ee01f8814f`.
