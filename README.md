> Установка на русском: [INSTALL_RU.md](./INSTALL_RU.md)

# FVSC — Fractal-Vector Semantic Core

Experimental personal semantic mapping with auditable evidence, provenance, local voice capture and explicit asymmetric semantic containers.

The current system records what words and relations appear to mean in a specific evidence history. The append-only evidence ledger is canonical. Graphs, recursive containers and density matrices are replaceable derived representations rather than assumed truths.

## Architecture

```text
Raw text or reviewed owner speech
  → language-agnostic parser
  → immutable EvidenceEvent ledger
  → explicit asymmetric containers and graph baselines
  → replaceable local state backend, including density matrices
  → Obsidian pilot, review and evaluation
```

## Current development status

The branch `fix/security-and-integrity-hardening` contains a working local Obsidian pilot, an append-only evidence ledger, immutable semantic states, Voice R1, chronological held-out evaluation and the first explicit `ContainerCore v1` implementation.

The implementation is **operationally ready for controlled real-vault and real-audio pilots**. Engineering readiness is demonstrated. Personal usefulness and superiority of any semantic backend are not.

Voice R1 provides bounded local audio import, explicit owner voice-memo sessions, WAV capture from Obsidian, deterministic decode/VAD, optional local `faster-whisper` ASR, transcript correction, explicit evidence promotion, provenance-preserving retraction and raw-audio retention. Real-time Antourage dialogue and calibrated owner-speaker verification remain R2/R3 work.

ContainerCore represents `A <- B` and `B <- A` as independent evidence-backed embeddings, supports bounded recursive activation, context-preserving path queries and exact evidence/path explanations, and keeps density matrices as optional local container state.

### Latest verified code checkpoint

```text
commit:                e05e923f2f13ac3d8f11a0c75a205629c1d8f7f6
standard test run:      29193677444
container live run:     29193677480
```

Passed at that checkpoint:

- 145 Python tests;
- 12 integration/live tests intentionally deselected by the unit profile;
- end-to-end temporary-vault workflow;
- Voice R1 import, VAD, correction, promotion, retraction, retention and ASR-failure recovery;
- explicit container contracts, asymmetric embeddings and retraction handling;
- context-sensitive cached paths, cycle protection and provenance explanations;
- deterministic graph/container/density ablation checks;
- controlled viability benchmark;
- `npm ci`, TypeScript typecheck, production build and plugin packaging.

### Density-only result on the complete public corpus

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

The current density-only materializer is above deterministic random but reliably worse than the direct graph on this proxy-labelled task.

### Explicit ContainerCore result

The first completed container ablation used a deterministic chronological 80-thread slice from the same frozen corpus:

- train/test: 64 / 16 threads;
- known-positive coverage: `0.7821`;
- 320 sampled positive and 320 sampled negative pairs;
- 6,400 pairwise comparisons per backend;
- semantic dimension: 16;
- recursion depth: 2;
- runtime: 39.71 seconds.

| Backend | ROC AUC | Average precision |
|---|---:|---:|
| Direct graph | **0.5716** | 0.5867 |
| Conditional graph | 0.5702 | 0.5709 |
| Container structure | 0.5637 | 0.5872 |
| Container projected density | 0.5631 | **0.5875** |
| Container hybrid | 0.5631 | 0.5869 |
| Density without containers | 0.5567 | 0.5558 |
| PPMI graph | 0.5509 | 0.5503 |
| Random | 0.5364 | 0.5148 |

Best container delta versus the best non-container backend: `-0.007891`.

Paired document-bootstrap CI95: `[-0.04890625, 0.02907617]`.

Registered verdict: **`container_model_competitive`**.

The explicit structure is competitive but not superior. The interval crosses zero. Projected density did not improve ROC AUC over structure-only containers, so the current matrix component has not earned additional complexity. This is a bounded preliminary test with proxy labels, not a validation of the full personal-semantics hypothesis.

- [Current project status](./docs/PROJECT_STATUS.md)
- [ContainerCore formal model](./docs/CONTAINER_CORE.md)
- [ContainerCore implementation plan and checkpoint](./docs/CONTAINER_CORE_IMPLEMENTATION_PLAN.md)
- [First ContainerCore real-language result](./benchmarks/results/container-core-workplace-2025-80threads-v1.md)
- [Repository cleanup and branch policy](./docs/REPOSITORY_HYGIENE.md)
- [Next goals and stop conditions](./docs/NEXT_GOALS.md)
- [Daily pilot protocol](./docs/daily-pilot.md)
- [Public-language benchmark protocol](./docs/NATURAL_LANGUAGE_BENCHMARK.md)
- [First density-only public-language result](./benchmarks/results/public-language-workplace-2025-r1.md)
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
| `core/container_core.py` | Explicit asymmetric containers and recursive projections |
| `core/container_query.py` | Cached context paths and evidence-backed explanations |
| `core/container_materializer_fast.py` | Signed-permutation projection baseline |
| `core/container_benchmark_cached.py` | Graph/container/density ablation |
| `core/voice_artifacts.py` | Immutable capture/transcript/candidate records and gates |
| `core/voice_ingest.py` | Decode, VAD, optional local ASR and review primitives |
| `core/voice_r1_repository.py` | Retention, ASR retry and raw-audio lifecycle |
| `core/voice_session.py` | Explicit voice-session state machine |
| `core/speaker_verification.py` | Future owner-verifier contract and conservative decisions |
| `service/pilot_app.py` | Daily-pilot API entry point |
| `service/pilot_voice_router.py` | Voice R1 import, review, promotion and retention API |
| `obsidian-plugin/src/voice.ts` | Local microphone capture and transcript-review UI |

## Current evidence policy

Project claims are separated into four levels:

1. **Engineering correctness:** demonstrated by the registered test and build suite.
2. **Density-only predictive value:** not demonstrated; the current density shape loses reliably to the direct graph on the complete public corpus.
3. **Explicit container predictive value:** competitive but not superior on the first bounded real-language slice.
4. **Personal practical usefulness:** not yet measured; requires real-vault ratings and real voice use.

The project can continue if density matrices are demoted. The evidence ledger, explicit container topology, provenance, voice pipeline, Obsidian integration and operator architecture are representation-independent assets.

## Author

Created by **Rein** with the support of **Claude** (Anthropic).
