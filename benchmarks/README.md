# FVSC viability benchmarks

## Controlled directionality benchmark

Run:

```bash
python -m core.viability_benchmark --output artifacts/viability-report.json
```

The benchmark uses the existing hand-authored containment set and compares:

1. **FVSC density matrices** — directional margin based on graded hyponymy;
2. **direct parser edges** — the weight of `A -> B` minus `B -> A` in `semantic_input`;
3. **chance** — expected directional accuracy of `0.5`.

The criteria are fixed in `core/viability_benchmark.py` before inspecting the
result:

- at least 80% concept-pair coverage;
- directional accuracy at least 0.65;
- one-sided exact sign-test `p < 0.05` against chance;
- accuracy range across dimensions 16, 32, 64 and 128 no greater than 0.15.

Possible verdicts:

- `pass`: controlled technical viability is supported;
- `inconclusive`: a signal is visible but the current evidence is too weak;
- `fail`: the density layer does not reliably preserve the annotated direction.

A separate verdict compares the density layer with direct parser edges.  If it
does not outperform the direct-edge baseline, the benchmark does **not** show
that density matrices add predictive value beyond the parser, even when the
controlled viability verdict is `pass`.

## What this benchmark cannot establish

This is a small, non-independent controlled set.  It cannot establish that FVSC
reconstructs a person's private meaning system, that its facets are
psychologically valid, or that it generalises to unseen vaults.

## Required external-validity study

The next benchmark must use held-out vault fragments and blinded human ratings:

1. split notes by time or folder before building the map;
2. generate candidate associations and interpretations from the training split;
3. mix FVSC outputs with outputs from TF-IDF/PPMI, embedding and random baselines;
4. hide model identity and output order from annotators;
5. ask the vault owner to rate personal relevance and directionality;
6. report paired bootstrap confidence intervals and effect sizes;
7. keep the test split untouched until model and thresholds are frozen.

Until that study exists, the defensible claim is **research prototype with a
controlled semantic signal**, not a validated model of personal meaning.
