> Установка на русском: [INSTALL_RU.md](./INSTALL_RU.md)

# FVSC — Fractal-Vector Semantic Core

Experimental personal semantic mapping with auditable evidence, provenance, local voice capture and density-matrix representations.

The current system records what words and relations appear to mean in a specific evidence history. Density matrices are an experimental semantic backend, not a validated claim of superiority.

## Architecture

```text
Raw text or reviewed owner speech
  → language-agnostic parser
  → immutable EvidenceEvent ledger
  → versioned SemanticState snapshots
  → density-shape, graph and mass baselines
  → Obsidian pilot, review and evaluation
```

## Current development status

The branch `fix/security-and-integrity-hardening` contains a working local Obsidian pilot with an append-only evidence ledger, immutable semantic states, live vault synchronization, daily review feedback, Voice R1 and chronological held-out evaluation.

The implementation is **operationally ready for controlled real-vault and real-audio pilots**. Engineering readiness is demonstrated; personal usefulness and density-matrix superiority are not.

Voice R1 provides bounded local audio import, explicit owner voice-memo sessions, WAV capture from Obsidian, deterministic decode/VAD, optional local `faster-whisper` ASR, transcript correction, explicit evidence promotion, provenance-preserving retraction and raw-audio retention. Real-time Antourage dialogue and calibrated owner-speaker verification remain R2/R3 work.

### Latest verified checkpoint

```text
commit: 7d0045be11b2d88aaa2dc6732e4e7f3298018cb9
GitHub Actions: 29186483448
```

Passed at that checkpoint:

- 51 Python tests;
- 12 integration/live tests intentionally deselected by the unit profile;
- end-to-end temporary-vault workflow;
- voice R1 import, VAD, correction, promotion, retraction, retention and ASR-failure recovery;
- public-thread benchmark schema/grouping/determinism checks;
- controlled viability benchmark;
- `npm ci`, TypeScript typecheck, production build and plugin packaging.

### First result on live public prose

Frozen Stack Exchange Workplace 2025 corpus:

- 1,068 attributed records in 194 leakage-grouped threads;
- known-positive coverage `0.8855`;
- 5,392,800 pairwise comparisons per model.

| Model | ROC AUC | Average precision |
|---|---:|---:|
| Direct parser graph | **0.5935** | **0.8281** |
| FVSC normalized density shape | 0.5607 | 0.7934 |
| Deterministic random | 0.4936 | 0.7749 |
| Trace mass | 0.3484 | 0.7201 |

FVSC delta versus the direct graph: `-0.032830`, paired bootstrap CI95 `[-0.033206, -0.032441]`.

Registered verdict: **`no_demonstrated_added_value`**.

The current matrix shape is above deterministic random, but reliably worse than the simpler direct graph on this proxy-labelled task. This does not disprove density matrices in general; it means the present materializer and metric have not justified their added complexity.

- [Current project status](./docs/PROJECT_STATUS.md)
- [Repository cleanup and branch policy](./docs/REPOSITORY_HYGIENE.md)
- [Next goals and stop conditions](./docs/NEXT_GOALS.md)
- [Daily pilot protocol](./docs/daily-pilot.md)
- [Public-language benchmark protocol](./docs/NATURAL_LANGUAGE_BENCHMARK.md)
- [First public-language result](./benchmarks/results/public-language-workplace-2025-r1.md)
- [Semantic runtime roadmap](./docs/semantic-runtime-roadmap.md)
- [Staged voice-ingest integration plan](./docs/VOICE_INGEST_PLAN.md)
- [Voice R1 pilot protocol](./docs/VOICE_R1_PILOT.md)
- [Real-time voice Antourage plan](./docs/VOICE_ANTOURAGE_PLAN.md)

## Quick start

```bash
pip install -r requirements.txt

# Optional local voice stack: faster-whisper + PyAV
pip install -r requirements-voice.txt

# Start the legacy service
uvicorn service.app:app --host 127.0.0.1 --port 8765

# Start the daily-pilot service
uvicorn service.pilot_app:app --host 127.0.0.1 --port 8765

# Open the interactive map + chat (Antourage)
# http://127.0.0.1:8765/

# Sync an Obsidian vault into FVSC notes + HTML map + cache
python -m core.vault_sync --vault "/path/to/vault" --top 100

# Unit and end-to-end tests
python -m pytest -q

# Controlled viability diagnostic
python -m core.viability_benchmark --output artifacts/viability-report.json
```

## Obsidian plugin (`obsidian-plugin/`)

Antourage is available as a native Obsidian plugin: a TypeScript frontend that auto-launches the Python backend, embeds the map and chat inside Obsidian, keeps the map synchronized with vault edits and exposes the Voice R1 workflow.

```bash
cd obsidian-plugin
npm ci
npm run build
install-to-vault.cmd     # copies built artefacts into <vault>/.obsidian/plugins/fvsc-antourage/
```

Then enable `FVSC Antourage` in Settings → Community plugins and set the Python interpreter / FVSC repo path. The status bar shows `FVSC: up` when the backend is ready.

Pilot and R1 voice commands in the Obsidian command palette:

