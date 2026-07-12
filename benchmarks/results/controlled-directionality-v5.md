# Controlled directionality benchmark v5

Date: 2026-07-11  
CI head: `122e5fee41563c01fdd83754938c4ce1a252daf5`

## Result

| Model | Direction accuracy | All-pairs AUC | Trace-matched AUC | Trace-matched comparisons |
|---|---:|---:|---:|---:|
| FVSC mass-preserving density | 1.0000 | 0.9766 | 0.5000 | 6 |
| Trace-normalised density control | 0.5000 | 0.5000 | 0.5000 | 6 |
| Trace-mass-only baseline | 1.0000 | 0.9766 | 0.5000 | 6 |
| Direct parser edges | 1.0000 | 0.9579 | 0.5000 | 6 |
| Chance | 0.5000 | 0.5000 | 0.5000 | — |

The FVSC result was identical across dimensions 16, 32, 64 and 128.

## Interpretation

### Supported

- The parser-to-matrix pipeline deterministically preserves the annotated
  containment direction on this controlled set.
- Gold links generally outrank unrelated ordered pairs.
- The result is stable across the tested dimensions.

### Not supported by this benchmark

- Added predictive value over direct parser edges: the AUC difference is only
  `+0.0187`, below the pre-defined `0.02` distinction threshold.
- Directional information beyond total matrix mass: the trace-only baseline has
  exactly the same direction accuracy and all-pairs AUC as FVSC.
- A trace-matched residual geometric signal: only six matched comparisons were
  available, and FVSC scored 0.5 on them.

## Scientific conclusion

The current implementation is **technically viable as a deterministic weighted
containment representation**, but this dataset does not demonstrate that its
spectral density-matrix geometry contributes information beyond the scalar
trace/mass induced by parser weights.

This is not evidence that density-matrix semantics is invalid. It is evidence
that the current evaluation set cannot distinguish the full FVSC operator from
a much simpler mass baseline.

## Required next experiment

Use held-out personal notes and blinded human ratings:

1. train the map on an earlier time period or selected folders;
2. hold out later notes before any tuning;
3. ask FVSC, trace-only, direct graph, TF-IDF/PPMI and embedding baselines to
   predict associations or rank relevant held-out notes;
4. mass-match candidate pairs so trace alone cannot solve the task;
5. randomise output order and hide model identity;
6. obtain personal-relevance ratings from the vault owner;
7. report paired bootstrap confidence intervals and effect sizes.

Until that experiment is completed, the defensible claim is: **FVSC encodes the
parser's weighted containment structure, but unique geometric value is not yet
demonstrated.**
