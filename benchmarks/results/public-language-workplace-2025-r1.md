# Public natural-language benchmark: Workplace 2025 R1

## Scope

This is the first FVSC evaluation on a bounded corpus of live public prose rather
than handcrafted containment sentences or the owner's vault.

The corpus was fetched through the Stack Exchange API before inspecting model
results:

- site: `workplace`;
- creation range: 2025-01-01 through 2025-12-31;
- first three chronological question pages;
- questions with score at least 1 and their answers;
- 1,068 attributed records in 194 discussion threads;
- all records are marked CC BY-SA 4.0;
- corpus SHA-256: `fb914a374bbf5c44688325d6588d175b995592b73bf2b7b2cea724b7ac074ecb`.

The raw JSONL corpus is not committed. The exact attributed snapshot and complete
report were uploaded by GitHub Actions run `29186278184` as artifact `8258133344`.

## Leakage control

All questions and answers from one thread were joined into one chronological
document before splitting. A question cannot enter training while an answer from
the same discussion enters test.

- train threads: 155;
- test threads: 39;
- evaluated test threads: 39;
- known-positive coverage: 0.8855;
- pairwise comparisons per model: 5,392,800.

## Result

| Model | ROC AUC | Average precision |
|---|---:|---:|
| Direct parser graph | **0.5935** | **0.8281** |
| FVSC normalized shape | 0.5607 | 0.7934 |
| Deterministic random | 0.4936 | 0.7749 |
| Trace mass | 0.3484 | 0.7201 |

Best baseline: `direct_graph`.

FVSC AUC difference from the best baseline:

```text
-0.032830
```

Paired bootstrap 95% interval:

```text
[-0.033206, -0.032441]
```

Verdict:

```text
no_demonstrated_added_value
```

## Interpretation

The current normalized density-matrix shape contains a modest predictive signal on
this parser-labelled natural-language task: its AUC is above deterministic random.
However, it is reliably worse than simply retaining direct parser-edge frequency.
The confidence interval is narrow and entirely negative, so this is not sampling
noise under the current evaluation construction.

This is consistent with the earlier controlled benchmark: the current pipeline is a
working deterministic representation, but there is still no evidence that its
spectral geometry adds information beyond simpler structures. On this corpus the
strongest simple structure is the direct graph, not trace mass.

The result does **not** establish that density matrices are unsuitable for FVSC. It
shows that the current hash-based materializer and shape metric have not yet earned
their complexity on held-out public prose.

## Methodological warnings

1. Test labels are relations produced by the same parser family used to construct
   training evidence. They are proxy labels, not independent semantic truth.
2. Average precision is high even for random because positive examples outnumber
   sampled negatives; ROC AUC and paired outcomes are more interpretable here.
3. Quotes occurred in 146 of 194 threads. Quote markers are preserved, but the
   current parser does not yet model reported speech or attribution.
4. The benchmark measures public-prose robustness, not personal usefulness.
5. No TF-IDF, PPMI or general embedding baseline has yet been added.

## Required next experiment

Before changing the density representation:

1. sample at least 100 extracted directed relations from the frozen corpus;
2. blind the reviewer to all model scores;
3. label each relation as supported, reversed, unrelated or ambiguous;
4. separately tag quotation, reported speech, negation, question and sarcasm;
5. calculate parser precision and direction precision;
6. add TF-IDF, PPMI and a frozen embedding baseline;
7. repeat on `interpersonal` and `worldbuilding` or `writers` as separate corpora.

Only after the parser audit should a poor score be attributed to the semantic state
rather than to noisy proxy labels.
