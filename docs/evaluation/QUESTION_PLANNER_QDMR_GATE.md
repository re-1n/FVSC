# Source-free QDMR-like question-planner gate

Status: public v1 completed; candidate failed and was not promoted.

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
view for question planning. The source formalism and BREAK benchmark are described in
Wolfson et al., “BREAK It Down: A Question Understanding Benchmark”:
<https://aclanthology.org/2020.tacl-1.13/>.

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

## Frozen run result

The run used `qwen2.5:14b-instruct-q4_K_M`, digest
`7cdf5a0187d5c58cc5d369b255592f7841d1c4696d45a8c8a9489440385b22f6`,
temperature `0`, and seed `42`.

| Diagnostic | Result |
|---|---:|
| Structurally valid plans | 10 / 12 |
| Exact atomic-plan case matches | 6 / 12 |
| Frozen requirement recall | 14 / 20 |
| Non-atomic requirement merges | 1 |
| Cases with invented emitted requirements | 2 |

The review compares only question-level obligations. It does not require literal
agreement with wording such as “routine” that appears in a prior frozen description
but not in the question itself.

The two schema failures were useful fail-closed detections: one `select` step illegally
referenced an earlier step and one `filter` step omitted its required reference. The
semantic failures were more important:

- former and current rules were merged into one `compare` requirement;
- a requested two-step response became two generic meta-requirements rather than one
  requirement per response step;
- a transfer was treated as internal setup, so only its motivating constraint was
  emitted;
- the network interruption itself was emitted as an answer requirement in addition to
  its requested cause.

## Decision

Do not connect v1 to the successful planned-slot synthesizer. The QDMR-like dependency
view remains a candidate, but `emits_requirement` is too weak as a free model decision.
The next candidate must derive answer-slot boundaries deterministically from explicit
question coordination, contrast, requested roles, and temporal pairs, while retaining
QDMR steps only as internal planning structure. It requires a new held-out gate; this
public set cannot promote a revised prompt.
