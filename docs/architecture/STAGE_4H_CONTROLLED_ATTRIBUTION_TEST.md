# Stage 4h — controlled interpretation attribution test

## Purpose

Stage 4h answers one narrow question before FVSC builds another representation:

> How much of the observed usefulness comes from source retrieval and FVSC's explicit
> evidence contracts, and how much comes from the capability of the model that writes
> the answer?

The earlier conversational diary probe is encouraging but cannot answer this. The
owner agreed with many intended meanings and corrected at least two important errors:
a sentence was attributed to the owner although another participant wrote it, and a
fictional referent was treated as a real person. The probe did not freeze candidates,
record a model/version, or run an ablation. It is qualitative input to this protocol,
not a benchmark result.

## Non-goals

- prove that FVSC stores every human meaning;
- compare every possible geometry;
- train a specialized model before establishing the failure class;
- publish or commit raw diary bodies, actor identities, runtime journals, or model
  prompts/outputs that reproduce source bodies without a separate reviewed release;
- treat owner agreement as objective psychological truth.

## Frozen unit of evaluation

Each released owner-gold case contains:

- `question_id` and the exact owner question;
- allowed author/source-kind/time/layer scope;
- positive, context, negative, and forbidden-composition source ids;
- source authorship and known `real`, `fictional`, `hypothetical`, or `unknown` referent
  status where the corpus licenses it;
- an ordered, frozen candidate set for each retrieval arm;
- generated claims with exact citation ids;
- model id/version, prompt version, seed/options, latency, and token/count estimate;
- claim-level owner assessment and optional correction.

Raw source bodies are resolved locally at run time and excluded from committed results.
Committed summaries contain aggregate metrics and de-identified error classes only.

## Released evaluation seed

The owner has explicitly authorized publication of
[`private_eval/fvsc_gold_001_015.json`](../../private_eval/fvsc_gold_001_015.json),
because its thoughts derive from publicly accessible owner channels. The release
contains 15 questions, logical source locators and roles, owner interpretations,
rejected interpretations, and pairwise composition boundaries. It contains no raw
message bodies, actor identifiers/usernames, Telegram export metadata, model journal,
or source corpus. The corpus continues to resolve locally at run time.

The frozen release digest and boundary are documented in
[`private_eval/README.md`](../../private_eval/README.md). Publishing this owner-gold
annotation does not authorize future generated reports or journals automatically;
each broader release remains separately reviewed.

## Questions

Use the existing Gold 001–015 rather than inventing a new ontology. Ensure the frozen
set covers at least the already reviewed operation families:

- function of a recurring metaphor (including the parasites question);
- semantic/poetic continuation (including `Diary:605`);
- meaning and manifestations of a concept (including love);
- temporal change (including wellbeing);
- authorship/adoption and quoted or AI-origin wording;
- fictional, hypothetical, and real referents;
- a case where correct behavior is abstention.

## Experimental arms

Every generative comparison uses the same rendering schema and receives only its
declared frozen candidates.

| Arm | Candidates | Interpreter | What it isolates |
|---|---|---|---|
| `A0 lexical-extractive` | lexical top-k | deterministic cited snippets/relations | non-generative evidence floor |
| `A1 lexical-local` | same lexical top-k | configured local Ollama model | current intended product path |
| `A2 oracle-local` | owner-gold positive/context set | same local model | local interpretation ceiling when retrieval is correct |
| `A3 lexical-reference` | same candidates as A1 | declared strong reference model, only with owner-approved privacy scope | model-capacity gap |
| `A4 structural-local` | exact or registered hybrid top-k | same local model | whether current structure changes interpretation through retrieval |

`A3` is optional if source privacy does not permit an external model. It must never be
silently substituted for the local product arm. A model does not receive the full
corpus merely to make the reference result look strong.

## Owner review

Claims are reviewed independently as `accepted`, `partially_accepted`, `rejected`, or
`needs_revision`. The owner also records:

