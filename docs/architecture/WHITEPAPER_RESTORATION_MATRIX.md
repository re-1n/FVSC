# Whitepaper restoration matrix

**Scope:** incremental restoration on `integration/fvsc-core-v1`. This is not a
second rewrite. Stage 4d/4d.1 remains the accepted foundation.

## Non-regression boundary

The following contracts already work and must survive every restoration slice:

- one Telegram message is one independently revisioned `SourceDocument`;
- `EvidenceLedger` is the append-only source of truth;
- source replacement, deletion, and reactivation preserve history;
- author, forward, reply, time, locator, and deferred-media evidence stays
  structural and does not become semantic pseudo-concepts;
- the character n-gram retriever remains the real-data floor;
- raw diary/vault text, actor identities, and absolute personal paths are not
  committed or persisted in the derived cache;
- density and ContainerCore are currently optional views; a gold evaluation must earn
  their complexity, and a controlled negative comparison may retire them from active
  query plans.
- no scalar distance, density operator, container, graph, or embedding is treated as
  the universal representation of personal meaning; views declare the relations and
  operations they support [ADR-007].

## Delta from the whitepaper

| Whitepaper capability | Current clean rebuild | Incremental action |
|---|---|---|
| Original text and provenance | Message/file source ids, revisions, timestamps, structural context | Preserve source spans and hashes on extracted judgments; resolve text from the private source at query time |
| Exact `S -> V -> O` judgment | `EvidenceEvent` supports it, but document ingest emits only `fvsc:self` / `fvsc:contains` co-occurrence aggregates | Add a portable `Judgment` contract and a linguistic extractor beside the existing fallback |
| Negation, modality, condition, intensity | Event has scalar polarity/modality/intensity; richer fields exist only inside the optional density backend | Carry typed linguistic fields in event context without changing the ledger schema |
| L0-L3 interpretation spectrum | `interpretation_layer` and lifecycle exist | Make every derived assertion defeasible, source-cited, and independently retractable |
| Contradiction and meaning over time | Ledger can retain competing active assertions and source history | Add temporal comparison as a derived view; never overwrite disagreement |
| Owner correction | Retraction/supersession primitives exist; old feedback engine is quarantined | Add typed confirmation/rejection/contextualization commands over event ids |
| Metaphor, image, dream, and open meaning | Source kind and sandbox ADRs exist; no canonical topic taxonomy | Represent mappings as open, evidence-linked proposals; keep imagery and literal claims distinct |
| Evaluation | Stage 4d.1 established source fidelity and a lexical floor | Use private Gold 001-015, including negative/split decisions, to compare exact, graph, container, and density views |
| Chat/Ollama/Obsidian | Main contains an older MVP; clean service folders are mostly empty | Restore thin transports only after the evidence/evaluation contracts are accepted |
| One density space as the universal semantic substrate | Density, explicit containers, graph, relation transforms, tensor factors, temporal state, and metaphor mappings all occur in the whitepaper; density was incorrectly privileged as the sole structural object | Admit those operations as initial atlas candidates; promote, replace, or retire one view at a time on its own owner-gold task |

## Restoration order

1. Portable `Judgment` projection over `EvidenceEvent`.
2. Exact linguistic extraction with the agnostic co-occurrence parser retained as
   a cheap fallback and comparison arm.
3. Layered proposals, owner feedback, and temporal/contradiction views.
4. Private gold evaluator with citations, negative links, and abstention scoring.
5. Promote only a registered view that beats the relevant simple baseline on its
   owner-validated relation/query family while preserving citations; otherwise keep
   the baseline and expose the failure.
6. Restore service, chat/Ollama, visualization, and Obsidian as thin clients.

The restoration order does not require implementing every candidate geometry. The
owner-scored interpretation test classifies the next failure first; only then is one
matching view (for example contextual retrieval, directed inclusion, hierarchy,
temporal trajectory, or ambiguity state) selected for an ablation.

## New real-data constraints

The diary review adds four requirements that were implicit but not operational:

- **Meaning is not a closed class.** Classes may describe source or extraction
  mechanics, never exhaust the content of a thought.
- **Adjacency is evidence, not identity.** Replies and close timestamps nominate
  context, but do not merge messages or meanings automatically.
- **Adoption differs from origin.** Owner-posted AI text or quotation is an
  owner-adopted expression while its external origin remains visible.
- **Interpretation is controlled.** FVSC records semantic traces and differences
  between evidence and interpretation; the owner chooses the maximum layer used.

The system should prefer an abstention or a missing link over an invented one. A
rejected composite gold candidate is therefore first-class evaluation evidence,
not a failed annotation to discard.
