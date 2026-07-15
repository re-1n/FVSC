# Released owner-gold seed

`fvsc_gold_001_015.json` is the owner-authorized evaluation seed for FVSC Stage 4h.
It contains 15 questions derived from posts in the owner's publicly accessible
Telegram channels, together with evidence roles, pairwise link boundaries, owner
interpretations, and explicitly rejected interpretations.

## Publication boundary

The released file contains:

- logical `Diary` references and local message-level `source_id` locators;
- positive, supporting, contextual, and negative evidence roles;
- owner-written questions, interpretations, and rejection constraints.

It does **not** contain raw Telegram message bodies, Telegram actor identifiers or
usernames, export metadata, absolute filesystem paths, model outputs, assessment
journals, access credentials, or the source corpus itself. A `source_id` is an opaque
locator resolved against the owner's local corpus; it is not a repository path and
does not make the benchmark independently reproducible without that corpus.

Other files created under `private_eval/`, including `interpretation_journal.json` and
generated reports, remain ignored unless the owner authorizes a separate reviewed
release.

## Frozen identity

- schema: `1`
- cases: `15`
- SHA-256: `609f92d2696490369c3dfaae9eeb598fde0c1b1e8bb3e2977e16ef5dca0a37e1`
- publication authorization: owner, 2026-07-15

Any change to the JSON creates a new evaluation revision and must update the digest,
record why the gold decision changed, and avoid rewriting earlier reported results.
