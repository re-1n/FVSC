# ADR-004: Antourage outputs are not owner evidence

- **Status:** Accepted (2026-07-13)

## Context

Antourage generates interpretations, simulations, proposals, and creative content. If
these silently became owner evidence, the canonical memory would be polluted with
non-fact.

## Decision

Antourage has **wide** rights to compute / simulate / generate / act, but **narrow**
rights to change the EvidenceLedger. Only an explicit user confirmation flow may produce
an `EvidenceEvent`. Outputs carry a type and a support level.

- **Types:** `evidence_reference`, `deterministic_computation`, `interpretation`,
  `owner_simulation`, `proposal`, `counterfactual`, `creative_artifact`, `action_request`.
- **Support levels:** `evidence_bound`, `partially_supported`, `free_generation`.

## Consequences

- LLM / Antourage text never auto-enters the ledger.
- `dream_report` and `owner_reflection` are distinct from external fact.
- Creative / sandbox output (ADR-005) is isolated from evidence.
