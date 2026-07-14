# FVSC architecture

> Target architecture for the `integration/fvsc-core-v1` rebuild (2026-07-13).
> Canonical decisions live in `docs/adr/`.
> The project-level purpose, invariants, success criteria, and non-goals are defined in
> [`docs/PROJECT_PURPOSE.md`](../PROJECT_PURPOSE.md).

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

## Compression and unfolding

FVSC compresses meaning for computation, not source text for archival. The mapping from
sources to semantic structure is generally many-to-one, so the map is not expected to
reconstruct original wording by itself.

The required invariant is **referential reversibility** [ADR-006]: every material
semantic element resolves to a source id, revision, span or locator, integrity hash, and
derivation chain where applicable. Exact text comes from the retained canonical source,
not from a guessed inverse of a graph, vector, container, or density state.

There are therefore three separate operations:

1. **Source retrieval** returns exact retained text and context.
2. **Semantic traversal** computes over compact derived structure.
3. **Generative unfolding** verbalizes selected structure and sources as a new cited,
   defeasible proposal; it is not original-text recovery.

A standalone export may pair the map with a separate content-addressed source archive.
The archive must not be confused with the semantic representation.

## Package layout (`src/fvsc/`)

| Path | Responsibility |
|---|---|
| `evidence/` | events, ledger, provenance, lifecycle |
| `ingest/` | source adapters, source lifecycle, co-occurrence fallback, exact judgments |
| `retrieval/` | transient lexical floor, exact evidence lookup, experimental fusion |
| `evaluation/` | open-meaning gold mechanics and retrieval/interpretation metrics |
| `interpretation/` | cited L2/L3 proposals, owner assessments, separate local journal |
| `semantic/graph/` | graph baseline representation + materializer |
| `semantic/containers/` | ContainerCore (experimental) |
| `semantic/density/` | density-matrix optional local backend |
| `runtime/` | snapshots, persistence, evaluation |
| `voice/` | reviewed local voice (Voice R1) |
| `antourage/` | asset runtime, capabilities, outputs, proposals |
| `antourage/assets/` | Gardener, Proxy, Safeguard, Trace, Dreamer, Narrator |
| `antourage/sandbox/` | sandbox branches + simulations (dream/narrative) |
| `integrations/obsidian/` | Obsidian plugin bridge |
| `integrations/ollama.py` | strict local structured-interpretation backend |
| `service/` | HTTP service + routers |
| `legacy/` | quarantined superseded modules (new code must not import) |

## Boundaries

- New `src/fvsc/` code must not import `legacy/` — enforced by
  `scripts/check_no_legacy_imports.py` in CI.
- Antourage outputs are typed and never auto-become owner evidence [ADR-004]; only an
  explicit confirmation flow produces an `EvidenceEvent`.
- Current claim assessments are durable owner review metadata outside EvidenceLedger.
  Promotion into canonical evidence is deliberately not automatic.
- Original source text remains canonical. Lexical retrieval operates transiently over
  current `SourceDocument` objects; proposal journals store generated claims and hashes,
  not copies of source bodies.
- Semantic projections are referentially reversible but not required to be
  text-invertible [ADR-006].
- Dream / narrative generation runs in sandbox branches, never in canonical memory
  [ADR-005].

## Separation across the repo

- **Production code** — `src/fvsc/`
- **Experimental runners** — `benchmarks/runners/` (ported later)
- **Registered results** — `benchmarks/results/` (kept; evidence of negative results)
- **Raw data** — `data/` (gitignored except small `fixtures/`)
