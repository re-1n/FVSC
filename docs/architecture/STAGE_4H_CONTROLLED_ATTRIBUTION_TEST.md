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

[ADR-004]: ../adr/ADR-004-antourage-outputs-are-not-owner-evidence.md
