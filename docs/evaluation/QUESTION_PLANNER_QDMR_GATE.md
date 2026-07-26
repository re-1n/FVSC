# Source-free QDMR-like question-planner gate

Status: implementation candidate; public generation and frozen review pending.

## Question

Can a model recover the already frozen answer requirements from the question alone,
without seeing sources, inventing answers, or performing claim-to-evidence linkage?

## Candidate formalism

Operation `S5` receives only the question and emits an ordered QDMR-like plan. Each
step has a constrained operation (`select`, `project`, `filter`, `compare`, or
`boolean`), backward-only references, a neutral description, and a flag identifying
whether it directly emits an answer requirement. Internal setup steps are allowed.

This is a deliberately small adaptation of Question Decomposition Meaning
Representation, not a canonical FVSC meaning ontology. It is a replaceable derived
view for question planning.

## Boundary and review

- No source text, source identifiers, answers, support decisions, or EvidenceLedger
  state may enter the planner prompt.
- Structural validity is checked automatically and fails closed.
- Requirement recall, invented requirements, preserved contrast/condition/order, and
  semantic equivalence to the frozen question-only plans require a separately frozen
  review artifact.
- Planner output cannot be promoted from this reused public development set. A passing
  result only licenses a new held-out end-to-end planner-plus-slot gate.

## Run

Use `scripts/run_question_planner_gate.py` with a frozen model tag and digest. The
script refuses to overwrite an artifact and records the prompt version, identity,
seed, generation output, and telemetry.
