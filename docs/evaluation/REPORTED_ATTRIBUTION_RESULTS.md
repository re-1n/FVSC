# Public reported-attribution diagnostic v1: results

Executed 2026-10-11 against protocol/fixture commit `04fbfae`.
The [protocol](REPORTED_ATTRIBUTION_AUDIT.md), inputs and runner were committed
before execution. The unchanged registered S6 guard was evaluated on 48 public,
synthetic English cases. No model generation or private corpus was used.

## Observed outcome

**Expanded direct-owner eligibility capability failed: 24/48 correct, 24 false
positives, 0 false negatives.** The runner exited with code 1 as specified.

| Attribution family | Correct | False positives | False negatives |
|---|---:|---:|---:|
| Owner's direct statement | 6/6 | 0 | 0 |
| Annotated external quotation | 6/6 | 0 | 0 |
| Endorsed external quotation | 6/6 | 0 | 0 |
| Owner restates content outside quotation | 6/6 | 0 | 0 |
| Indirect report | 0/6 | 6 | 0 |
| Quotation without expression annotation | 0/6 | 6 | 0 |
| Unknown author | 0/6 | 6 | 0 |
| Non-owner author | 0/6 | 6 | 0 |

The [machine-readable artifact](reported_attribution_v1_results.json) includes every
source text, attribution envelope, expected and actual eligibility, full source
commit, Python version and LF-normalized SHA-256 fingerprints.

## Interpretation and limits

Verified external expression spans successfully block relation cues. An explicit
owner restatement outside the span remains eligible. The endorsement cases only
check exclusion from **direct authorship**; they do not measure whether agreement
can be recovered as a separate supported claim.

The failing cases expose the narrower implementation boundary: S6 checks relation
cues and supplied expression spans, but does not enforce transport-author/origin
metadata or extract reported speech. For example, `Mira said that the cedar
workshop is confirmed.` remains eligible for the direct-owner question despite
the attribution in the text. The same proposition also remains eligible when the
metadata says `non_owner` or `unknown`.

These are unsafe candidate links under the frozen question scope, not observed
hallucinated answers. The diagnostic does not execute an entire retrieval/planning
pipeline and cannot establish whether an upstream filter would prevent a link.
Metadata is supplied as synthetic oracle input; attribution extraction accuracy
was not tested. Six repeated relation templates are not 48 independent natural
language phenomena, and 50% here is not an estimate of production accuracy.

The existing narrow contract is unchanged: the prior relation-support, polarity
and annotated-attribution unit tests still pass (**19 passed**). This diagnostic
does not revoke those results or extend their scope.

## Next implementation boundary

1. Introduce an explicit owner-attribution eligibility step for direct-owner
   questions, with unresolved authorship producing abstention and a recorded reason.
2. Represent reported content with its speaker and source span; keep reporting,
   endorsement and direct assertion distinct. A non-owner source can still support
   a question about that speaker, so a global source rejection is inappropriate.
3. Freeze new cases before measuring an intervention. Include nested reports,
   mixed owner/external text, endorsement without restatement, ambiguous metadata
   and Russian language examples. Keep this public set as a regression diagnostic,
   not unseen evidence of generalization.

No production guard or gold label was changed in response to these results.