- whether the answer reflects the intended meaning rather than generic plausibility;
- whether each citation actually supports its claim;
- false owner attribution or adoption/origin collapse;
- unsupported real/fictional/hypothetical referent assumptions;
- forbidden joining of separate messages or narrative lines;
- missed necessary context;
- whether abstention was preferable;
- usefulness on a short ordinal scale frozen before the run.

Review metadata remains outside EvidenceLedger [ADR-004]. A correction may become new
owner evidence only through a separate explicit formulation/action.

## Metrics

Report per arm and paired per question:

- claim acceptance/partial/rejection rates;
- meaning-fidelity and usefulness scores;
- citation precision and positive/context citation recall;
- false-author and referent-status error counts;
- forbidden-composition and unsupported-claim counts;
- appropriate and missed abstention;
- retrieval recall/rank separately from interpretation quality;
- latency, context size, and estimated compute cost.

Thresholds for promotion are written into the private run configuration **before**
owner scoring. False owner attribution, fabricated citations, and forbidden composites
are high-severity errors and are never traded away for smoother prose by averaging them
into one score.

## Diagnosis matrix

| Observation | Primary diagnosis | Next action |
|---|---|---|
| A2 is weak | local model/prompt cannot interpret even correct evidence | revise prompt/schema or test another local model before any geometry |
| A2 strong, A1 weak | retrieval/context selection failure | improve one candidate view matching missed evidence |
| A3 much stronger than A1 on identical candidates | local model-capacity gap | choose a larger/local fine-tuned or distilled entourage; do not credit the atlas |
| A4 beats A1 with paired confidence | exact/structural retrieval adds value | promote only the responsible structural operation |
| A1 and A4 tie while lexical is cheaper | no demonstrated structural value | retain lexical default |
| citation support is poor across arms | evidence rendering/claim schema failure | fix citation contract before semantic representation work |
| authorship/referent errors persist with correct candidates | scope metadata or interpreter constraint failure | strengthen typed scope verification and abstention |

## Stop and continuation rule

Stage 4h ends with an error taxonomy and one decision. It may select **at most one**
next relation-conditioned view experiment. That experiment must declare its baseline,
ablation, owner-gold cases, materializer version, citation path, latency, and storage
cost before implementation.

If no view has a justified target, the correct next step is to improve the local
interpreter or keep the lexical/exact system—not to add another semantic substrate.

## Preregistered first pilot

The first executable run is diagnostic, not confirmatory:

- six questions: Gold 001 (parasites), Gold 008 (love/death/dissolution), Gold 010
  (`Diary:605` continuation), Gold 013 (formalization versus living meaning), plus the
  two separate Stage 4h challenge cases (wellbeing/authorship and unknown referent);
- `A0`, `A1`, `A2`, and `A4`; `A3` is deferred and no source body may leave the local
  machine under this pilot authorization;
- lexical/structural `top_k=10`, final prompt cap `12`, reply/temporal context depth `1`;
- one exact Ollama tag and digest for A1/A2/A4, `temperature=0`, `seed=42`, and
  `num_ctx=8192`, `num_predict=768`, and concise prompt version
  `source-cited-json-v2-concise` unless different values are frozen in the manifest
  before generation;
- zero tolerated fabricated/unsupported citations, false owner attribution,
  unsupported referent assumptions, or forbidden composites;
- A2 diagnostic target: accepted-or-partial claims `>=0.80`, citation precision
  `>=0.90`, median meaning fidelity `>=3/4`.

The manifest has `evaluation_mode=pilot`; code rejects promotion in that mode.
`confirmatory` requires at least 17 frozen cases, a positive paired bootstrap lower
bound, mean A4−A1 fidelity delta `>=0.5`, citation-precision drop `<=0.05`, no safety
regression, and latency at most `2x` unless a new protocol is preregistered.

