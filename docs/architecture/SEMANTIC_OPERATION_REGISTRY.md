# Semantic operation registry

> **Status:** accepted research-control document. A row names a testable operation,
> not a closed class of human meaning and not an implementation promise.

## Why the registry exists

FVSC does not first divide all human meaning into an exhaustive ontology. It records
canonical evidence, then asks which concrete operations must be performed over that
evidence. Different operations may require different mathematical views, and one
question may compose several views.

Every derived view is therefore registered by:

- the question or relation it is meant to support;
- the evidence and provenance fields it consumes;
- its candidate mathematical structure and simpler baseline;
- its uncertainty and abstention contract;
- owner-gold cases, forbidden links, quality and cost metrics;
- its status: `foundation`, `baseline`, `candidate`, `promoted`, `deprecated`, or
  `deferred`.

Canonical source identity, attribution and revision history are foundations. They are
not semantic views and cannot be traded away for a better aggregate score.

## Current registry

| ID | Operation | Foundation or candidate structure | Baseline / falsification target | Status |
|---|---|---|---|---|
| `F0` | Resolve an explicit source locator and exact revision/span | content-addressed source index | direct id lookup must be exact; no semantic ranker may override it | foundation; locator anchoring incomplete |
| `F1` | Distinguish transport author, text origin, owner adoption and embedded quotation | typed provenance envelope plus content-addressed expression spans | message-level author flag; zero false owner-authorship is required | foundation; selected for Stage 4h.1 |
| `O1` | Find lexically related usages | Unicode character TF-IDF | exact token/id lookup | baseline; current default |
| `O2` | Find an explicit predicate, negation, modality or condition | typed Judgment graph / hyperedges | lexical retrieval on the same candidate budget | candidate; current extractor loses many poetic fragments and does not beat `O1` |
| `O3` | Recover necessary discourse context without merging voices | reply/discourse graph plus bounded temporal intervals | source-only, reply-only and time-only expansion | candidate after `F1` |
| `O4` | Describe how an owner-recognized meaning or state changes over time | interval graph, typed trajectory and change points | date-filtered lexical evidence plus cited local synthesis | candidate |
| `O5` | Compare the function of a metaphor across usages | typed source-domain to target-domain mappings, optionally embedding-assisted | lexical usage clusters and raw-context model | candidate |
| `O6` | Test directed inclusion, hierarchy or asymmetric dependence | partial order, box/cone embedding, directed graph or local density/operator score | direct graph and lexical evidence | candidate; no universal container is promoted |
| `O7` | Find paraphrase or contextual usage similarity | contextual embeddings or local subspaces | character TF-IDF | candidate |
| `O8` | Preserve contradiction, modality and incompatible readings | signed constraint graph / typed hypergraph | independent cited claims without forced reconciliation | candidate |
| `O9` | Interpret a query term in the owner's usage, such as the intended scope of “самочувствие” | versioned personal usage/glossary view grounded in owner examples | general-language query as written | candidate after source-boundary correction |
| `O10` | Show similarities, differences and asymmetries between two people | aligned relation-conditioned personal views | raw-context model and flat profile similarity | deferred until two-party consent and single-owner validation |
| `S1` | Keep user-facing prose propositionally identical to validated cited claims, with explicit abstention | claim-first structured output plus deterministic renderer | independently generated answer plus claims | candidate for missing-link risk; rejected as global default after atlas over-abstention |
| `S2` | Preserve several independently relevant facets during cited synthesis | coverage plan over typed selected units | one-shot and claim-first cited synthesis | candidate; public phenomenon atlas frozen |
| `S3` | Normalize paraphrastic source relations against explicit question requirements before rendering | requirement-to-claim coverage map with supported/unsupported status | global claim-first and independent answer baseline | rejected: indexed end-to-end map failed held-out schema/coverage gate |
| `S4` | Fill a frozen question plan without losing or inventing requirements | one supported/unsupported cited slot per externally supplied requirement | indexed end-to-end requirement map | controlled capacity passed; automatic planning not evaluated |
| `S5` | Decompose a question into independently answerable requirements without source leakage | source-free QDMR-like ordered steps with typed operations and backward dependencies | implicit one-shot decomposition | v1 failed atomic-plan gate; dependency view retained, free emitted-slot boundary rejected |
| `S6` | Reject source-slot links that lack the explicitly requested relation | narrow typed relation-cue eligibility guard before deterministic slot rendering | unguarded `S4` planned-slot output on the same generation | promoted only for six registered English relations after public gate; unknown relations fail closed |

The candidate structure column is deliberately plural. A structure is promoted only
for the operation on which it wins; no row grants it universal semantic status.

## Composition contract

A query planner may compose rows, but it must keep their scores and uncertainty
separate. For example, “как изменялось самочувствие автора?” may require:

1. `O9` to resolve what the owner means by “самочувствие” in this task;
2. `F1` to exclude participant, lyric, quotation and unresolved-origin claims from
   owner-authored evidence;
3. `O1`/`O7` to nominate usages;
4. `O3` to recover only licensed context;
5. `O4` to order supported states and changes;
6. source-span verification before an L3 verbalization.

One score must not silently stand in for this chain. Each step records the source ids,
view version and reason for inclusion.

## Promotion protocol

For one selected operation:

1. freeze owner-gold cases and negative/forbidden links;
2. freeze the source corpus, candidate budget and simple baseline;
3. implement the smallest replaceable materializer;
4. compare quality, citation correctness, attribution safety, abstention, latency,
   update cost and storage;
5. promote only a repeatable operation-level gain; keep the simpler baseline on a tie;
6. test cross-view composition only after the individual view passes.

The current selection is not a new mathematical view. Stage 4h exposed an `F1`
foundation failure, so attribution and expression boundaries are corrected before
testing `O3`, `O4`, `O5` or `O9`.

