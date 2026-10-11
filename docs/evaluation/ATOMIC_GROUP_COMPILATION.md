# Atomic reviewed-group compilation

## Status

Implementation feasibility. This protocol does not revise frozen Gold and does not
promote a representation.

## Problem

A reviewed semantic group may contain several alternatives, adoption decisions and
scope corrections. Treating the whole group as one retrieval atom preserves safety but
can make the mandatory seed/guard/correction bundle larger than the per-query budget.
Increasing every query budget hides the structural problem and increases irrelevant
context.

## Contract

- The original reviewed group remains present as an immutable provenance parent.
- A parent may be marked `selectable=false`; it remains addressable but does not enter
  retrieval ranking.
- Every derived child declares `parent_group_id`.
- A child contains one bounded distinction, adoption decision or relation already
  stated by the parent. It may not add a new interpretation.
- Guards and corrections link to the smallest children that preserve the reviewed
  boundary.
- Selecting a child does not imply selecting, accepting or rendering every sibling.
- Parent identity is rendered with the child so a reviewer can trace the derivation.

## Synthetic gate

The compiler must:

1. retain and validate the parent;
2. reject missing or non-group parents;
3. omit a non-selectable parent from ranking;
4. compile a child without rendering the oversized parent;
5. retain mandatory guards and corrections;
6. stay inside the unchanged token budget.

## Private owner-reviewed result

In the frozen dialogue census, the safe monolithic bundle for the metaphor-reception
question required 671 estimated tokens:

`M005A + N008 + G001`

A private derived view split `G001` into five children covering mechanism A,
composition B, the relation between the frames, adoption of A and reception of B.
The owner accepted all five child formulations and confirmed that they jointly preserve
the essential content of `G001`. The review was frozen separately from the parent
census as `private-owner-reviewed-derived-view-v1`; it does not mutate the parent Gold
or broaden publication permission.
With `G001` retained as a non-selectable parent, the compiler selected:

`G001.A_ADOPTION + G001.B_RECEPTION + N008`

The resulting block required 451 estimated tokens and fit the original 500-token
budget. It preserved the crucial distinction: the participant confirmed the radical
mechanistic level but did not adopt the supportive paint metaphor.

The post-review deterministic generation diagnostic compared raw + stable locators with
the atomic FVSC view at the original 500-token budget. Raw produced 7 accepted and
3 partial answers; atomic FVSC produced 9 accepted and 1 partial answer, with zero
rejections or adoption reversals. Atomic FVSC used 4,656 prompt tokens versus 5,116
for raw (9% fewer). This remains one private dialogue and one model/seed, so it is not a
general promotion result.

This is also a structural feasibility result, not a preregistered recall gain. The existing oracle
was defined over the monolithic parent and earlier M-units; no child-to-oracle
equivalence map was preregistered. That map must not be invented after seeing the
result. A later revision may score atomic children only after an independent derivation
review freezes which parent claims each child preserves.

The diagnostic also exposed and corrected duplicate rendering when a primary unit was
simultaneously a mandatory guard correction. The first artifact is retained as
diagnostic history; the post-fix run is the reported result.

## Related-facet follow-up

The remaining partial answer concerned a response protocol whose interaction rule and
possible tactile facet are stored in separate reviewed units. A bounded two-hop typed
traversal raised retrieval coverage and delivered both units within 492 estimated
tokens. The generation model still omitted tactility from its answer. Therefore this
failure is now classified as downstream synthesis/coverage, not retrieval. It must not
be counted as an atomic-storage or ranker gain.

## Next evaluation

Before owner review is requested, test the same contract on public synthetic groups
covering:

- mutually exclusive interpretations;
- compatible levels of description;
- speaker adoption of one alternative but not another;
- correction guards spanning multiple children;
- nested provenance without implicit sibling adoption.
