# Project status — 2026-07-14

## Where we are

- `main` (`ff703b7`) — frozen. The shippable MVP / plugin / Ollama line. **Do not modify
  or merge without explicit instruction.**
- `fix/security-and-integrity-hardening` (`1ade64d`) — 217-commit research monolith
  (ContainerCore v1, Voice R1, comparative benchmark, Draft PR #1). Frozen as a lab
  journal; archived by tag `experiment/container-core-v1` (pushed to origin).
- `integration/fvsc-core-v1` — **active.** Clean rebuild from `main`, carrying file
  states (not history) in logical blocks into the `src/fvsc/` layout.
  - Rebuild progress: Stage 0 (scaffold) ✅, Stage 1 foundation ✅, Stage 3
    representations ✅, Stage 4a–4c ingest foundation ✅, Stage 4d vault ingest ✅,
    Stage 4d.1 real-data ingest correction ✅, Stage 4e real-data semantic
    evaluation ✅, Stage 4f cited interpretation ✅, and Stage 4g thin local
    transports/Obsidian ✅. Checkpoint `e8a6d91` is pushed; GitHub Actions run 221 is
    green.
  - Working vault chain: `Obsidian Markdown -> SourceDocument -> EvidenceLedger ->
    MaterializedSnapshot -> atomic JSON cache`. Source replacement/deletion is
    append-only; source kinds remain explicit; cache stores no raw note body or absolute
    vault path.
  - Stage 4d.1 checkpoints: `1bea6d7` `f6f4389` `48f9916` `7a7b175`;
    **160 passed / 1 skipped / 11 deselected**, boundary check and GitHub CI green.
  - A 658-record private Telegram diary now produces 645 message-level documents while
    preserving configured owner adoption, participant comments, forwards, replies,
    deferred media, and Moscow calendar metadata. The diary itself is not committed.
  - The first gold query retrieves its primary message first with the lexical baseline
    and expands to the correct three-message context. The semantic snapshot misses the
    rare metaphor term, so semantic superiority is **not demonstrated**.
  - Stage 4e restores portable exact-relation Judgments, source-span citations,
    user-controlled interpretation views, feedback overlays, temporal contradictions,
    Gold 001–015, and reusable evaluation indexes. Full local suite:
    **193 passed / 1 skipped / 11 deselected**; boundary check green.
  - Across all 15 owner questions, lexical MRR@10/recall@10 is **0.5262/0.6389**;
    judgment-only is **0.2611/0.3778** and both tested fusions are worse than lexical.
    Exact structure is retained for explanation and feedback, but lexical remains the
    default source retriever. Semantic superiority is **not demonstrated**.
  - Stage 4f/4g adds content-addressed citations, independently reviewable L2/L3
    claims, forbidden-link evaluation, an atomic proposal/assessment journal, a
    strict loopback Ollama adapter, `VaultRuntime`, thin FastAPI routes, and a native
    Obsidian source/search/interpret/review view. Antourage output remains outside
    EvidenceLedger. Full local suite: **229 passed / 2 skipped / 11 deselected**;
    boundary check and production TypeScript build green.
  - The private Gold 001–015 retrieval rerun is unchanged: lexical remains default,
    no exact/hybrid arm is promoted, and negative hits remain zero.
  - Next: run actual Ollama proposals over Gold 001–015 and collect owner claim-level
    assessments. This is the first test of interpretation usefulness, not another
    architecture-building stage.

## Settled decisions (ADRs)

- ADR-001 EvidenceLedger is canonical.
- ADR-002 ContainerCore is experimental (no demonstrated superiority; density adds no
  AUC over structure-only).
- ADR-003 Density is an optional local state, not canonical.
- ADR-004 Antourage outputs are not owner evidence.
- ADR-005 Dream and narrative assets use sandbox branches.
- ADR-006 Semantic compression is referentially reversible, not text-invertible.

## Honest results on record

- Container bakeoff (Stack Exchange Workplace, 80 threads): best container vs direct
  graph ΔAUC −0.0079, paired CI95 [−0.049, +0.029] → `container_model_competitive`
  (no statistical superiority).
- Prior density-only bakeoff: `no_demonstrated_added_value`.
- Owner Gold 001–015: exact Judgment and hybrid retrieval do not beat the lexical
  source floor. No semantic arm is promoted.

These are **not** proof that density / containers are useless — only that the current
static materializer + shape metric did not earn their complexity for parser-edge ranking.
C5 validation is required before any promotion claim.

## Hard constraints

- Do not change / merge `main`; do not merge PR #1; do not delete the security branch.
- Do not claim density proven better; do not hide negative results.
- Do not auto-record LLM / Antourage output as owner evidence.
- Owner assessment of an Antourage claim is journaled separately; it does not mutate
  the original source or silently become an EvidenceEvent.
- Distinguish `dream_report` / `owner_reflection` / external fact.
- Do not claim semantic superiority from source retrieval alone; the owner must validate
  open interpretations and evidence links on a real-data gold set.
- Do not describe generated prose as text recovered from a semantic map. Exact wording
  is resolved from retained source revisions; map unfolding is a cited interpretation.
