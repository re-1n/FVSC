# Project status — 2026-07-13

## Where we are

- `main` (`ff703b7`) — frozen. The shippable MVP / plugin / Ollama line. **Do not modify
  or merge without explicit instruction.**
- `fix/security-and-integrity-hardening` (`1ade64d`) — 217-commit research monolith
  (ContainerCore v1, Voice R1, comparative benchmark, Draft PR #1). Frozen as a lab
  journal; archived by tag `experiment/container-core-v1` (pushed to origin).
- `integration/fvsc-core-v1` — **active.** Clean rebuild from `main`, carrying file
  states (not history) in logical blocks into the `src/fvsc/` layout.

## Settled decisions (ADRs)

- ADR-001 EvidenceLedger is canonical.
- ADR-002 ContainerCore is experimental (no demonstrated superiority; density adds no
  AUC over structure-only).
- ADR-003 Density is an optional local state, not canonical.
- ADR-004 Antourage outputs are not owner evidence.
- ADR-005 Dream and narrative assets use sandbox branches.

## Honest results on record

- Container bakeoff (Stack Exchange Workplace, 80 threads): best container vs direct
  graph ΔAUC −0.0079, paired CI95 [−0.049, +0.029] → `container_model_competitive`
  (no statistical superiority).
- Prior density-only bakeoff: `no_demonstrated_added_value`.

These are **not** proof that density / containers are useless — only that the current
static materializer + shape metric did not earn their complexity for parser-edge ranking.
C5 validation is required before any promotion claim.

## Hard constraints

- Do not change / merge `main`; do not merge PR #1; do not delete the security branch.
- Do not claim density proven better; do not hide negative results.
- Do not auto-record LLM / Antourage output as owner evidence.
- Distinguish `dream_report` / `owner_reflection` / external fact.
