# Frozen-plan slot synthesis ablation

Status: controlled public ablation completed; automatic planning not evaluated.

## Question

Did the failed end-to-end requirement gate fail because the model cannot preserve
multi-part answers, or because it had to invent requirements, claims and indexed
linkage in one output?

## Controlled operation

The same twelve held-out questions receive externally frozen question-only plans.
Plans contain one or two neutral requirement descriptions and no answers, source
labels or support decisions. The model fills exactly one `supported/unsupported` slot
per requirement. Supported slots contain one cited claim; unsupported slots contain no
proposition. User-facing prose is rendered deterministically.

This is a capacity ablation. It does not test how plans are produced in a live system.

## Result

| Metric | Planned slots |
|---|---:|
| Macro required-facet recall | 1.000 |
| Abstention accuracy | 1.000 |
| Citation correctness | 1.000 |
| Unsupported-facet rate | 0.000 |
| Prohibited violations | 0 |
| Prompt tokens | 3,028 |
| Output tokens | 804 |
| Mean wall seconds | 10.58 |

All sixteen positive slots were filled and all four missing-link cases were classified
unsupported.

Under the literal requested schema, the four unsupported outputs used a proposition-
free sentinel object (`text=null`, no citations, `evidence_bound`) instead of JSON
`null`, producing four strict schema errors. A deterministic adapter accepts only that
exact empty sentinel for an already-unsupported slot. It cannot accept text, citations,
extra fields or a supported slot. After this safe transport normalization, schema
errors are zero. Both strict and tolerant counts are retained.

## Conclusion

Frozen planning separates the bottleneck: the model can fill and verbalize a correct
multi-requirement plan on this set. The failed end-to-end candidate overloaded one
generation with question decomposition, semantic support, claims and indexed linkage.

No operation is promoted. The next public experiment evaluates question planning
alone against frozen question-only plans. Only after planner quality passes may a
two-stage planner-plus-slot pipeline receive a new held-out end-to-end gate.
