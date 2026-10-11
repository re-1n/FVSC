"""Conservative views over explicit attribution; no speaker or stance extraction."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

from .source_provenance import ExpressionSpan, OwnerEndorsement, SourceAttribution


@dataclass(frozen=True)
class OwnerEligibility:
    reason: str
    regions: tuple[tuple[int, int], ...] = ()

    @property
    def eligible(self) -> bool:
        return bool(self.regions)


def _authored(span: ExpressionSpan) -> bool:
    return (
        span.kind == "owner_commentary"
        and span.origin_status == "owner"
        and span.owner_relation == "authored"
    )


def direct_owner_eligibility(
    text: str, attribution: SourceAttribution | None,
) -> OwnerEligibility:
    """Return authorized text regions, never treating adoption as authorship.

    Semantic attribution is trusted input; hashes verify text binding, not truth.
    Even an owner-authored span cannot override a contradictory transport envelope.
    """
    if attribution is None:
        return OwnerEligibility("missing_attribution")
    attribution.verify(text)
    if attribution.transport_author_role != "owner":
        return OwnerEligibility("author_not_owner_or_unknown")
    if attribution.forwarded:
        return OwnerEligibility("forwarded_source")
    if attribution.text_origin_status == "external":
        return OwnerEligibility("external_origin")
    spans = attribution.expression_spans
    if attribution.text_origin_status != "owner":
        regions = tuple((s.start, s.end) for s in spans if _authored(s))
        return OwnerEligibility(
            "verified_owner_spans" if regions else "owner_spans_required", regions,
        )
    # Owner-origin text may contain explicit exceptions. Unresolved or conflicting
    # annotations override the broad origin flag and remain excluded.
    regions = []
    cursor = 0
    for span in spans:
        if not _authored(span):
            if cursor < span.start:
                regions.append((cursor, span.start))
            cursor = span.end
    if cursor < len(text):
        regions.append((cursor, len(text)))
    meaningful = tuple((start, end) for start, end in regions if text[start:end].strip())
    return OwnerEligibility(
        "owner_origin_regions" if meaningful else "no_owner_text", meaningful,
    )


@dataclass(frozen=True)
class ReportedExpression:
    """A transient, source-bound annotated expression, not a direct owner claim.

    No source text is copied. Speaker resolution and stance-cue extraction are
    deliberately absent. Endorsement is inherited from the explicit annotation.
    """
    source_label: str
    source_text_sha256: str
    expression: ExpressionSpan
    owner_endorsement: OwnerEndorsement
    speaker: None = None

    def verify(self, *, source_label: str, text: str) -> None:
        if source_label != self.source_label:
            raise ValueError("reported expression source label mismatch")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != self.source_text_sha256:
            raise ValueError("reported expression source revision mismatch")
        self.expression.verify(text)


def reported_expressions(
    source_label: str, text: str, attribution: SourceAttribution | None,
) -> tuple[ReportedExpression, ...]:
    """Preserve external annotations separately; never infer endorsement from adoption."""
    if not source_label.strip():
        raise ValueError("source label must not be empty")
    if attribution is None:
        return ()
    attribution.verify(text)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return tuple(
        ReportedExpression(source_label, digest, span, span.owner_endorsement)
        for span in attribution.expression_spans
        if span.kind != "owner_commentary" and span.origin_status == "external"
    )
