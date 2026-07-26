# Stage 4d.1 — Real-data ingest correction

**Status:** Implemented on `integration/fvsc-core-v1` (2026-07-14).

## Why this checkpoint exists

Stage 4d passed deterministic lifecycle and cache acceptance, but a 658-record
Telegram export exposed semantic failures that synthetic file tests could not:

- hundreds of messages collapsed into monthly source documents;
- author, forwarding, reply, locator, and message boundaries disappeared;
- owner-authored material and participant comments shared one source kind;
- UTC month buckets disagreed with the author's Moscow timeline at midnight;
- a gold query about a rare metaphor was absent from the materialized vocabulary
  even though ordinary character-level retrieval found its source first.

The correction does not replace `EvidenceLedger`, lifecycle reconciliation, or
the JSON cache. It changes source granularity and keeps structural context before
another API or chat layer is built.

## Confirmed source contract

### One Telegram message is one source document

Every ordinary Telegram message receives a stable source id and revision. Monthly
periods remain metadata only. Message order in the export cannot change revisions.
Empty-text messages may remain as deferred media or locator records instead of
silently disappearing.

### Authorship is not inferred from forwarding

Owner identities are explicit caller configuration and safe-default to none.
Configured owner messages use the compatibility source kind `owner_reflection`,
meaning "owner-adopted expression", not a closed classification of content.
Participant comments remain `unknown`. Raw Telegram actor ids and names are not
persisted; opaque actor keys are.

An AI answer, quotation, or forwarded passage posted by the owner may therefore
be owner-adopted without being asserted as an external fact. Origin and adoption
are separate provenance fields.

### Replies and time are context, not document merging

`reply_to` remains an explicit structural relation between source records. A
configurable short time-gap relation may nominate nearby messages as context, but
is marked heuristic and never claims semantic equivalence. Source records are not
concatenated across either relation.

Unix timestamps are canonical. A configured IANA display timezone controls local
calendar metadata only; the accepted diary uses `Europe/Moscow`.

### Meaning is open-ended

No exclusive topic/content taxonomy is canonical. Observed source relations are
layer 0. Explicit metaphor mappings or linguistic assertions are layer 1. Model
interpretations are layer 2, retain message-level evidence, and remain rejectable.
The materializer must not turn structural source ids, actor ids, reply edges, or
locators into semantic concepts.

## Acceptance gates

- two messages in one month remain two independently revisioned documents;
- owner identities and participant comments stay distinct per message;
- forwarding never overrides configured authorship;
- reply targets and short-gap context survive as structural evidence;
- URL-only and deferred-media messages remain addressable;
- Moscow display dates do not inherit UTC month-boundary errors;
- export reordering is deterministic and duplicate message ids fail closed;
- no raw actor id/name or absolute personal path appears in persisted metadata;
- structural events do not enter the semantic snapshot;
- unchanged resync remains idempotent and message edits retract only that message's
  obsolete assertions;
- full Python suite, legacy-import boundary check, and remote CI pass.

## Gold acceptance

The first owner-defined question is: "What role do parasites play in my
metaphors?" The current snapshot materializes no `паразит*` form at its configured
concept cap. Stage 4d.1 does not hard-code an answer. It ensures the primary
message, its framing message, and its emotional reply can be retrieved and cited
as separate evidence before an open interpretation layer is evaluated.

## Real-data validation

The private Telegram export was used locally as an acceptance fixture and was not
committed. Its 658 records produced 645 addressable message documents: 614 configured
owner messages, 31 participant comments, and 13 skipped service records. The adapter
preserved 194 forwarding origins, 113 explicit replies, 313 short-gap context links,
and deferred 191 non-text records without discarding their identity.

The structural pass emitted 1,502 layer-0 events while excluding structural relations
from the 1,200-concept semantic snapshot. Replaying the unchanged export produced no
new lifecycle events.

For the first gold question, character n-gram TF-IDF ranked the primary source message
first and context expansion returned the three-message chain containing its framing,
metaphor, and reply. The current semantic snapshot still contains no `паразит*` concept
at its configured cap. Therefore Stage 4d.1 proves source fidelity and establishes a
retrieval floor; it does **not** demonstrate semantic superiority.

Validated checkpoints are `1bea6d7`, `f6f4389`, `48f9916`, and `7a7b175`.
The full suite reports **160 passed / 1 skipped / 11 deselected**, the legacy-import
boundary check passes, and GitHub CI is green at every checkpoint.
