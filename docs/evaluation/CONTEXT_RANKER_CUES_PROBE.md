# Reviewed retrieval-cues probe

## Status

Preregistered implementation probe. It does not promote a selector or a semantic
representation.

## Question

Can short, explicitly reviewed query paraphrases improve selection when a question and
an immutable semantic unit express the same meaning with different surface words,
without changing the compiler's guard, correction, isolation or fail-closed contract?

## Arms

- `B0`: Unicode character n-gram cosine over unit id and evidence text.
- `B1`: Unicode character TF-IDF over the same text; corpus-common n-grams are
  downweighted without adding semantic annotations.
- `C1`: the same ranker over unit id, evidence text and optional reviewed retrieval
  cues.
- `Ablation`: run `C1` units with cues disabled; this must reproduce `B0`.

The token budget, `top_k`, linked-unit expansion and compiler implementation must be
identical between arms.

An optional absolute score floor is a fail-closed control, not a ranker improvement.
It must be frozen on synthetic calibration data before a private evaluation. Candidates
below the floor are reported separately from bundles omitted by the token budget.
The first diagnostic floor is `0.20`, chosen before its private retrieval-only run. It
is deliberately provisional and may not be tuned on that run's per-question failures.

## Cue contract

- A cue is a retrieval annotation, not evidence and not owner meaning.
- Cues are omitted from rendered model context and citations.
- Cues must be non-empty, trimmed, unique and versioned with the unit set.
- A cue may paraphrase a reviewed unit but may not add an unsupported fact, voice,
  adoption decision or forbidden interpretation.
- Private evaluation questions must not be copied verbatim into cues after inspecting
  failures. Any private cue set requires a separate frozen authoring pass before
  scoring.

## First evaluation order

1. Synthetic fixtures covering surface-match distractors, paraphrases, mandatory
   guards, mandatory corrections, budget exhaustion, low-score rejection and
   fail-closed selection.
2. Freeze a cue set independently of scored private outputs.
3. Compare `B0`, `B1`, `C1` and the disabled-cue ablation on the same frozen questions
   and budget.
4. Report per-question oracle recall, empty selections, prompt tokens, latency,
   accepted/partial/rejected meaning review and every adoption/scope reversal.

## Gate

`C1` is retained as a candidate only if it:

- improves macro per-question oracle recall over `B0`;
- introduces zero adoption, scope or voice reversals;
- introduces zero unsupported or prohibited claims;
- preserves fail-closed behavior;
- does not increase the rendered token budget.

A one-dialogue deterministic run remains diagnostic even if all gates pass. Cues that
encode the evaluation questions, require post-result tuning or merely move Gold into
the retriever invalidate the comparison.

## Diagnostic results

The frozen private retrieval-only audit (no model generation) produced:

| Arm | Macro oracle recall | Empty questions | Decision |
|---|---:|---:|---|
| character cosine | 0.683 | 1 | retained baseline |
| character TF-IDF | 0.733 | 0 | not promoted |
| TF-IDF + frozen 0.20 floor | 0.650 | 2 | rejected |
| Qwen3-Embedding 0.6B | 0.533 | 0 | rejected |
| Qwen3-Embedding 0.6B + task instruction | 0.533 | 0 | rejected |

TF-IDF improved aggregate recall mainly on the abstention question, but filled a
previously empty question with an irrelevant positive unit. The absolute floor restored
that abstention while removing useful weak matches elsewhere. Therefore neither TF-IDF
nor a global lexical-score floor passes the safety/coverage gate. The result supports
testing a genuinely semantic local candidate or an independently authored reviewed-cue
set; it does not justify tuning the floor on individual private questions.

The local multilingual embedding candidate used the exact frozen Ollama tag
`qwen3-embedding:0.6b` and digest
`ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d`.
Raw query/document cosine and the model-author-recommended task-instructed query arm
produced the same macro recall. Both missed important reviewed units and neither fixed
the known empty lexical question. The 0.6B embedding arm therefore remains available
as an ablation but is not promoted or fused into the default.
