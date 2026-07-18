# Project status — 2026-07-18

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
    evaluation ✅, Stage 4f cited interpretation ✅, Stage 4g thin local
    transports/Obsidian ✅, and the semantic-representation audit ✅. Audit checkpoint
    `f5cdefa` passed GitHub Actions run 223. Stage 4h harness checkpoint `2fc1c66`
    passed GitHub Actions run 225; draft PR #2 tests every pushed branch head.
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
  - Gold 001–015 is now released at
    [`private_eval/fvsc_gold_001_015.json`](../../private_eval/fvsc_gold_001_015.json)
    with explicit owner authorization. It contains questions, logical source locators,
    roles, owner interpretations, rejected readings, and link boundaries—not raw
    Telegram bodies, actor identities, the source corpus, or the interpretation journal.
  - The separate source-body-free Stage 4h challenge addendum now freezes the two
    severe blind-probe boundaries without rewriting Gold 001–015: a participant's
    hope comment is negative evidence for owner wellbeing, and the text of
    `Diary:747` licenses neither a real-person nor a fictional-person assertion.
  - The released Gold 001–015 retrieval rerun is unchanged: lexical remains default,
    no exact/hybrid arm is promoted, and negative hits remain zero.
  - A conversational blind-question probe over the private diary produced useful
    interpretations and substantial owner agreement, but also exposed a false owner
    attribution and an unsupported real-person assumption for a fictional referent.
    The probe did not log a frozen candidate set, model/version, output, or ablation
    through the FVSC runtime. It is qualitative design evidence, **not** a benchmark and
    not proof that FVSC rather than the strong surrounding model produced the result.
  - The whitepaper representation audit preserves its exact Judgments, directed
    containers, relation transforms, tensor factors, graph view, recursive propagation,
    temporal traces, metaphor mappings, and L0–L3 policy. ADR-007 removes only the
    unsupported privilege of one universal density space and organizes those existing
    constructs as a provenance-grounded atlas of relation-conditioned views.
  - Stage 4h execution infrastructure is implemented in eight independent commits:
    content-addressed run/threshold contracts; a separate two-case challenge addendum;
    corpus/candidate freezing for A0/A1/A2/A4; exact Ollama tag/digest, seed, token and
    duration telemetry; one paired local runner; keyed arm-blinded owner-review packs;
    paired scoring/diagnosis with safety gates; and the local `stage4h_pilot.py`
    run/score workflow. Gold interpretations are never prompt input, A4 cannot fall
    back to lexical, source revisions are rechecked immediately before generation,
    and raw outputs/excerpts remain under ignored `.fvsc/stage4h/`.
  - Runtime hardening now binds a 900-second per-request timeout and
    `num_predict=768`. The first capable-GPU attempt at `0c2b2dd` then exposed one
    pre-scoring candidate defect: Gold 008/A4 context expansion admitted adjacent
    media-only `message-697` with an empty body. The fail-closed guard stopped the run
    before any artifact or blind map was written, so this is not a pilot result.
    Checkpoint `94e7730` retains the media record in corpus topology but excludes it
    from the text-only prompt view, preflights every frozen source before generation,
    and versions the corrected retrieval identifiers. On the exact 645-document local
    corpus, all 24 frozen case/arm sets now contain zero empty prompt candidates.
  - The preregistered first run is a six-question diagnostic pilot (18 possible
    generative variants across A1/A2/A4; A0 is automatic). `A3` is deferred because no
    external-source privacy scope has been authorized. Pilot mode cannot promote a
    representation; confirmatory mode requires at least 17 cases and every registered
    quality, citation, safety, confidence, and latency gate.
  - Current local verification after the text-eligibility correction: **259 passed /
    2 skipped / 11 deselected**. The earlier harness checkpoint `2fc1c66` passed GitHub
    Actions run 225; each new integration head is rechecked by draft PR #2.
    This repository-side environment does not run the owner-scored Ollama pilot; local
    candidate construction and CI verify the harness while raw sources remain private.
  - Next: retry the controlled six-question pilot on the owner's local Ollama machine
    from `94e7730` or later,
    complete the blinded claim/citation review, and use the diagnosis to select at most
    one next view experiment—or retain lexical/improve the interpreter.

## Settled decisions (ADRs)

- ADR-001 EvidenceLedger is canonical.
- ADR-002 ContainerCore is experimental (no demonstrated superiority; density adds no
  AUC over structure-only).
- ADR-003 Density is an optional local state, not canonical.
- ADR-004 Antourage outputs are not owner evidence.
- ADR-005 Dream and narrative assets use sandbox branches.
- ADR-006 Semantic compression is referentially reversible, not text-invertible.
- ADR-007 Semantic computation uses a provenance-grounded atlas of
  relation-conditioned views; no derived representation is universally privileged.

## Honest results on record

- Container bakeoff (Stack Exchange Workplace, 80 threads): best container vs direct
  graph ΔAUC −0.0079, paired CI95 [−0.049, +0.029] → `container_model_competitive`
  (no statistical superiority).
- Prior density-only bakeoff: `no_demonstrated_added_value`.
- Owner Gold 001–015: exact Judgment and hybrid retrieval do not beat the lexical
  source floor. No semantic arm is promoted.
- The conversational owner probe suggests that cited synthesis can be useful, but it
  cannot yet separate the contribution of retrieval/structure from the capability of
  the surrounding model. Two corrected failure modes—authorship and fictional/real
  referent status—are required Stage 4h checks.

These are **not** proof that density / containers are useless or that a unified tensor
representation is impossible. They show that the current materializers and operations
did not earn universal status or added complexity on their registered tasks. Each
future view requires a relation-specific validation before promotion.

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
- Do not describe one distance, matrix, embedding, graph, or container as the complete
  representation of personal meaning. Preserve whitepaper constructs as candidate
  views and promote only measured operations.