### Pre-scoring text-eligibility correction

The first GPU execution at `0c2b2dd` produced no run directory, blind map, review, or
score. Before the atomic artifact write, the fail-closed runner found one invalid
prompt candidate: A4 context expansion for Gold 008 had retained adjacent
`message-697`, whose `ingest_status=deferred_media` and text body is empty. The model,
Ollama transport, and GPU were healthy; this was a deterministic corpus/candidate
contract defect rather than an inference failure.

Checkpoint `94e7730` corrects prompt eligibility without deleting evidence:

- textless records remain in the corpus digest and reply/temporal topology;
- optional context expansion skips records with no non-whitespace text in this
  text-only pilot, while continuing deterministically to the next eligible context;
- a direct lexical, structural, or owner-oracle candidate without text fails during
  candidate freezing instead of being silently removed;
- the runner resolves every frozen source and revision before the first model call, so
  a late invalid arm cannot consume generation compute and then prevent artifact output;
- retrieval identifiers now bind `text-context-v1` to distinguish the corrected
  candidate view.

This correction changes no question, gold decision, arm, ranker, threshold, model,
seed, context depth, or output cap. Because the failed attempt created no result or
owner-visible blinded output, the retry remains a diagnostic pilot rather than an
outcome-conditioned rerun. Two support entries with `source_id=null` in Gold 012 and
Gold 014 are intentionally unavailable locators, are excluded from oracle candidates,
and are outside the six-case pilot; they are not this failure mode.

## Local execution

List exact local model tags:

```bash
PYTHONPATH=src python scripts/stage4h_pilot.py models
```

Run the six-case pilot (repeat `--owner-id` for every owner identity in the export):

```bash
PYTHONPATH=src python scripts/stage4h_pilot.py run \
  --telegram "/path/to/result.json" \
  --owner-id "OWNER_ACTOR_ID_1" \
  --owner-id "OWNER_ACTOR_ID_2" \
  --model "EXACT_TAG_FROM_OLLAMA_LIST" \
  --num-predict 768 \
  --ollama-timeout 900
```

`--ollama-timeout` is a per-generation transport limit, not a model sampling option.
The pilot defaults to 900 seconds because CPU-only local inference can exceed the
general interactive adapter default of 180 seconds. Successful runs still record the
actual wall time and Ollama token/duration telemetry for every generated arm.

`--num-predict` is a manifest-bound output cap. It prevents an invalid or overly
verbose JSON continuation from consuming the full context window. The first CPU-only
attempt exposed the missing cap by decoding 572 tokens at about 1.12 tokens/second
without completing before the 900-second transport timeout; it produced no result
bundle and therefore did not enter owner scoring. Prompt v2 additionally requests one
to three concise claims so the cap constrains runaway output rather than silently
truncating the intended response shape.

The command resolves the installed model digest, freezes the corpus and every
candidate rank/revision, runs the paired local arms, and writes one new directory under
ignored `.fvsc/stage4h/<run-id>/`:

- `manifest.json`, `candidates.json` — source-body-free run identity;
- `results.json` — generated raw proposals and telemetry, local only;
- `review-pack.json` / `review-pack.md` — arm-blinded claims and exact local excerpts;
- `blind-map.json` — withheld arm mapping;
- `reviews.template.json` — copy to `reviews.json` and replace every `null` only after
  reviewing the blinded pack.

Score a completed review file:

```bash
PYTHONPATH=src python scripts/stage4h_pilot.py score \
  --run-dir ".fvsc/stage4h/<run-id>" \
  --reviews ".fvsc/stage4h/<run-id>/reviews.json"
```

`report.json` contains aggregate/de-identified metrics and one diagnosis. Raw results,
excerpts, blind mappings, and owner reviews remain ignored. Publishing any of them is a
separate owner-reviewed action.

[ADR-004]: ../adr/ADR-004-antourage-outputs-are-not-owner-evidence.md