```text
FVSC Antourage: Pilot: rebuild semantic ledger
FVSC Antourage: Pilot: create daily semantic review
FVSC Antourage: Voice: import audio file
FVSC Antourage: Voice: start/stop owner voice memo
FVSC Antourage: Voice: open transcript review queue
FVSC Antourage: Voice: emergency stop
```

The rebuild also runs chronological held-out evaluation and writes reports under `.fvsc/` and `_fvsc_review/`. Generated reports are excluded from semantic ingest. Raw voice audio is stored outside the vault by default.

## Service API

| Endpoint | Description |
|---|---|
| `GET /viz` | Interactive legacy map and Antourage chat UI. |
| `POST /viz/ask` | SSE stream from a local LLM backend. |
| `POST /viz/file_ingest` | Legacy live vault-watcher endpoint. |
| `POST /viz/save_cache` | Force-save legacy in-memory space. |
| `GET /viz/concepts/{term}/sources` | Provenance drill-down. |
| `GET /viz/silent` | Browse the legacy silent pool. |
| `POST /pilot/rebuild` | Rebuild the append-only pilot ledger from eligible vault notes. |
| `POST /pilot/file_ingest` | Apply one live create/modify/delete/rename event. |
| `GET /pilot/concepts/{term}` | Concept state, provenance and related concepts. |
| `POST /pilot/trace` | Explain a shape relation with shared evidence references. |
| `GET /pilot/daily-review` | Generate daily semantic review data. |
| `POST /pilot/review-feedback` | Persist review ratings without re-ingesting generated content. |
| `POST /pilot/evaluate` | Run chronological held-out comparison against baselines. |
| `GET /pilot/readiness` | Report data sufficiency and usefulness gates. |
| `GET /pilot/voice/status` | Report Voice R1 capabilities and repository state. |
| `POST /pilot/voice/import` | Import a bounded audio file or uploaded voice memo. |
| `POST /pilot/voice/sessions` | Start an explicit voice-memo lifecycle record. |
| `POST /pilot/voice/sessions/{id}/stop` | Stop a voice session idempotently. |
| `POST /pilot/voice/emergency-stop` | Stop the active voice session. |
| `POST /pilot/voice/captures/{id}/transcribe` | Retry retained audio after ASR becomes available. |
| `GET /pilot/voice/candidates` | List transcript-review candidates. |
| `POST /pilot/voice/candidates/{id}/correct` | Create a corrected immutable transcript revision. |
| `POST /pilot/voice/candidates/{id}/promote` | Explicitly promote reviewed owner speech into the ledger. |
| `POST /pilot/voice/candidates/{id}/retract` | Retract previously promoted voice evidence. |
| `DELETE /pilot/voice/captures/{id}/audio` | Delete raw audio while preserving transcript/evidence history. |
| `POST /spaces/{name}/ingest` | Ingest text into the legacy space API. |
| `POST /spaces/{name}/retrieve` | Legacy density-based retrieval. |
| `GET /spaces/{name}/concepts/{term}/report` | Full legacy concept report. |
| `GET /compare?a=X&b=Y` | Cross-space legacy map comparison. |

## Core modules

| Module | Purpose |
|---|---|
| `core/text_parser_agnostic.py` | Language-agnostic text → semantic input |
| `core/semantic_input.py` | Semantic input → vectors and density matrices |
| `core/basis_vectors.py` | Deterministic hash-based basis vectors |
| `core/density_core.py` | Legacy semantic space and density operations |
| `core/semantic_state.py` | Immutable evidence mass + normalized PSD semantic shape |
| `core/evidence.py` | Content-addressed evidence events and lifecycle |
| `core/pilot_runtime.py` | Source replacement, snapshots, related concepts and trace |
| `core/pilot_persistence.py` | Versioned atomic JSON persistence |
| `core/pilot_evaluation.py` | Chronological held-out evaluation and baselines |
| `core/natural_language_benchmark.py` | Attributed public-corpus fetch and evaluation |
| `core/voice_artifacts.py` | Immutable capture/transcript/candidate records and gates |
| `core/voice_ingest.py` | Decode, VAD, optional local ASR and review primitives |
| `core/voice_r1_repository.py` | Retention, ASR retry and raw-audio lifecycle |
| `core/voice_session.py` | Explicit voice-session state machine |
| `core/speaker_verification.py` | Future owner-verifier contract and conservative decisions |
| `service/pilot_app.py` | Daily-pilot API entry point |
| `service/pilot_voice_router.py` | Voice R1 import, review, promotion and retention API |
| `obsidian-plugin/src/voice.ts` | Local microphone capture and transcript-review UI |

## Current evidence policy

Project claims are separated into three levels:

1. **Engineering correctness:** demonstrated by the registered test and build suite.
2. **Predictive semantic value:** not demonstrated; current FVSC shape loses to the direct graph on the first public corpus.
3. **Personal practical usefulness:** not yet measured; requires real-vault ratings and real voice use.

The project can continue even if density matrices are eventually demoted. The evidence ledger, provenance, voice pipeline, Obsidian integration and operator architecture are representation-independent assets.

## Author

Created by **Rein** with the support of **Claude** (Anthropic).
