# Next steps

Migration order (foundation-first; each commit must build and pass tests):

1. **Commit №0 — scaffold + tooling** (this branch, in progress): `src/fvsc/` skeleton,
   CI (`tests.yml`), pytest markers, `data/.gitignore`, legacy-boundary check, ADRs,
   architecture / status docs.
2. **Foundation** — `EvidenceEvent`, `EvidenceLedger`, `SemanticState`, persistence,
   snapshot contracts → `src/fvsc/evidence/` + `runtime/`.
3. **Representations** — graph → containers (experimental) → density, no Obsidian/HTTP
   deps. Keep `benchmarks/results/`.
4. **Applied** — voice (reviewed R1) → Antourage contracts → obsidian → service.
5. **Verify** — unit, persistence/restart, synthetic voice, plugin build, ContainerCore
   fixtures, registered benchmarks. Then open a new small PR and close PR #1 as
  `superseded`.

## Follow-ups (not blocking)

- Track `obsidian-plugin/package-lock.json` so CI can use `npm ci` (reproducible builds)
  and restore the `typecheck` job.
- Port `core.viability_benchmark` and the `natural-language-live.yml` workflow once the
  benchmark modules are ported (Stage 3 / 5).
- Decide on `data/conceptnet_ru.json` (12.7 MB, tracked) — keep as a curated asset or
  untrack with a download fallback.
- Unify tests under `tests/{unit,integration,e2e}/` as subsystems port.
