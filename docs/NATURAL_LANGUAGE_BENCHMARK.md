# FVSC public natural-language benchmark

_Last updated: 2026-07-12_

## Purpose

This benchmark tests parser and semantic-state robustness on ordinary public prose
that was not handcrafted for FVSC. It is not a personal map, does not measure whether
FVSC understands the vault owner, and must never write public posts into the personal
`EvidenceLedger`.

## Source decision

The initial adapter uses the Stack Exchange API rather than Reddit.

Reasons:

- Stack Exchange publicly documents CC BY-SA licensing by contribution date;
- every local record preserves author name/profile, post URL and license version;
- questions and answers can be fetched through a documented API with backoff/quota;
- the benchmark is evaluation-only and does not train an LLM;
- all records from one discussion thread remain on the same side of the split.

Reddit is deferred. Current Reddit Data API Terms grant a narrow revocable license for
display in an application and state that using user content for ML/AI training requires
rightsholder permission. The terms also require deletion of cached content and derived
models after termination. That is not a stable basis for a reproducible committed
benchmark without a separate agreement or an explicitly licensed dataset.

## Data boundary

The repository contains:

- corpus schema and validation;
- attributed Stack Exchange fetcher;
- HTML-to-prose normalization;
- thread grouping;
- deterministic evaluator and tests.

The repository does not contain downloaded posts. Local corpora belong under:

```text
data/public_corpora/
```

That path is ignored by Git. Evaluation reports contain aggregate metrics and hashes,
not raw source text.

## Fetch a corpus

Install the normal project dependencies, then run for a bounded date range. Example:

```bash
python -m core.natural_language_benchmark fetch-stackexchange \
  --site workplace \
  --from-date 2025-01-01 \
  --to-date 2025-12-31 \
  --pages 5 \
  --minimum-score 1 \
  --output data/public_corpora/workplace-2025.jsonl
```

The command:

1. requests questions with body text;
2. fetches answers for the selected question IDs;
3. removes code blocks while preserving normal prose and quote markers;
4. records author attribution and source links;
5. assigns CC BY-SA 2.5, 3.0 or 4.0 by contribution date;
6. writes deterministic UTF-8 JSONL;
7. reports the file SHA-256.

The API may return `backoff`; the fetcher waits as required. Repeated identical fetches
should not be sent more often than necessary.

## Run the benchmark

```bash
python -m core.natural_language_benchmark evaluate \
  --input data/public_corpora/workplace-2025.jsonl \
  --output artifacts/natural-language-workplace-2025.json \
  --train-fraction 0.8 \
  --bootstrap-samples 2000
```

All posts in one question thread are joined into one document. The thread's earliest
timestamp determines chronological order, so a question cannot be in train while one
of its answers is in test.

The report includes:

- corpus hash, record/thread counts and license distribution;
- attribution completeness;
- parseable thread count and parser relation count;
- skipped short/unparseable threads;
- quote-marker coverage;
- FVSC shape, direct graph, trace mass and deterministic random metrics;
- paired bootstrap interval and explicit verdict;
- no raw source text.

## First experiment

Use three separate, frozen corpora rather than one large mixed sample:

1. `workplace` — practical decisions, constraints and interpersonal reasoning;
2. `interpersonal` — explicit subjective interpretation and communication;
3. `worldbuilding` or `writers` — creative and hypothetical language.

Suggested first size per site:

- 300–1,000 attributed records;
- at least 100 parseable threads;
- a fixed date range ending before the experiment begins;
- no post selection based on FVSC results.

Do not combine sites until each individual report is inspected. Cross-site aggregation
can hide a parser failure in one register behind easier material from another.

## Manual audit

Parser-derived edges are not independent truth labels. Before interpreting AUC:

1. sample at least 100 extracted directed relations;
2. blind the reviewer to model score;
3. label each as supported, reversed, unrelated or ambiguous;
4. separately tag negation, question, quotation, reported speech and sarcasm;
5. calculate extraction precision and direction precision with intervals.

A model cannot be credited for predicting labels that the parser itself fabricated.

## Required baselines

The existing first pass compares:

- FVSC normalized shape;
- direct parser-edge frequency;
- trace mass;
- deterministic random score.

Before a strong claim, add and report:

- document-level TF-IDF cosine;
- PPMI/co-occurrence;
- a frozen general-purpose embedding cosine baseline;
- mass-matched and trace-matched subsets.

No unique FVSC value is demonstrated unless it beats the strongest simple baseline on
a held-out, leakage-controlled sample with a positive paired confidence interval.

## Stop conditions

Stop and fix the benchmark if:

- posts from one thread cross train/test;
- author/source/license attribution is missing;
- raw corpus files are committed accidentally;
- public text enters the personal pilot ledger;
- the date range or selection rule is changed after seeing results;
- deleted or inaccessible source content cannot be removed from the local corpus;
- manual audit shows low parser precision;
- CI becomes red at the branch head.
