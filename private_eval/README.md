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

## Stage 4h challenge addendum

`fvsc_stage4h_challenge_001_002.json` is a separate two-case addendum. It does not
rewrite Gold 001–015 or the retrieval numbers already reported on that frozen seed.
The cases pin the two severe errors found by the earlier blind probe:

- a participant comment must not become evidence about the owner's wellbeing;
- a poetic source that does not establish whether its referent is real or fictional
  requires an explicit source-grounded abstention.

The referent case deliberately does not publish or pass a hidden real/fictional truth
label to the interpreter. It tests whether the system respects what the cited source
can establish. The addendum follows the same source-body-free publication boundary as
Gold 001–015.

## Frozen identity

- schema: `1`
- cases: `15`
- SHA-256: `609f92d2696490369c3dfaae9eeb598fde0c1b1e8bb3e2977e16ef5dca0a37e1`
- publication authorization: owner, 2026-07-15

Challenge addendum identity:

- schema: `1`
- cases: `2`
- SHA-256: `9fb043a20199d774aef9c2fcd3764aedaa70a724b74c15dd22043130e71ff665`
- publication authorization: owner, 2026-07-15

Any change to the JSON creates a new evaluation revision and must update the digest,
record why the gold decision changed, and avoid rewriting earlier reported results.
