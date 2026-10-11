# Academic prior art for FVSC's open questions

Date: 2026-10-11. Scope: targeted triage of primary publication pages and abstracts,
with the full papers checked for PARC 3.0, ALCE and AMR-to-UMR. This is neither a
full-paper appraisal of every source nor a systematic literature review. It records
candidate methods and test designs; it does not promote a representation or report a
new FVSC experiment. Claims about transfer to FVSC are our inferences and require
checking against full methods, datasets and licences before adoption.

## Decision in brief

Research already provides useful *parts* of the solution: attribution annotations,
document-level semantic graphs, atomic claim and citation evaluation, usage-level
semantic-change tests, and mappings between graph formalisms. None of the reviewed
results establishes that one mathematical representation recovers a particular
person's meanings across all FVSC operations. In particular, a published improvement
on lexical ambiguity or generic question answering does not override FVSC's current
lexical retrieval baseline or its owner-reviewed evidence policy.

| FVSC question | Closest prior art | What transfers | Unresolved for FVSC |
|---|---|---|---|
| Who asserted what, including quotation? | PARC 3.0; discourse ATTRIBUTION | source/cue/content spans; frame/report distinction | owner adoption, external origin, nested/implicit reports in personal messages |
| How do we preserve every answer requirement with valid citations? | ALCE; FActScore; MEBench | separate coverage, claim support, citation and attribution scores | personal meaning, forbidden combinations, defensible abstention |
| What common semantic structure is useful across languages? | UMR; 2026 UMR parsing task | sentence/document graph and alignment baselines | robust automatic extraction and operation-specific value over lexical retrieval |
| How do views translate without pretending to be lossless? | AMR-to-UMR mapping | explicit category mappings and manual-gap accounting | general transition registry with provenance and measured losses |
| Can density represent ambiguity or temporal meaning? | Meyer & Lewis; semantic-change studies | a density ambiguity candidate; usage-level change evaluation | owner-validated senses, personal history, proof of gain over simpler views |

## 1. Attribution and reported content

