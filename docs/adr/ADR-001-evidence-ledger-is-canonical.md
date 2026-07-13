# ADR-001: EvidenceLedger is the canonical memory

- **Status:** Accepted (2026-07-13)
- **Deciders:** Rein

## Context

Earlier FVSC iterations treated the density matrix as the core representation. Empirical
work showed density does not earn its complexity for the ranking task:

- Density-only bakeoff: `no_demonstrated_added_value` (density shape AUC 0.5607 vs
  direct-graph 0.5935, Δ −0.0328, CI95 [−0.0332, −0.0324]).
- Container bakeoff: density adds no AUC over structure-only.

We need a stable source of truth that outlives any single representation backend.

## Decision

The append-only **EvidenceLedger** is the canonical memory: statements, episodes,
sources, time, retraction, supersession, provenance. It is the source of truth. All
representations (graph, containers, density) are materialized FROM the ledger, never the
reverse.

## Consequences

- A representation can be rebuilt or swapped without losing memory.
- Retraction / supersession are first-class (no destructive edits).
- Provenance is mandatory for every event.
- Density matrices are demoted to an optional local backend (ADR-003).
