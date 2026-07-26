# Stage 4h.1 — source-boundary correction

## Decision

The first Stage 4h run generated its blinded review pack successfully. Owner review is
still incomplete and the blind map remains closed, so no arm, model or semantic view
is promoted from that run.

The first five qualitative reviews already reveal an arm-independent foundation
failure that does not require unblinding to correct:

- the interpreter receives source text and `source_kind`, but not the safe authorship,
  forwarding, adoption, reply or local-time metadata already held by ingest;
- an owner-sent message is treated as one undivided expression even when Telegram
  explicitly marks an embedded block quotation;
- transport authorship is therefore easy to mistake for authorship of every included
  lyric, quotation, translated passage or AI-produced block;
- the review pack does not show enough source metadata to audit this distinction;
- an explicit locator such as `Diary:747` is not guaranteed to anchor retrieval;
- citations normally cover a whole source message even when only a smaller span
  supports a claim.

These findings invalidate attribution-sensitive conclusions, but they do not show
which blinded retrieval arm is best. Existing private artifacts remain unchanged and
may still be fully scored as a record of the old contract.

## Correction order

### 1. Safe source-attribution envelope

Every prompt-visible source declares, without raw actor identifiers:

- `transport_author_role`: `owner`, `non_owner`, or `unknown`;
- whether the message is forwarded and whether its forward origin is known to be an
  owner identity;
- `owner_adopted_expression`, kept distinct from text authorship and literal
  endorsement;
- `text_origin_status`, defaulting to `unresolved` unless transport evidence or an
  explicit owner annotation licenses a narrower value;
- reply/context locators only when they can be represented without leaking identities.

`owner` transport authorship means “the owner sent/published this source”. It never by
itself means “the owner composed every substring”.

### 2. Content-addressed expression spans

Telegram `blockquote` entities become typed half-open spans over normalized source
text. A span stores offsets, its text digest, kind, origin status and derivation—not a
duplicate source body. It can be verified against the source revision just like a
Judgment citation.

Automatic ingest may identify an explicit quotation boundary. It must not guess that
plain text is a song, AI answer or the owner's own composition. Those distinctions
remain `unresolved` until an explicit annotation overlay or a separately evaluated
classifier provides evidence.

### 3. Prompt and review visibility

The local interpreter receives the safe envelope and verified span descriptors. Its
prompt must state that adoption, selection, origin and authorship are different
relations. The blinded review pack shows the same metadata, display time and a usable
logical locator while continuing to hide arm, model, ranker and telemetry.

### 4. Deterministic locator anchoring

An explicit logical locator is resolved before lexical or semantic nomination. If the
locator is absent or ambiguous, the system abstains or reports the unresolved locator;
it does not answer a different semantically similar question. Additional candidates
may supply context but cannot replace the anchor.

### 5. Owner annotation overlay

The implemented sparse overlay lets the owner mark verified spans as `quotation`,
`song_lyric`, `translated_external`, `ai_output`, `owner_commentary`, or
`unclassified`. It records three independent relations:

- origin: `owner`, `external`, `mixed`, or `unresolved`;
- owner relation: `authored`, `adopted`, `selected`, `not_adopted`, or `unknown`;
- owner endorsement: `endorsed`, `rejected`, `neutral`, `mixed`, or `unresolved`.

Each entry binds `source_id`, exact `source_revision`, half-open offsets and the span
digest. Partial overlap with an automatic span fails closed; the owner may replace an
exact automatic boundary with a more precise type. The overlay contains no source
body, is content-addressed by `overlay_id`, and never rewrites the document text or
revision. It is deliberately sparse: the owner annotates ambiguity that matters to a
test, not every sentence in the corpus.

Canonical JSON shape (placeholder values only):

```json
{
  "annotations": [
    {
      "source_id": "telegram/private-diary/messages/message-N.json",
      "source_revision": "<sha256>",
      "span": {
        "derivation": "owner-annotation:v1",
        "end": 20,
        "kind": "ai_output",
        "origin_status": "external",
        "owner_relation": "adopted",
        "start": 10,
        "text_sha256": "<sha256>"
      }
    }
  ],
  "overlay_id": "<canonical-payload-sha256>",
  "schema_version": 1
}
```

`owner_endorsement` is omitted when unresolved. The local validator recomputes every
digest and rejects stale, unknown, overlapping or body-bearing fields before any model
call.

## Rerun gate

A corrected pilot uses new corpus/retrieval/prompt identifiers and a new run id. Before
generation it must prove:

- every prompt source has a validated attribution envelope;
- every expression span verifies against the exact source revision;
- explicit locators resolve exactly;
- the owner annotation `overlay_id`, when used, is part of the immutable run id;
- source ids, author roles, forward roles and quote spans appear in the review pack;
- the old blind map has not informed candidate or prompt changes;
- no raw corpus, generated answer or owner review is committed.

Only after a complete blind review can the project choose one next semantic operation
from the [semantic operation registry](SEMANTIC_OPERATION_REGISTRY.md).

## Implemented checkpoint

The Stage 4h.1 checkpoints now provide:

- a typed, body-free attribution envelope that separates transport author, unresolved
  text origin, forwarding and owner adoption;
- content-addressed `ExpressionSpan` records for explicit Telegram block quotations;
- prompt v4 with attribution, message id, local display time, reply and temporal
  context labels;
- backward-compatible blinded review packs with source context and concrete scoring
  instructions;
- deterministic source-locator resolution before lexical or structural nomination;
- a revision-bound, body-free owner annotation overlay, prompt-visible endorsement
  distinct from adoption, and a no-model validation command.

The private 645-document acceptance corpus materializes 61 verified quotation spans.
On the private acceptance corpus, a two-span seed already validates the known song
lyric in message 681 and the AI continuation in message 725 without committing either
the corpus or the overlay. The next action is a new preregistered Stage 4h.1 run with
prompt v4 and that validated overlay; the original blind map remains closed.
