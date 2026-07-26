# Stage 4e — Real-data semantic evaluation

**Status:** implemented locally on `integration/fvsc-core-v1` (2026-07-14).
Remote CI for this checkpoint is pending explicit authorization to push the
repository changes; `main` and PR merge state remain untouched.

## What was restored

Stage 4d/4d.1 is unchanged. This stage adds compatible projections over its
message-level sources and canonical ledger:

- a portable whitepaper-style `Judgment` (`subject -> exact verb -> object`);
- source spans and hashes without persisting private sentence bodies;
- a lightweight Russian `pymorphy3` morphology adapter for negation, modality,
  conditionals, quantifiers, copulas, and adjective relations;
- explicit L1/defeasible marking for every heuristic judgment;
- owner/source/extractor/max-layer policies for derived semantic views;
- append-only owner feedback overlays (`confirm`, `reject`, `contextualize`);
- temporal histories and contradiction detection that retain both sides;
- an open-meaning gold schema with free owner interpretation, evidence citations,
  split/excluded decisions, and explicit negative links;
- reusable lexical and judgment indexes plus a deterministic fusion comparison.

The language-agnostic co-occurrence parser remains the compatibility fallback.
Exact extraction can be evaluated independently, but is not substituted for it.

## Private gold contract

The owner-reviewed set contains 15 questions, 53 resolved source references, and
five explicit `separate` links. Ten cases are accepted, four are split, and one is
open. Meanings are not assigned to a closed topic class. Gold mechanics describe
only evidence roles and whether links are supported, contextual, separate, or
unknown.

Examples of first-class negative evidence include:

- different trace thoughts must not be collapsed into one meaning;
- the metaphysical death-ocean is separate from the inner ocean with lighthouses;
- the raw lost-state poem is not a continuation of the qualia computation thread;
- notes about anonymous networks and network compulsion are not one composite
  thought merely because they occupy a related domain;
- AI/SCP elaboration keeps separate origin even when posted and adopted by the
  owner.

The gold JSON and Telegram export remain private and gitignored. The committed
runner accepts caller paths and owner ids; it contains no personal defaults.

## Real-data result

The same 658-record export produced 645 message sources, including 614 configured
owner messages. Of 431 owner messages with cleaned text, 262 (60.8%) yielded at
least one morphology-based judgment. The extractor emitted 2,165 judgments in
total (2,140 owner, 25 participant). A majority of owner judgments were adjective
relations (1,262), and manual inspection found noisy shallow SVO attachments.

Retrieval at `k=10` over all 15 questions:

| Arm | MRR@10 | Mean recall@10 | Context recall@10 | Negative hits |
|---|---:|---:|---:|---:|
| Character n-gram lexical floor | **0.5262** | **0.6389** | **0.3333** | 0 |
| Judgment-only | 0.2611 | 0.3778 | 0.1667 | 0 |
| Equal reciprocal-rank fusion | 0.4000 | 0.4000 | 0.3333 | 0 |
| Lexical 5:1 judgment fusion | 0.3950 | 0.5389 | 0.3333 | 0 |

No semantic or hybrid arm beats the lexical floor. Semantic superiority is not
demonstrated, and no fusion arm is promoted.

The failure is structural, not merely a tuning problem: primary poetic or
fragmentary sources for Gold 004, 011, and 013 produce no SVO at all. Original
text retrieval therefore cannot be replaced by judgment extraction.

## Compute profile

On the private corpus, isolated morphology ingest took about 5.4 seconds. The two
transient indexes took about 1.2 seconds to build. After index reuse, all 15
questions across four comparison arms took about 0.94 seconds. No LLM, remote API,
or persisted raw-text index was required.

## Architecture decision

1. **Lexical source discovery remains the default.** It is the accepted floor and
   currently the best source retriever.
2. **Judgments remain valuable evidence proposals.** They preserve exact verbs,
   logical envelopes, citations, feedback, timelines, and contradictions, but do
   not replace original text or claim complete meaning.
3. **Fusion stays off.** A semantic reranker must independently beat the floor
   before default behavior changes.
4. **Graph, ContainerCore, and density remain optional views.** They have no
   owner-gold natural-language source-ranking advantage to report; older registered
   bakeoffs are also non-superior.
5. **The next falsifiable layer is interpretation quality.** Retrieve original
   sources lexically, propose an L2 answer with exact citations, compare it with the
   owner's free-form interpretation and forbidden links, and keep it outside owner
   evidence until explicitly accepted.

This is the intended compression boundary: original evidence is retained; cheap
structure narrows and explains relations; higher interpretation is optional,
source-cited, and owner-controlled.
