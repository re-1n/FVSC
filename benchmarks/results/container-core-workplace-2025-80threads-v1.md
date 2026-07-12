# ContainerCore v1 — Workplace 2025 bounded ablation

## Registered result

This report records the first completed real-language ablation of the explicit asymmetric container implementation.

- GitHub Actions run: `29193677480`
- source commit: `e05e923f2f13ac3d8f11a0c75a205629c1d8f7f6`
- corpus SHA-256: `fb914a374bbf5c44688325d6588d175b995592b73bf2b7b2cea724b7ac074ecb`
- available corpus: 1,068 records in 194 threads
- deterministic chronological slice: 80 threads
- train/test: 64 / 16
- known-positive coverage: 0.7821
- sampled positives/negatives: 320 / 320
- semantic dimension: 16
- maximum recursion depth: 2
- runtime: 39.71 seconds
- materializer: `explicit-container-core-signed-permutation-v1`

## Results

| Backend | ROC AUC | Average precision | Pairwise comparisons |
|---|---:|---:|---:|
| `conditional_graph` | 0.5702 | 0.5709 | 6,400 |
| `container_density` | 0.5631 | 0.5875 | 6,400 |
| `container_hybrid` | 0.5631 | 0.5869 | 6,400 |
| `container_structure` | 0.5637 | 0.5872 | 6,400 |
| `direct_graph` | 0.5716 | 0.5867 | 6,400 |
| `fvsc_density_shape` | 0.5567 | 0.5558 | 6,400 |
| `ppmi_graph` | 0.5509 | 0.5503 | 6,400 |
| `random` | 0.5364 | 0.5148 | 6,400 |

Best container backend: `container_structure`.

Best non-container backend: `direct_graph`.

Container AUC delta:

```text
-0.007891
```

Paired document-bootstrap CI95:

```text
[-0.04890625, 0.02907617]
```

Asymmetric forward/reverse positive-pair rate: `0.5125`.

Registered verdict:

```text
container_model_competitive
```

## Interpretation

The explicit **structure-only container backend** reached AUC `0.5637`, versus `0.5716` for the direct graph. The difference is small (`-0.0079`) and its paired interval crosses zero. Therefore this run does **not** establish superiority, but it also does not support a reliable rejection of the container structure on this bounded slice.

The density variants did not improve the container result:

- structure: `0.5637`;
- projected density: `0.5631`;
- hybrid: `0.5631`.

This means the current deterministic density geometry has not earned additional complexity. The value observed so far comes primarily from the explicit asymmetric structure, not from the matrix state.

The asymmetry rate of `0.5125` confirms that the implementation produces direction-dependent containment for roughly half of evaluated positive pairs. This is an implementation property, not evidence of semantic correctness by itself.

## Scope and limitations

- Parser-derived edges remain proxy labels rather than independent human annotations.
- The test uses the first 80 chronological threads, not all 194 corpus threads.
- Candidate pairs are deterministically capped at 20 positives and 20 negatives per test document.
- Projection operators are deterministic signed permutations at dimension 16, not learned transformations.
- Strongest-path projection is used; other path aggregation rules remain untested.
- Relation ranking does not directly test contextual polysemy, order effects, episodic reconstruction or personal usefulness.

## Decision

ContainerCore remains an **experimental competitive backend**. It must not replace the direct graph as the default yet.

Next gates:

1. blind-audit at least 100 parser relations;
2. run a human-labelled contextual-polysemy benchmark;
3. test learned or calibrated projection operators;
4. compare path-aggregation rules;
5. repeat on the owner's vault with usefulness ratings;
6. scale to the complete corpus only after reducing dense materialization cost.

Raw third-party text is not committed with this report.
