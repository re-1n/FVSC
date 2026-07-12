# FVSC viability benchmarks

## Controlled directionality benchmark

Run:

```bash
python -m core.viability_benchmark --output artifacts/viability-report.json
```

The benchmark uses the existing hand-authored containment set and compares:

1. **FVSC mass-preserving density matrices** — the same graded-hyponymy direction used by production queries;
2. **trace-normalised density matrices** — a negative control;
3. **direct parser edges** — `weight(A -> B) - weight(B -> A)` in `semantic_input`;
4. **chance** — expected directional accuracy of `0.5`.

### Why mass must be preserved

The first CI run (benchmark v1) normalised both matrices to trace 1 before
computing graded hyponymy. It produced exactly 46 ties and accuracy 0.5. This is
expected mathematically: when both operators have equal trace, the positive and
negative spectral mass of their difference is balanced, so this particular
margin loses its direction.

Benchmark v2 matches the actual FVSC query contract and uses unnormalised
operators for the primary result. The trace-normalised calculation remains in
the report as an explicit negative control. The v1 artifact remains in the
GitHub Actions history; it was not deleted or reinterpreted as a successful run.

### Pre-registered criteria

The decision thresholds remain:

- at least 80% concept-pair coverage;
- directional accuracy at least 0.65;
- one-sided exact sign-test `p < 0.05` against chance;
- accuracy range across dimensions 16, 32, 64 and 128 no greater than 0.15.

Possible verdicts:

- `pass`: controlled technical viability is supported;
- `inconclusive`: a signal is visible but the current evidence is too weak;
- `fail`: the density layer does not reliably preserve the annotated direction.

A separate verdict compares the primary density result with direct parser
edges. If it does not outperform the direct-edge baseline, the benchmark does
**not** show predictive value beyond the parser, even when controlled viability
passes.

## What this benchmark cannot establish

This is a small, non-independent controlled set. It cannot establish that FVSC
reconstructs a person's private meaning system, that its facets are
psychologically valid, or that it generalises to unseen vaults. In particular,
a successful mass-preserving result may encode weight/frequency asymmetry rather
than a psychologically meaningful semantic order.

## Required external-validity study

The next benchmark must use held-out vault fragments and blinded human ratings:

1. split notes by time or folder before building the map;
2. generate candidate associations and interpretations from the training split;
3. mix FVSC outputs with TF-IDF/PPMI, embedding and random baselines;
4. hide model identity and output order from annotators;
5. ask the vault owner to rate personal relevance and directionality;
6. report paired bootstrap confidence intervals and effect sizes;
7. keep the test split untouched until model and thresholds are frozen.

Until that study exists, the defensible claim is **research prototype with a
controlled semantic signal**, not a validated model of personal meaning.
