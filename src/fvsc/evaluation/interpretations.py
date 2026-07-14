"""Structural evaluation for source-cited interpretation proposals.

The evaluator checks provenance coverage and owner-declared negative links.  A
character n-gram similarity is exposed only as a surface diagnostic; it is not
treated as a semantic truth score and cannot promote a proposal into evidence.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re
from typing import Iterable

from ..interpretation import InterpretationProposal
from .gold import GoldCase


_SPACE_RE = re.compile(r"\s+")


def _surface_ngrams(text: str) -> Counter[str]:
    normalized = _SPACE_RE.sub(" ", text.casefold()).strip()
    if not normalized:
        return Counter()
    compact = f" {normalized} "
    features: Counter[str] = Counter()
    for width in (3, 4, 5):
        if len(compact) < width:
            continue
        features.update(compact[index : index + width] for index in range(len(compact) - width + 1))
    return features


def surface_similarity(left: str, right: str) -> float:
    """Return deterministic character n-gram cosine similarity in ``[0, 1]``."""
    left_features = _surface_ngrams(left)
    right_features = _surface_ngrams(right)
    if not left_features or not right_features:
        return 0.0
    shared = left_features.keys() & right_features.keys()
    dot = math.fsum(left_features[key] * right_features[key] for key in shared)
    left_norm = math.sqrt(math.fsum(value * value for value in left_features.values()))
    right_norm = math.sqrt(math.fsum(value * value for value in right_features.values()))
    return dot / (left_norm * right_norm)


def _recall(expected: set[str], actual: set[str]) -> float | None:
    return None if not expected else len(expected & actual) / len(expected)


def _mean(values: Iterable[float | None]) -> float | None:
    present = tuple(value for value in values if value is not None)
    return None if not present else math.fsum(present) / len(present)


@dataclass(frozen=True)
class ProposalEvaluation:
    case_id: str
    proposal_id: str
    primary_citation_recall: float | None
    relevant_citation_recall: float | None
    context_citation_recall: float | None
    citation_precision: float | None
    negative_citation_count: int
    forbidden_link_violations: int
    unsupported_claim_count: int
    partially_supported_claim_count: int
    surface_similarity_to_owner: float | None
    max_surface_similarity_to_rejected: float | None
    structurally_safe: bool


def evaluate_interpretation_proposal(
    case: GoldCase,
    proposal: InterpretationProposal,
) -> ProposalEvaluation:
    """Compare one proposal with open-meaning gold mechanics.

    ``separate`` is enforced at claim granularity: citing two separated source
    refs in different claims is allowed, while using both to support one claim
    is counted as a forbidden composite.
    """
    if proposal.question != case.question:
        raise ValueError("proposal question does not match the gold case")

    citations_by_id = {item.citation_id: item for item in proposal.citations}
    cited_source_ids = set(proposal.cited_source_ids)
    primary = set(case.primary_source_ids)
    relevant = set(case.relevant_source_ids)
    context = set(case.context_source_ids)
    negatives = set(case.negative_source_ids)
    allowed = relevant | context
    citation_precision = (
        None
        if not cited_source_ids
        else len(cited_source_ids & allowed) / len(cited_source_ids)
    )

    source_by_ref = {
        item.ref: item.source_id for item in case.evidence if item.source_id is not None
    }
    forbidden_source_pairs: set[tuple[str, str]] = set()
    for link in case.links:
        if link.decision != "separate":
            continue
        left = source_by_ref.get(link.left_ref)
        right = source_by_ref.get(link.right_ref)
        if left is not None and right is not None and left != right:
            forbidden_source_pairs.add(tuple(sorted((left, right))))

    violations: set[tuple[str, str, str]] = set()
    unsupported_claim_count = 0
    partially_supported_claim_count = 0
    for claim in proposal.claims:
        if claim.support_level == "free_generation" or not claim.citation_ids:
            unsupported_claim_count += 1
        elif claim.support_level == "partially_supported":
            partially_supported_claim_count += 1
        claim_sources = {
            citations_by_id[citation_id].source_id for citation_id in claim.citation_ids
        }
        for left, right in forbidden_source_pairs:
            if left in claim_sources and right in claim_sources:
                violations.add((claim.claim_id, left, right))

    owner_similarity = (
        surface_similarity(proposal.answer, case.owner_interpretation)
        if case.owner_interpretation
        else None
    )
    rejected_similarities = tuple(
        surface_similarity(proposal.answer, rejected)
        for rejected in case.rejected_interpretations
    )
    negative_count = len(cited_source_ids & negatives)
    violation_count = len(violations)
    structurally_safe = (
        negative_count == 0
        and violation_count == 0
        and unsupported_claim_count == 0
    )
    return ProposalEvaluation(
        case_id=case.case_id,
        proposal_id=proposal.proposal_id,
        primary_citation_recall=_recall(primary or relevant, cited_source_ids),
        relevant_citation_recall=_recall(relevant, cited_source_ids),
        context_citation_recall=_recall(context, cited_source_ids),
        citation_precision=citation_precision,
        negative_citation_count=negative_count,
        forbidden_link_violations=violation_count,
        unsupported_claim_count=unsupported_claim_count,
        partially_supported_claim_count=partially_supported_claim_count,
        surface_similarity_to_owner=owner_similarity,
        max_surface_similarity_to_rejected=(
            max(rejected_similarities) if rejected_similarities else None
        ),
        structurally_safe=structurally_safe,
    )


@dataclass(frozen=True)
class InterpretationEvaluation:
    cases: tuple[ProposalEvaluation, ...]
    mean_primary_citation_recall: float | None
    mean_relevant_citation_recall: float | None
    mean_context_citation_recall: float | None
    mean_citation_precision: float | None
    negative_citation_count: int
    forbidden_link_violations: int
    unsupported_claim_count: int
    structurally_safe_cases: int


def summarize_interpretation_evaluations(
    cases: Iterable[ProposalEvaluation],
) -> InterpretationEvaluation:
    results = tuple(cases)
    case_ids = tuple(item.case_id for item in results)
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("interpretation evaluations contain duplicate case ids")
    return InterpretationEvaluation(
        cases=results,
        mean_primary_citation_recall=_mean(
            item.primary_citation_recall for item in results
        ),
        mean_relevant_citation_recall=_mean(
            item.relevant_citation_recall for item in results
        ),
        mean_context_citation_recall=_mean(
            item.context_citation_recall for item in results
        ),
        mean_citation_precision=_mean(item.citation_precision for item in results),
        negative_citation_count=sum(item.negative_citation_count for item in results),
        forbidden_link_violations=sum(
            item.forbidden_link_violations for item in results
        ),
        unsupported_claim_count=sum(item.unsupported_claim_count for item in results),
        structurally_safe_cases=sum(item.structurally_safe for item in results),
    )


__all__ = [
    "InterpretationEvaluation",
    "ProposalEvaluation",
    "evaluate_interpretation_proposal",
    "summarize_interpretation_evaluations",
    "surface_similarity",
]
