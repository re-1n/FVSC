# FVSC architecture

> Target architecture for the `integration/fvsc-core-v1` rebuild (2026-07-13).
> Canonical decisions live in `docs/adr/`.
> The project-level purpose, invariants, success criteria, and non-goals are defined in
> [`docs/PROJECT_PURPOSE.md`](../PROJECT_PURPOSE.md).

## Three layers

1. **Canonical evidence** — retained source revisions plus the append-only
   `EvidenceLedger` (statements, episodes, authorship, time, retraction, supersession,
   exact Judgments, and provenance). Source of truth. [ADR-001]
2. **Derived semantic atlas** — versioned, relation-conditioned views materialized from
   canonical evidence: lexical and exact indexes, graph paths, temporal projections,
   explicit containers, contextual vectors/regions, density state, and future
   backends. No view is universally privileged. [ADR-007]
3. **Cited interpretation and interaction** — query plans, defeasible L2/L3 proposals,
   owner review, HTTP/Obsidian/Antourage clients, and sandbox output. Generated content
   is not canonical owner evidence. [ADR-004, ADR-005]

> EvidenceLedger stores history. The semantic atlas exposes selected computable
> relations while every result remains resolvable to evidence. ContainerCore is one
> experimental directed view [ADR-002]; density is one optional local-state view
> [ADR-003]. Neither is the definition of meaning or canonical memory.

The atlas preserves the whitepaper's existing typed relations, relation transforms,
tensor-factor idea, graph view, contextual facets, recursive propagation, temporal
traces, metaphor mappings, and L0–L3 policy. The correction is that these capabilities
are not forced through one universal density operator. See
[`SEMANTIC_ATLAS.md`](SEMANTIC_ATLAS.md).

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
- Semantic scores declare their relation, context/time/layer scope, view version, and
  provenance. A universal distance or universal concept operator is not a core
  contract [ADR-007].
- Dream / narrative generation runs in sandbox branches, never in canonical memory
  [ADR-005].

## Separation across the repo

- **Production code** — `src/fvsc/`
- **Experimental runners** — `benchmarks/runners/` (ported later)
- **Registered results** — `benchmarks/results/` (kept; evidence of negative results)
- **Raw data** — `data/` (gitignored except small `fixtures/`)

[ADR-001]: ../adr/ADR-001-evidence-ledger-is-canonical.md
[ADR-002]: ../adr/ADR-002-containercore-is-experimental.md
[ADR-003]: ../adr/ADR-003-density-is-optional-local-state.md
[ADR-004]: ../adr/ADR-004-antourage-outputs-are-not-owner-evidence.md
[ADR-005]: ../adr/ADR-005-dream-and-narrative-use-sandbox-branches.md
[ADR-006]: ../adr/ADR-006-semantic-compression-is-referentially-reversible.md
[ADR-007]: ../adr/ADR-007-semantic-atlas-uses-relation-conditioned-views.md
