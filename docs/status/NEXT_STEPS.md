# Next steps

Migration order (foundation-first; each commit must build and pass tests):

1. ✅ **Commit №0 — scaffold + tooling**: `src/fvsc/` skeleton,
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
   - ✅ **Stage 4d — vault ingest** — Obsidian Markdown → typed `SourceDocument` →
     canonical `EvidenceLedger` → deterministic `MaterializedSnapshot` → versioned,
     atomic JSON cache. Includes idempotent replay, append-only change/delete/reactivate
     lifecycle, protected generated-folder exclusions, explicit source kinds, and a
     portable Telegram JSON source adapter. Commits `817bd2f` `180f6c0` `964b296`
     `e63ee84` `ba7c893` `c512367`; **152 passed / 1 skipped**.
   - ✅ **Stage 4d.1 — real-data ingest correction** — message-level Telegram sources,
     explicit owner adoption, private participant provenance, reply/time/forward/media
     evidence excluded from semantic concepts, and a character n-gram lexical floor.
     Commits `1bea6d7` `f6f4389` `48f9916` `7a7b175`; **160 passed / 1 skipped /
     11 deselected** and GitHub CI green.
   - ✅ **Stage 4e — real-data semantic evaluation** — portable exact-relation
     Judgments, source spans, policy-controlled layers, feedback, temporal
     contradictions, released Gold 001–015 with locally resolved source bodies, and
     lexical/exact/fusion comparison.
     Lexical wins (MRR@10 0.5262 vs 0.2611 exact); no semantic arm is promoted.
   - ✅ **Stage 4f — source-cited interpretation proposals** — typed L2/L3 claims,
     revision/hash citations, forbidden-link checks, claim-level owner assessment,
     and a separate atomic interpretation journal. No automatic owner evidence.
   - ✅ **Stage 4g — FastAPI + Ollama + Obsidian** — clean `VaultRuntime`, thin local
     HTTP routes, strict loopback JSON Ollama adapter, native lexical source search,
     cited interpretation, source opening, and claim review in Obsidian.
   - ✅ **Semantic-representation audit** — ADR-007 and the semantic-atlas architecture
     preserve the whitepaper's Judgment, container, relation-transform, tensor-factor,
     graph, recursive, temporal, metaphor, and L0–L3 work while demoting density from a
     universal substrate to an optional local view. The audit also corrects the legacy
     unbounded containment ratio, eigenvector/facet overclaim, non-unique matrix
     decomposition, and unproven fractal/convergence claims.
   - **First vertical dialogue census — participant review pending.** A bounded private
     two-party episode now has source-linked candidate `M/R/G/N/Q` units, external
     reply-antecedent checks, provenance for model-assisted wording, and an independent
     challenge pass. One participant's meaning layer is reviewed; the other participant
     has a neutral source-cited review pack. Keep every source body and review artifact
     under ignored `private_eval/`; freeze a new private revision only after the second
     review and a final challenge pass. This is evaluation construction, not evidence of
     semantic-representation superiority.
   - ✅ **Stage 4h harness** — immutable manifest and preregistered thresholds;
     source-body-free challenge addendum; frozen A0/A1/A2/A4 candidates; exact local
     model digest/seed/token/duration telemetry; paired local generation; keyed blinded
     owner-review pack; paired scoring and conservative diagnosis. Raw proposals,
     excerpts, arm map, and owner review stay under ignored `.fvsc/stage4h/`.
   - ✅ **Original Stage 4h generation** — after the recorded CPU timeout, empty-context
     and Windows-writer corrections, the owner's GPU run produced all 18 blinded
     A1/A2/A4 items. Five items have preliminary qualitative review; the blind map is
     still closed, so no arm comparison or promotion is valid yet. Review every
     remaining claim/citation and measure false authorship, unknown-referent assumptions,
     forbidden composites, abstention, latency, and tokens. `A3` remains deferred until
     a separate external-source privacy scope is explicitly authorized.
   - **Stage 4h.1 source-boundary correction — ready for rerun.** The operation registry,
     typed transport-author/origin/adoption envelope, 61 verified Telegram blockquote
     spans on the private corpus, attribution-aware prompt v4, auditable review-pack
     context, deterministic explicit-locator anchoring and sparse revision-bound owner
     annotation overlay are implemented. The overlay separates origin, adoption and
     endorsement, stores no body, and is bound into the new immutable run id. The known
     song/AI two-span seed validates against the 645-document corpus. These are
     canonical-safety corrections, not a promoted semantic view. Next: push, run the
     no-model validator, then execute and blind-review the corrected pilot. Protocol:
     [`STAGE_4H1_SOURCE_BOUNDARIES.md`](../architecture/STAGE_4H1_SOURCE_BOUNDARIES.md).
   - **Decision after Stage 4h** — choose at most one relation-conditioned view whose
     inductive bias matches the dominant error (for example contextual usage retrieval,
     directed inclusion, temporal trajectory, or ambiguity state). Register a baseline
     and ablation before implementation. Do not build the full research menu.
     Protocol: [`STAGE_4H_CONTROLLED_ATTRIBUTION_TEST.md`](../architecture/STAGE_4H_CONTROLLED_ATTRIBUTION_TEST.md).
     The whitepaper subsection **«Заимствуемые паттерны MAGMA и MemMachine»** records
     five bounded candidates (M1–M3, MM1–MM2), their FVSC guardrails, and the required
     ablations. Treat them as post-pilot options and baselines, not as an authorized
     dependency or simultaneous implementation plan.
   Keep HTTP, plugin, and LLM dependencies outside the ingest layer. Do not commit
   vault data, voice data, or generated folders.
5. **Verify** — current owner-overlay checkpoint: **283 passed / 1 skipped / 11
   deselected**, legacy boundary green, Obsidian production build green, and unchanged
   frozen Gold/addendum files. GitHub Actions run 29708329826 for the preceding pushed
   source-boundary head is queued, not failed; push this tranche and wait for its own
   remote result.
   Draft PR #2 already exists and validates each pushed `integration/fvsc-core-v1`
   head; do not create or merge another PR without separate user instruction.

## Follow-ups (not blocking)

- Track `obsidian-plugin/package-lock.json` so CI can use `npm ci` (reproducible builds)
  and restore the `typecheck` job. It remains intentionally ignored in this checkpoint.
- Profile the plugin's debounced full-vault reconciliation and add a source-scoped
  endpoint only if live vault latency warrants the extra lifecycle surface.
- Port `core.viability_benchmark` and the `natural-language-live.yml` workflow once the
  benchmark modules are ported (Stage 5).
- **`benchmarks/results/` is absent on this branch** despite ADR-002 ("Negative results
  are recorded in `benchmarks/results/`, not hidden"). Port the registered negative
  results as a `chore(benchmarks)` commit in Stage 5 alongside the runners. None of the
  Stage-3 modules read them, so not a blocker.
- ✅ **Parser + provenance + vault ingest** now use only `src/fvsc/` contracts; the new
  modules do not import legacy `core/`, HTTP, plugin, visualization, export, or LLM code.
- Decide on `data/conceptnet_ru.json` (12.7 MB, tracked) — keep as a curated asset or
  untrack with a download fallback.
- Unify tests under `tests/{unit,integration,e2e}/` as subsystems port. Note: test dirs
  carry no `__init__.py` (foundation convention), so test-file basenames must be unique
  across the whole tree — `density/test_density.py` not `test_core.py` (collides with
  `containers/test_core.py`).
