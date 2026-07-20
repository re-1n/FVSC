# Semantic capacity probe v1

Date: 2026-07-21
Status: synthetic schema sanity check; not eligible for representation promotion

## Question

When both arms receive manually normalized meaning rather than raw text, which frozen
target facts can the guaranteed flat `Judgment` core and a source-grounded UMR subset
retain?

This isolates representation capacity from parser quality. It does **not** measure
automatic extraction, interpretation accuracy on natural data, or downstream utility.

## Frozen cases

The public fixture `data/fixtures/semantic_capacity_probe_v1.json` contains 4 synthetic
cases and 15 target facts:

| Case | Language | Target operation |
|---|---|---|
| `simple-predicate-ru` | Russian | predicate and arguments |
| `explicit-negation-de` | German | predicate, arguments, explicit negation |
| `modal-conceiver-fr` | French | modality source/conceiver |
| `cross-sentence-links-en` | English | coreference and temporal order across sentences |

The language variety checks that contracts and exact source alignment are not tied to a
Russian tokenizer. It is far too small to establish broad cross-lingual performance.

## Arms

- `judgment_core`: subject, verb, object and explicit polarity guaranteed by the current
  flat projection. Optional free-form/context fields are not credited as structural
  document relations.
- `umr`: sentence edges, node attributes and document edges imported by the loss-aware
  UMR subset adapter.

Both arms are projected to node-id-independent `SemanticFact` values and scored against
the same frozen fact set.

## Result

| Arm | Micro precision | Micro recall | Micro F1 | Macro F1 | Missing facts |
|---|---:|---:|---:|---:|---:|
| `judgment_core` | 0.9091 | 0.6667 | 0.7692 | 0.7818 | 5 |
| `umr` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |

Both arms retained all simple predicate and explicit-negation facts. The flat core missed
two modal/conceiver relations and three document-level coreference/temporal relations.
Its single false positive is the forced `unspecified` object in the intransitive modal
case.

UMR's perfect score is expected in this sanity check: the target set deliberately includes
features expressible by the imported UMR annotation, and no parser must infer them. It
validates the importer and demonstrates a concrete structural gap; it is not evidence of
perfect semantic understanding or superiority on real text.

## Reproduction

```powershell
$env:PYTHONPATH='src'
python scripts/semantic_schema_probe.py
python -m pytest tests/unit/evaluation/test_semantic_probe.py -q
```

The runner prints deterministic JSON and does not write into `EvidenceLedger`.

## Gate and next experiment

`promotion_eligible` remains `false`. The next useful tranche is a blinded, source-cited
set of real owner-reviewed cases. It must compare automatic or manually controlled
extraction separately from representation capacity and score registered semantic queries,
false attribution, abstention and cost. A density arm should be introduced only after an
ambiguity-labelled subset exists; adding it to these unambiguous cases would not test its
claimed advantage.
