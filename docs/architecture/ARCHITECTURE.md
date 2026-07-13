# FVSC architecture

> Target architecture for the `integration/fvsc-core-v1` rebuild (2026-07-13).
> Canonical decisions live in `docs/adr/`.

## Three layers

1. **EvidenceLedger** — append-only canonical memory (statements, episodes, sources,
   time, retraction, supersession, provenance). Source of truth. [ADR-001]
2. **ContainerCore** — explicit asymmetric containers + directed nestings (A←B ≠ B←A).
   Semantic-structure layer. **Experimental.** [ADR-002]
3. **Local state** — swappable backend: facet distribution / graph / density matrix /
   other operator backend. Density is **optional local state**, never canonical. [ADR-003]

> EvidenceLedger stores history; ContainerCore stores compositional structure; density
> matrices may store local contextual state of containers. Matrices are not canonical
> memory.

## Package layout (`src/fvsc/`)

| Path | Responsibility |
|---|---|
| `evidence/` | events, ledger, provenance, lifecycle |
| `semantic/graph/` | graph baseline representation + materializer |
| `semantic/containers/` | ContainerCore (experimental) |
| `semantic/density/` | density-matrix optional local backend |
| `runtime/` | snapshots, persistence, evaluation |
| `voice/` | reviewed local voice (Voice R1) |
| `antourage/` | asset runtime, capabilities, outputs, proposals |
| `antourage/assets/` | Gardener, Proxy, Safeguard, Trace, Dreamer, Narrator |
| `antourage/sandbox/` | sandbox branches + simulations (dream/narrative) |
| `integrations/obsidian/` | Obsidian plugin bridge |
| `service/` | HTTP service + routers |
| `legacy/` | quarantined superseded modules (new code must not import) |

## Boundaries

- New `src/fvsc/` code must not import `legacy/` — enforced by
  `scripts/check_no_legacy_imports.py` in CI.
- Antourage outputs are typed and never auto-become owner evidence [ADR-004]; only an
  explicit confirmation flow produces an `EvidenceEvent`.
- Dream / narrative generation runs in sandbox branches, never in canonical memory
  [ADR-005].

## Separation across the repo

- **Production code** — `src/fvsc/`
- **Experimental runners** — `benchmarks/runners/` (ported later)
- **Registered results** — `benchmarks/results/` (kept; evidence of negative results)
- **Raw data** — `data/` (gitignored except small `fixtures/`)
