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

A concept click opens that node and up to 16 neighbors in a stable radial layout in
the side panel. No camera animation, force simulation or automatic navigation is
triggered by receiving an answer. Clicking another node or **Назад** changes focus.
The panel exposes source links and an expandable edge list; truncated neighborhood
and source-list counts are shown. The layout is for navigation, not a visualization
of density-matrix distances or an exhaustive global semantic map.

Endpoints: `GET /v1/map?focus=...`, `POST /v1/map/mentions` (`texts` array). The map
is cached within the runtime and invalidated whenever runtime state is installed.

## Startup and verification

The plugin checks `/health` before spawning a service and reuses an existing instance
only if its normalized vault-path hash matches. This addresses the false `failed`
indicator from attempting a duplicate launch. An externally started service is not
terminated when the plugin unloads. Cold-start allowance is 90 seconds.

Checks: 64 Python tests (service, interpretation and Ollama adapter), 7 frontend tests
(concept click behavior, service identity and Unicode offsets), TypeScript checking
and esbuild bundling. No live Obsidian visual automation was available; final layout
and usability remain subject to the owner's interactive test.
