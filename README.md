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

# Smoke test
python -m pytest service/tests/test_smoke.py -v

# Self-retrieval: ingest whitepaper and search it
python service/selftest.py
```

## Service API

| Endpoint | Description |
|---|---|
| `POST /spaces/{name}/ingest` | Ingest text (plain or Markdown) |
| `POST /spaces/{name}/retrieve` | Quantum retrieval: Tr(ρ_query · ρ_chunk) |
| `GET /spaces/{name}/concepts/{term}/report` | Full concept report |
| `GET /compare?a=X&b=Y` | Cross-space map comparison |
| ... | 11 endpoints total |

## Core modules

| Module | Purpose |
|---|---|
| `core/text_parser_agnostic.py` | Language-agnostic text → semantic_input |
| `core/semantic_input.py` | JSON structures → density matrices |
| `core/basis_vectors.py` | Orthogonal basis vectors (hash-based, deterministic) |
| `core/density_core.py` | SemanticSpace, Judgment, Component, Concept, ρ operations |
| `core/thesaurus_prior.py` | ConceptNet/RuWordNet weak prior (bonus-only) |
| `core/feedback.py` | Interactive FeedbackEngine |

## Key properties

- **Asymmetric containment**: A contains B ≠ B contains A
- **Polysemy as entropy**: S(ρ) = -Tr(ρ·log(ρ))
- **Recursive deepening**: concepts contain concepts that contain them back — fractal
- **Time decay**: степенной decay с архивацией (ACT-R + MINERVA 2)
- **Provenance**: каждое суждение отслеживается до исходного текста
- **Stenographic principle**: записывать что сказано, не додумывать

## Author

Created by **Rein** with the support of **Claude** (Anthropic).
