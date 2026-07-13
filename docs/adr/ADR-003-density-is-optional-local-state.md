# ADR-003: Density matrices are an optional local state, not canonical

- **Status:** Accepted (2026-07-13)

## Context

Density matrices were the original core hypothesis. Benchmarks did not demonstrate added
value for parser-edge ranking. Density remains theoretically interesting for
non-commutative order-effects (C5-B) and context-local state.

## Decision

Density lives in `src/fvsc/semantic/density/` as a **swappable local-state backend**. It
is **never** canonical memory (that is the EvidenceLedger, ADR-001). It may represent the
local contextual state of a container.

## Consequences

- New code must not depend on density for correctness.
- Density is one of several backends (facet, graph, density, future operator backends).
- Order-effects ablations (full / diagonal / commuting / random / classical) gate any
  density promotion.
