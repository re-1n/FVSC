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

## Quick start

```bash
pip install -r requirements.txt

# Start the service
uvicorn service.app:app --host 127.0.0.1 --port 8765

# Open the interactive map + chat ("Антураж")
# http://127.0.0.1:8765/

# Sync an Obsidian vault into FVSC notes + HTML map + cache
python -m core.vault_sync --vault "/path/to/vault" --top 100

# Smoke test
python -m pytest service/tests/test_smoke.py -v

# Self-retrieval: ingest whitepaper and search it
python service/selftest.py
```

## Obsidian plugin (`obsidian-plugin/`)

Antourage is available as a native Obsidian plugin: TS frontend that
auto-launches the Python backend, embeds the map + chat inside Obsidian, and
keeps the map in sync with vault edits via a live watcher.

```bash
cd obsidian-plugin
npm install
npm run build
install-to-vault.cmd     # copies built artefacts into <vault>/.obsidian/plugins/fvsc-antourage/
```

Then enable «FVSC Antourage» in Settings → Community plugins and set the
Python interpreter / FVSC repo path. The status bar shows `● FVSC: up` when
the backend is ready. Edits to `.md` files are debounced and POSTed to
`/viz/file_ingest` so the map mutates without a manual rebuild.

## Service API

| Endpoint | Description |
|---|---|
| `GET  /viz` | Interactive map + chat UI (Антураж). cytoscape.js graph, SSE-driven highlights. |
| `POST /viz/ask` | SSE stream: tokens + highlight events from a local LLM (Ollama). |
| `POST /viz/file_ingest` | Live vault-watcher endpoint — create/modify/delete/rename a note. |
| `POST /viz/save_cache` | Force-save the in-memory space to `_fvsc_cache.pkl`. |
| `GET  /viz/concepts/{term}/sources` | Provenance drill-down: top-N notes that formed a concept's meaning. |
| `GET  /viz/silent` | Browse `silent_pool` — tokens uttered too rarely to enter the strong map. |
| `POST /spaces/{name}/ingest` | Ingest text (plain or Markdown) |
| `POST /spaces/{name}/retrieve` | Quantum retrieval: Tr(ρ_query · ρ_chunk) |
| `GET  /spaces/{name}/concepts/{term}/report` | Full concept report |
| `GET  /compare?a=X&b=Y` | Cross-space map comparison |
| ... | 18 endpoints total |

## Core modules

| Module | Purpose |
|---|---|
| `core/text_parser_agnostic.py` | Language-agnostic text → semantic_input |
| `core/semantic_input.py` | JSON structures → density matrices |
| `core/basis_vectors.py` | Orthogonal basis vectors (hash-based, deterministic) |
| `core/density_core.py` | SemanticSpace, Judgment, Component, Concept, ρ operations, `silent_pool`, `purge_source`, `ingest_one_file` |
| `core/thesaurus_prior.py` | ConceptNet/RuWordNet weak prior (bonus-only) |
| `core/provenance.py` | Per-file source attribution + silent_pool builder |
| `core/feedback.py` | Interactive FeedbackEngine |
| `core/vault_sync.py` | Walk Obsidian vault → SemanticSpace → concept notes + HTML map + cache |
| `core/export_to_vault.py` | Render concepts as Obsidian `.md` notes with wikilinks |
| `core/semantic_chat.py` | Terminal REPL chat about the map (uses local Ollama) |
| `core/llm/` | LLM client abstraction (Ollama backend, no new deps) |
| `service/viz_router.py` | `/viz` page + SSE chat + provenance + live `/file_ingest` |
| `service/viz_session.py` | Streaming `[[marker]]` parser → highlight events |
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
