> Установка на русском: [INSTALL_RU.md](./INSTALL_RU.md)

# FVSC — Fractal-Vector Semantic Core

Deterministic personal semantic mapping through density matrices.

Records what words mean to a specific person — not what they mean in general.

Each concept becomes a density matrix operator. Containment, polysemy, and
semantic depth — all from linear algebra, no neural networks, no training.

## Architecture

```
Raw text (any language)
  → text_parser_agnostic (co-occurrence + sliding window)
  → semantic_input (concept tree with weights)
  → density_core (ρ matrices, recursive deepening, decay, consolidation)
  → compare_maps (cross-person alignment via Tr(ρ_A·ρ_B))
```

## Current development status

The branch `fix/security-and-integrity-hardening` contains a working local
Obsidian pilot with an append-only evidence ledger, immutable semantic states,
live vault synchronization, daily review feedback and chronological held-out
evaluation.

The implementation is **operationally ready for a controlled real-vault pilot**.
It is not yet evidence that FVSC is practically useful or that density-matrix
shape outperforms simpler graph or mass baselines.

- [Current project status](./docs/PROJECT_STATUS.md)
- [Next goals and stop conditions](./docs/NEXT_GOALS.md)
- [Daily pilot protocol](./docs/daily-pilot.md)
- [Semantic runtime roadmap](./docs/semantic-runtime-roadmap.md)
- [Staged voice-ingest integration plan](./docs/VOICE_INGEST_PLAN.md)

## Quick start

```bash
pip install -r requirements.txt

# Start the legacy service
uvicorn service.app:app --host 127.0.0.1 --port 8765

# Start the daily-pilot service
uvicorn service.pilot_app:app --host 127.0.0.1 --port 8765

# Open the interactive map + chat ("Антураж")
# http://127.0.0.1:8765/

# Sync an Obsidian vault into FVSC notes + HTML map + cache
python -m core.vault_sync --vault "/path/to/vault" --top 100

# Unit and end-to-end tests
python -m pytest -q

# Controlled viability diagnostic
python -m core.viability_benchmark --output artifacts/viability-report.json
```

## Obsidian plugin (`obsidian-plugin/`)

Antourage is available as a native Obsidian plugin: TS frontend that
auto-launches the Python backend, embeds the map + chat inside Obsidian, and
keeps the map in sync with vault edits via a live watcher.

```bash
cd obsidian-plugin
npm ci
npm run build
install-to-vault.cmd     # copies built artefacts into <vault>/.obsidian/plugins/fvsc-antourage/
```

Then enable «FVSC Antourage» in Settings → Community plugins and set the
Python interpreter / FVSC repo path. The status bar shows `● FVSC: up` when
the backend is ready. Edits to eligible `.md` files are debounced and sent to
the legacy visualization map and the append-only pilot ledger.

Pilot commands in the Obsidian command palette:

```text
FVSC Antourage: Pilot: rebuild semantic ledger
FVSC Antourage: Pilot: create daily semantic review
```

The rebuild also runs the chronological held-out evaluation and writes reports
under `.fvsc/` and `_fvsc_review/`. Generated reports are excluded from semantic
ingest.

## Service API

| Endpoint | Description |
|---|---|
| `GET  /viz` | Interactive map + chat UI (Антураж). cytoscape.js graph, SSE-driven highlights. |
| `POST /viz/ask` | SSE stream: tokens + highlight events from a local LLM (Ollama). |
| `POST /viz/file_ingest` | Live vault-watcher endpoint — create/modify/delete/rename a note. |
| `POST /viz/save_cache` | Force-save the legacy in-memory space. |
| `GET  /viz/concepts/{term}/sources` | Provenance drill-down: top-N notes that formed a concept's meaning. |
| `GET  /viz/silent` | Browse `silent_pool` — tokens uttered too rarely to enter the strong map. |
| `POST /pilot/rebuild` | Rebuild the append-only pilot ledger from eligible vault notes. |
| `POST /pilot/file_ingest` | Apply one live create/modify/delete/rename event to the pilot. |
| `GET  /pilot/concepts/{term}` | Concept state, provenance and related concepts. |
| `POST /pilot/trace` | Explain a shape relation with shared evidence references. |
| `GET  /pilot/daily-review` | Generate data for the daily semantic review. |
| `POST /pilot/review-feedback` | Persist checked daily-review ratings without re-ingesting the review. |
| `POST /pilot/evaluate` | Run chronological held-out comparison against simple baselines. |
| `GET  /pilot/readiness` | Report data sufficiency and practical-usefulness gates. |
| `POST /spaces/{name}/ingest` | Ingest text (plain or Markdown). |
| `POST /spaces/{name}/retrieve` | Quantum retrieval: Tr(ρ_query · ρ_chunk). |
| `GET  /spaces/{name}/concepts/{term}/report` | Full legacy concept report. |
| `GET  /compare?a=X&b=Y` | Cross-space map comparison. |

## Core modules

| Module | Purpose |
|---|---|
| `core/text_parser_agnostic.py` | Language-agnostic text → semantic_input |
| `core/semantic_input.py` | JSON structures → density matrices |
| `core/basis_vectors.py` | Orthogonal basis vectors (hash-based, deterministic) |
| `core/density_core.py` | Legacy SemanticSpace, Judgment, Component, Concept and ρ operations |
| `core/semantic_state.py` | Immutable evidence mass + normalized PSD semantic shape |
| `core/evidence.py` | Content-addressed append-only evidence events and lifecycle |
| `core/pilot_runtime.py` | Source replacement, snapshot materialization, related concepts and trace |
| `core/pilot_persistence.py` | Versioned atomic JSON persistence and restoration |
| `core/pilot_evaluation.py` | Chronological held-out evaluation and baseline comparison |
| `core/thesaurus_prior.py` | ConceptNet/RuWordNet weak prior (bonus-only) |
| `core/provenance.py` | Per-file source attribution + silent_pool builder |
| `core/feedback.py` | Interactive FeedbackEngine |
| `core/vault_sync.py` | Walk Obsidian vault → SemanticSpace → concept notes + HTML map + cache |
| `core/export_to_vault.py` | Render concepts as Obsidian `.md` notes with wikilinks |
| `core/semantic_chat.py` | Terminal REPL chat about the map (uses local Ollama) |
| `core/llm/` | LLM client abstraction (Ollama backend, no new deps) |
| `service/viz_router.py` | `/viz` page + SSE chat + provenance + live `/file_ingest` |
| `service/pilot_app.py` | Daily-pilot API entry point |
| `obsidian-plugin/src/` | TS plugin: lifecycle, backend control, settings, view, vault watcher |

## Key properties

- **Asymmetric containment**: A contains B ≠ B contains A
- **Polysemy as entropy**: S(ρ) = -Tr(ρ·log(ρ))
- **Recursive deepening**: concepts contain concepts that contain them back — fractal
- **Time decay**: степенной decay с архивацией (ACT-R + MINERVA 2)
- **Per-file provenance**: every Judgment carries the .md it came from; drill-down opens the source note in Obsidian
- **Silent pool**: tokens uttered too rarely to enter density-matrix are still recorded — the system knows what you "barely said"
- **Living map**: vault edits push incrementally; full rebuild restores precision
- **Stenographic principle**: записывать что сказано, не додумывать

## Author

Created by **Rein** with the support of **Claude** (Anthropic).