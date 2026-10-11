# Dialogue and click-driven concept navigation

Implemented 2026-10-11 in the clean service and Obsidian plugin.

## Dialogue

Antourage now appends questions and answers to a scrollable conversation. A selector
reopens saved conversations; **Новый диалог** starts a separate one. Search has its
own result panel and does not erase the conversation. Older proposals without a
conversation id are available as a read-only archive of standalone questions.

Successful turns persist in the existing `.fvsc/interpretations.json` journal.
The plugin remembers the selected conversation in its existing settings. The service
returns the last 200 turns when reopening a conversation; the journal retains the
earlier ones. Failed requests stay visible during the session and leave the question
in the composer, but are not persisted as successful turns.

For a follow-up, the client sends up to six previous proposal ids. The service checks
their existence, distinctness, chronological order and conversation membership before
providing their questions/answers as a separate `dialogue_history` field to Ollama.
Each prior question/answer is bounded to 1024 characters. History is explicitly not
owner evidence. Fresh claims still require current source citations; old S-labels
are not reused. These instructions reduce confusion but are not a formal guarantee
of model compliance. Only preceding user questions expand lexical retrieval (up to
six questions, 2048 characters each);
model answers are not fed into retrieval as evidence.

Endpoints: `GET /v1/dialogues`, `GET /v1/dialogues/{id}`; `/v1/interpret` additionally
accepts `conversation_id` and `previous_proposal_ids`.

## Map

**Карта понятий** is an FVSC panel, separate from Obsidian's file-link graph. It reads
existing concepts from the materialized snapshot and subject/object relationships
from active evidence. It never invents nodes or uses LLM text to create graph edges.
Edges preserve relation, polarity, modality and links to their source records.
They are extractor assertions and can be wrong; they are not claims of ground truth.

Only exact whole-word/phrase matches to current concept names become clickable in
questions, answers and individual claims. Matching is case-insensitive and selects
the longest phrase. Unmatched text remains ordinary text. No fuzzy matching,
coreference or Russian inflection resolution is claimed. UI uses text nodes, never
interprets source/answer text as HTML.

A concept click now opens **Внутри понятия**, a recursive container of components
explicitly added by the owner. Its boundary represents the containing concept;
clicking a component enters that concept, and breadcrumbs / **На уровень выше**
return to an ancestor. An empty container means composition has not been described,
not that the concept is objectively atomic. **Связи понятия** shows the extracted
neighborhood (up to 16 neighbors), separately from owner-authored composition.

Add a component by name (including a new concept) or choose from suggested extracted
neighbors. Suggestions are not automatically accepted as components. Removing a
membership preserves the concept and its own contents. Shared components and cycles
are allowed; revisiting an ancestor returns to that level. Association clicks and
dialogue links start a new path, never an invented containment edge. **Мои понятия**
reopens authored concepts, including ones removed from another container.

Composition and its append-only add/remove history persist in vault-local
`.fvsc/containers.sqlite3`, separate from the canonical evidence ledger and sources.
This prototype uses exact NFC-normalized, trimmed labels as vault-local identities;
homonyms, contextual variants, rename/merge, and inference from composition are not
implemented. New authored labels are not yet included in dialogue auto-link matching.
Up to 100 direct components are supported per concept, with no imposed semantic
depth. Source-backed links between components preserve polarity/modality and remain
extractor assertions. At most 500 such edges are shown, with the total count visible.

The local force layout has repulsion, springs, damping and soft collision spacing.
Drag nodes or the background, zoom with the wheel or +/- buttons, pause physics, or
use **Вместить**. Dragging does not open a node. Physics stops on close/re-render;
receiving dialogue text never navigates the map. Coordinates are display positions,
not density-matrix distances. The engine is bundled and requires no network at runtime.
D3 Force was evaluated via its official documentation, but npm network access was
unavailable, so this version uses a small local implementation. It is not Obsidian's
own graph engine and does not claim identical physical behavior.

Endpoints: `GET /v1/map?focus=...`, `POST /v1/map/mentions` (`texts` array). The map
is cached within the runtime and invalidated whenever runtime state is installed.
Container endpoints: `GET /v1/map/container?focus=...`, `GET /v1/map/containers`,
`POST /v1/map/component` (`parent`, `child`, `present`).

## Startup and verification

The plugin checks `/health` before spawning a service and reuses an existing instance
only if its normalized vault-path hash matches. This addresses the false `failed`
indicator from attempting a duplicate launch. An externally started service is not
terminated when the plugin unloads. Cold-start allowance is 90 seconds.

Checks: 67 Python tests (service, interpretation and Ollama adapter), 10 frontend tests
(concept click/drag behavior, recursive paths, physics, service identity and Unicode offsets), TypeScript checking
and esbuild bundling. No live Obsidian visual automation was available; final layout
and usability remain subject to the owner's interactive test.
