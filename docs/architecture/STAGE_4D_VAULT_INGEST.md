# Stage 4d — Vault ingest

## Outcome

Stage 4d adds a deterministic, local-only path:

`Obsidian Markdown -> SourceDocument -> EvidenceLedger -> MaterializedSnapshot -> JSON cache`

`EvidenceLedger` is canonical (ADR-001). `MaterializedSnapshot` is the first derived
semantic-space view; graph, containers, and density may be rebuilt from the ledger.
Density is not required for ingest correctness and is not persisted as canonical memory
(ADR-003).

## Research code retained and rejected

Retain from the frozen research line:

- deterministic per-file vault walking and protected generated-directory exclusions;
- Markdown cleanup without importing Obsidian, HTTP, or LLM code;
- per-source provenance and the non-canonical silent pool;
- append-only source replacement/deletion lifecycle;
- versioned atomic cache writes and regular-file/symlink checks;
- explicit environment/CLI paths instead of author-specific defaults.

Do not carry forward:

- pickle or direct persistence of legacy `SemanticSpace` objects;
- direct imports from `core/` or `src/fvsc/legacy/`;
- visualization, concept-note export, plugin callbacks, FastAPI, or Ollama;
- Russian-only cleanup that deletes Latin text from a language-agnostic pipeline;
- hard-coded vault, Telegram, model, or ConceptNet paths.

## Contracts

### Source documents

Every input document has a POSIX-relative `source_id`, SHA-256 `source_revision`,
finite `observed_at`, adapter id, cleaned text, and an explicit source kind:

- `owner_reflection`;
- `dream_report`;
- `external_fact`;
- `unknown` (safe default; never silently promoted to owner evidence).

Obsidian source kind is read only from an explicit `fvsc_source_kind` or
`source_kind` frontmatter field. Parser-derived relations use interpretation layer 1
and keep the source kind in event context/provenance. They are not verbatim owner
assertions and LLM/Antourage output has no path into this ingest layer (ADR-004/005).

### Source lifecycle

- Re-scanning an unchanged vault is idempotent.
- Changed sources append retractions for obsolete active parser events, then append the
  new revision's assertions atomically.
- Deleted sources append retractions; history is never erased.
- Reconciliation only manages events created by the selected source adapter, so voice,
  manual, or future external evidence in the same ledger is untouched.
- Generated FVSC folders, `.obsidian`, trash, attachments, symlinks, and caller-defined
  exclusions are never ingested.

### Cache

The cache is trusted local derived state, but uses validated JSON rather than executable
pickle. It stores a versioned envelope, ledger records and digest, current relative source
revisions, semantic input, silent-pool metadata, and deterministic materializer metadata.
Writes use a same-directory temporary file, `fsync`, restrictive permissions where
available, and atomic replace. Raw note text and absolute vault paths are not persisted.

Default runtime location: `<vault>/.fvsc/cache.json`. `.fvsc/` is a protected generated
folder and must not enter source control or a subsequent ingest pass.

## Independent commit slices

1. `docs(ingest)` — this contract and acceptance gates.
2. `feat(ingest)` — `SourceDocument`, Markdown normalization, deterministic vault scan,
   explicit source kinds, protected exclusions.
3. `feat(ingest)` — semantic-input/provenance to `EvidenceEvent` adapter plus atomic
   change/delete/idempotent source reconciliation and materialization.
4. `feat(runtime)` — versioned atomic JSON vault cache with schema/digest validation.
5. `feat(ingest)` — local sync orchestration and CLI: load cache, scan, reconcile,
   materialize, save.
6. `feat(ingest)` — portable Telegram/exocortex JSON source adapter only; no vault
   writes, personal channel map, or direct semantic backend.
7. `docs(status)` — record Stage 4d completion and the next FastAPI checkpoint.

Each slice must pass the full Python suite and the legacy-import boundary check before it
is committed. Remote CI must be green before the next remote checkpoint is treated as
stable.

## Acceptance gates

- Synthetic vault end-to-end: create -> unchanged rescan -> modify -> delete -> reload.
- Ledger history and active view survive cache round-trip with identical digest.
- Snapshot id/state digest are reproduced from cached ledger records.
- Source revisions and provenance contain only relative ids; cache contains no raw note
  body or absolute vault path.
- Source kinds remain distinct in every generated assertion.
- No `core`, HTTP, plugin, LLM, visualization, or export import under the new ingest/cache
  modules.
- Full test suite, boundary check, and Obsidian-plugin CI build pass.
