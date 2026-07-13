# ADR-002: ContainerCore remains experimental

- **Status:** Accepted (2026-07-13)

## Context

ContainerCore v1 (explicit asymmetric containers, stages C0–C4) is implemented and
benchmarked. On the frozen Stack Exchange Workplace corpus (80 threads) it is competitive
with the direct-graph baseline but shows **no statistical superiority**: best-container
vs direct-graph ΔAUC −0.0079, paired CI95 [−0.049, +0.029]. The density component did not
improve AUC over structure-only — the observed effect comes mostly from explicit
asymmetric structure.

## Decision

ContainerCore ships as an **experimental** backend. It is not the default. Claims of
container superiority are prohibited until C5 validation (contextual polysemy,
order-effects, episodic reconstruction) shows a statistically reliable advantage.

## Consequences

- Default retrieval uses the graph baseline; containers are opt-in.
- Negative results are recorded in `benchmarks/results/`, not hidden.
- The C5 protocol must run before any promotion.