**Established method.** [PARC 3.0 (Pareti, 2016)](https://aclanthology.org/L16-1619/)
annotates attribution relations with a source, cue and content span; the paper reports
roughly 20,000 relations and studies varied surface forms. This is a useful annotation
model for distinguishing a message author from the holder of an embedded statement.
Its own corpus analysis finds indirect reports to be the majority, so direct quotation
spans alone cannot cover the phenomenon.
[Maier (2023)](https://aclanthology.org/2023.dnd-14.6/) analyzes direct, indirect,
mixed and free indirect reports as a relation between a reporting frame and reported
content. It supplies a conceptual distinction, not a tested FVSC extractor.

**Local fit.** FVSC already verifies explicit external `ExpressionSpan`s and blocks
their cues from direct owner claims in the [F1/S6 audit](../evaluation/RELATION_GUARD_ATTRIBUTION_AUDIT.md).
It does not yet have a typed reported-claim operation. PARC's source/cue/content
annotation can inform such an operation, but PARC's news-text setting cannot by
itself settle owner adoption or endorsement. Those remain distinct FVSC fields.

**First candidate test.** Freeze public pairs with identical proposition text but
different holders: direct owner assertion, owner quotation of another person, owner
endorsement of that quotation, indirect report, and unresolved attribution. Score
holder identity, direct/reported claim eligibility, exact span linkage, false owner
attribution and abstention. Compare against the current F1/S6 behavior. An implicit
report must not be promoted merely because a reporting verb is present.

## 2. Answer completeness, citation and abstention

[ALCE (Gao et al., 2023)](https://aclanthology.org/2023.emnlp-main.398/) separates
answer correctness and citation quality in end-to-end retrieval plus cited generation.
Its *citation recall* asks whether emitted statements are fully supported by their
citations; this is different from FVSC's *required-facet recall*, which asks whether
the answer omitted a required statement. Both are needed to detect a concise but
incomplete answer.
[FActScore (Min et al., 2023)](https://aclanthology.org/2023.emnlp-main.741/)
decomposes generated text into atomic factual claims and checks their support. Its
support fraction is a precision-oriented diagnostic; by itself it cannot detect a
required facet the answer never mentioned.
[MEBench (2025)](https://aclanthology.org/2025.emnlp-main.77/) evaluates
cross-document multi-entity answering with attention to completeness, correctness and
entity attribution. [FanOutQA (Zhu et al., 2024)](https://aclanthology.org/2024.acl-short.2/)
is a released multi-hop, multi-document benchmark.

**Local fit.** FVSC's [coverage atlas](../evaluation/COMPOSITIONAL_COVERAGE_ATLAS.md)
already separates required-facet recall, prohibited combinations and citation
correctness. The literature supports keeping these axes separate. It does not license
replacing owner review with an automatic factuality score or using a generic answer
benchmark as proof of personal-meaning fidelity. The narrow six-relation `S6` gate is
still the only promoted relation-support operation.

**Next measurement, before another synthesis change.** On a new public held-out set,
report both required-facet recall and supported-claim precision; independently count
source/holder attribution, citation correctness, prohibited links, abstention and
latency. Keep frozen source sets identical across arms. A method that raises support
precision by omitting positive requirements should fail the gate. Reusing private Q07
for tuning is excluded by the existing evaluation record.

## 3. Semantic graphs and language coverage

[UMR's first dataset/infrastructure release (Bonn et al., 2024)](https://aclanthology.org/2024.lrec-main.229/)
defines sentence and document graphs covering predicate/argument structure plus
document-level coreference, time and modality across several languages. The
[2026 UMR parsing shared task](https://aclanthology.org/2026.dmr-1.12/) adds released
data and evaluation for seven languages, while explicitly identifying alignment and
document semantics as difficult. These papers make UMR a useful *baseline and
annotation vocabulary*, not a proven universal substrate for FVSC.

**Local fit.** FVSC has a loss-aware UMR subset importer and a small multilingual
capacity probe, but extraction and owner-meaning gains have not been established.
Compare an operation-specific UMR graph against exact Judgments and source text on the
same held-out cases. Score source alignment and attribution before semantic quality;
do not treat manually supplied UMR facts as automatic parsing performance.

## 4. Translation between representations

[Mapping AMR to UMR (Bonn et al., 2023)](https://aclanthology.org/2023.tlt-1.8/)
documents explicit mappings for categories shared by the formalisms and notes that
coverage newly introduced by UMR may need manual work. This is a concrete precedent
for FVSC's transition contract: name the source and target categories, what survives,
what is added or cannot be reconstructed, and the evidence supporting the result.

This does **not** establish a generic lossless converter among graphs, hypergraphs,
temporal trajectories and density operators. A candidate FVSC transition should have
an example-level loss table and a reverse-resolution check to source revisions. For
instance, projecting a three-participant event to pairwise edges must record whether
the event's joint participation remains recoverable. Until such tests exist, the
[atlas architecture](../architecture/SEMANTIC_ATLAS.md) remains a contract and
research plan rather than a completed transition engine.

## 5. Density and change over time

[Meyer and Lewis (2020)](https://aclanthology.org/2020.conll-1.21/) report density
matrix models for corpus-trained lexical ambiguity and word-sense discrimination.
That result supports an ambiguity-specific candidate; it does not show that FVSC's
deterministic personal density materializer identifies owner-recognized facets, or
that density should carry graph relations, time and attribution.

[Kutuzov et al. (2022)](https://aclanthology.org/2022.nejlt-1.9/) show that
contextualized semantic-change methods can confuse changes in contextual variance
with changes in lexical sense. The [LSCD Benchmark (2026)](https://aclanthology.org/2026.starsem-conference.10/)
organizes change evaluation through usage-pair judgments, usage graphs/sense groups
and comparisons over time. Both suggest testing *source-linked usages* before
interpreting movement of an aggregate vector, cluster or spectrum as a personal
change of meaning. Neither is a direct benchmark for a single person's narrative.

## Research decisions and next step

1. **Reuse annotation and evaluation ideas; do not import their conclusions.** The
   literature offers baselines and failure categories, not a replacement for
   owner-reviewed personal evidence.
2. **Prioritize a public attribution/reporting gate.** The latest F1/S6 checkpoint
   exposes a precise missing operation: reported content should be expressible without
   becoming a direct owner assertion. PARC and discourse attribution give enough
   structure to design the gate before implementing a parser.
3. **Keep answer coverage as the second track.** Adapt ALCE/FActScore/MEBench-style
   decomposed metrics to FVSC's already frozen requirement and forbidden-link policy;
   test on new cases, without reopening the exhausted private Q07 diagnostic.
4. **Defer new mathematical backends.** UMR, density and cross-view transitions need
   operation-specific held-out owner or public evidence before promotion. Record a
   transition's information loss explicitly when a concrete second view is tested.

No new model, dataset, parser or personal corpus was downloaded or run for this review.
The proposed gates above are research designs, not preregistered or executed results.
