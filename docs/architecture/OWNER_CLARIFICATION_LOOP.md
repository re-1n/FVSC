# On-demand owner clarification prototype

Implemented 2026-10-11. This is a user-triggered clarification loop in search,
not an automatic question planner or a validated improvement in usability.

## User flow

1. Write and synchronize notes as usual. Ingest asks no clarification questions.
2. Search in Antourage. On a source card, choose **Использовать как мою позицию…**.
3. Select a fragment in the original text, or use the whole short note. The UI shows
   the exact fragment and the search question before asking for a decision.
4. Choose **Это моя позиция**, **Согласен с чужой мыслью**, **Просто сохранил**,
   **Не уверен**, **Пропустить**, or write an explanation in your own words.
5. Reopening the same fragment/question shows the saved decision, not another
   question. **Изменить ответ** appends a correction while preserving history.

No reward, streak, forced choice or completion requirement is introduced. A skipped
question remains skipped until explicitly amended. Another question, source revision
or fragment is a different clarification target. Context matching is exact after
trimming outer whitespace; there is no semantic merging of questions.

## Meaning of the choices

| Choice | May this fragment represent the owner's position for this question? |
|---|---|
| My position | Yes, by explicit owner confirmation |
| Agree with another's thought | Yes, as agreement; authorship is unchanged |
| Merely saved it | No |
| Unsure | Unresolved |
| Free-form explanation | Unresolved; preserve the owner's wording without classifying it |
| Skip | Deferred; do not repeat automatically for this exact target |

An existing verified expression annotation with explicit endorsement/rejection can
avoid the question. Message authorship and adoption alone cannot. Any explicit
context-bound answer overrides the inherited annotation for this target.

`usable_as_owner_position` describes this narrow confirmation only. It is not proof
of relevance, entailment, direct authorship, historical continuity or current belief
outside the displayed context. It must never be substituted for `direct_owner`
eligibility from the [previous operation](../evaluation/OWNER_ATTRIBUTION_RESULTS_V1.md).

## Storage and API

The service lazily creates `.fvsc/clarifications.sqlite3` on first use. The SQLite
journal is separate from canonical sources, EvidenceLedger and proposal assessments.
It stores target identifiers, exact question text, fragment offsets/hash, choices,
free-form answers and timestamps. It does not copy source bodies. User-entered
questions and explanations may themselves contain sensitive text; they remain local.

Targets are identified by SHA-256 over source id, source revision, code-point span,
fragment hash and exact context question. Every prepare/answer verifies the source
against the synchronized runtime. Synchronize edits to invalidate old targets;
the journal does not independently watch the filesystem. Deleted sources are rejected.

- `POST /v1/clarifications/prepare`: `source_id`, `source_revision`, `start`, `end`,
  `question`. Returns the current decision and exact fragment; at most one question.
- `POST /v1/clarifications/answer`: `clarification_id`, `action`, optional `note`,
  `expected_sequence` (0 before the first answer). Returns the updated decision.

Answers are append-only in application code. Repeating the identical last answer is
idempotent. A different answer with a stale sequence is rejected, preventing a stale
card from overwriting a newer choice. SQLite transactions and a process lock protect
the single-service deployment. Multiple service processes sharing the journal are
not a supported deployment mode. The API uses the existing local-service trust model.

The browser maps UTF-16 selection indices to Python code-point offsets, accounting
for emoji and textarea newline normalization. The selected fragment is limited to
8192 code points; larger notes require an explicit selection.

## Verification and limits

- **40 Python tests passed**: new domain/API loop plus existing service, interpretation
  and owner-attribution regressions. Includes real vault persistence across service
  restart, unchanged source/ledger, stale revisions, idempotence and amendments.
- **4 frontend offset tests passed**, TypeScript checking passed, plugin bundled.
- The Windows sandbox denied pytest's default temporary directory. File-backed tests
  used a temporary fixture override creating unique directories under `.fvsc/` with
  inherited permissions; test assertions were unchanged.
- The sandbox also denied Node child-process spawning for `npm run build`. The plugin
  was bundled by invoking the installed esbuild executable directly with the same
  entry point, CJS/ES2020/node settings and external Obsidian/Electron dependencies.
- No live Obsidian UI session or human usability study was run. Type checking and
  offset tests do not establish layout, accessibility or lower interaction effort.

The general `/v1/interpret` path does **not** consume this journal yet. The UI states
this limitation. This prototype records and reuses clarification decisions; it does
not claim to correct generated answers. Free-form answers also need a separate,
reviewable interpretation step before they can authorize source use.

Next integration: provide an explicit owner-position answer mode that consumes only
current, context-matching decisions, cites both the source fragment and clarification
record, and preserves the distinction between agreement and authorship. Then compare
task time, repeated questions, attribution errors and abandoned interactions with
ordinary notes plus re-explanation. Do not claim a friction reduction before that test.
