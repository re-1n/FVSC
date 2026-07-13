# Next steps

Migration order (foundation-first; each commit must build and pass tests):

1. **Commit №0 — scaffold + tooling** (this branch, in progress): `src/fvsc/` skeleton,
   CI (`tests.yml`), pytest markers, `data/.gitignore`, legacy-boundary check, ADRs,
   architecture / status docs.
2. ✅ **Foundation** — `EvidenceEvent`, `EvidenceLedger`, `SemanticState`, persistence,
   snapshot contracts → `src/fvsc/evidence/` + `runtime/`.
3. ✅ **Representations** — mass-invariant shape metrics (`semantic/metrics.py`) →
   ContainerCore v1 experimental (`semantic/containers/`, ADR-002) → density optional
   backend (`semantic/density/`, ADR-003). No Obsidian/HTTP/parser deps. Commits
   `717da42` `3165784` `95c3830` `2809c39`; **104 passed / 1 skipped**.
4. **Applied / clickable MVP**:
   - ✅ ingest foundation — language-agnostic parser, provenance adapter,
     `semantic_input`, and deterministic basis vectors. Working chain:
     `raw text -> parser -> concept tree -> vectors / rho`; **117 passed / 1 skipped**.
   - **Stage 4d — vault ingest** — Obsidian Markdown files → canonical
     `EvidenceLedger` + derived semantic representations → local on-disk cache;
     source lifecycle and provenance are mandatory.
   - FastAPI service.
   - Chat + local Ollama integration.
   - Visualization + Obsidian bridge.
   Keep HTTP, plugin, and LLM dependencies outside the ingest layer. Do not commit
   vault data, voice data, or generated folders.
5. **Verify** — unit, persistence/restart, synthetic voice, plugin build, ContainerCore
   fixtures, registered benchmarks. Then open a new small PR and close PR #1 as
  `superseded`.

## Follow-ups (not blocking)

- Track `obsidian-plugin/package-lock.json` so CI can use `npm ci` (reproducible builds)
  and restore the `typecheck` job.
- Port `core.viability_benchmark` and the `natural-language-live.yml` workflow once the
  benchmark modules are ported (Stage 5).
- **`benchmarks/results/` is absent on this branch** despite ADR-002 ("Negative results
  are recorded in `benchmarks/results/`, not hidden"). Port the registered negative
  results as a `chore(benchmarks)` commit in Stage 5 alongside the runners. None of the
  Stage-3 modules read them, so not a blocker.
- ✅ **Parser + provenance** landed in Stage 4a–4c under `src/fvsc/ingest/` and
  `src/fvsc/evidence/`; Stage 4d must consume those public contracts rather than
  importing the legacy `core/` package.
- Decide on `data/conceptnet_ru.json` (12.7 MB, tracked) — keep as a curated asset or
  untrack with a download fallback.
- Unify tests under `tests/{unit,integration,e2e}/` as subsystems port. Note: test dirs
  carry no `__init__.py` (foundation convention), so test-file basenames must be unique
  across the whole tree — `density/test_density.py` not `test_core.py` (collides with
  `containers/test_core.py`).
