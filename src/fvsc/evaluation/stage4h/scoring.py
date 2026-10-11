"""Owner-scored Stage 4h attribution metrics and conservative diagnosis."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import random
import statistics
from typing import Any, Iterable, Mapping, Sequence

from ..gold import GoldCase, GoldSet, RankedSources, evaluate_rankings
from ..interpretations import evaluate_interpretation_proposal
from .candidates import FrozenCandidateBundle
from .contracts import Stage4hArm, Stage4hOwnerReview, Stage4hRunSpec, content_digest
from .review_pack import Stage4hBlindMap
from .runner import Stage4hArmResult, Stage4hRunResultBundle


def _mean(values: Sequence[float]) -> float | None:
    return None if not values else math.fsum(values) / len(values)


def _median(values: Sequence[float]) -> float | None:
    return None if not values else float(statistics.median(values))


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _paired_bootstrap_interval(
    values: Sequence[float],
    *,
    samples: int = 5_000,
    seed: int = 42,
) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    rng = random.Random(seed)
    means = sorted(
        math.fsum(values[rng.randrange(len(values))] for _ in values) / len(values)
        for _ in range(samples)
    )
    lower = means[int(0.025 * (samples - 1))]
    upper = means[int(0.975 * (samples - 1))]
    return lower, upper


@dataclass(frozen=True)
class Stage4hRetrievalSummary:
    mrr_at_k: float | None
    recall_at_k: float | None
    context_recall_at_k: float | None
    negative_hits_at_k: int
    abstention_accuracy: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "abstention_accuracy": self.abstention_accuracy,
            "context_recall_at_k": self.context_recall_at_k,
            "mrr_at_k": self.mrr_at_k,
            "negative_hits_at_k": self.negative_hits_at_k,
            "recall_at_k": self.recall_at_k,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hRetrievalSummary":
        return cls(
            mrr_at_k=value.get("mrr_at_k"),
            recall_at_k=value.get("recall_at_k"),
            context_recall_at_k=value.get("context_recall_at_k"),
            negative_hits_at_k=value.get("negative_hits_at_k", 0),
            abstention_accuracy=value.get("abstention_accuracy"),
        )


@dataclass(frozen=True)
class Stage4hArmSummary:
    arm: Stage4hArm
    total_cases: int
    generated_cases: int
    reviewed_cases: int
    claim_count: int
    accepted_or_partial_rate: float | None
    meaning_fidelity_mean: float | None
    meaning_fidelity_median: float | None
    usefulness_mean: float | None
    usefulness_median: float | None
    citation_precision: float | None
    citation_partial_rate: float | None
    relevant_citation_recall: float | None
    context_citation_recall: float | None
    negative_citation_count: int
    forbidden_link_violations: int
    unsupported_claim_count: int
    false_owner_attribution_count: int
    unsupported_referent_count: int
    owner_forbidden_composite_count: int
    missed_context_count: int
    abstention_preferable_count: int
    severe_error_count: int
    mean_wall_seconds: float | None
    prompt_tokens: int | None
    output_tokens: int | None
    retrieval: Stage4hRetrievalSummary

    @property
    def coverage_rate(self) -> float:
        return 0.0 if self.total_cases == 0 else self.generated_cases / self.total_cases

    def to_dict(self) -> dict[str, Any]:
        return {
            "abstention_preferable_count": self.abstention_preferable_count,
            "accepted_or_partial_rate": self.accepted_or_partial_rate,
            "arm": self.arm,
            "citation_partial_rate": self.citation_partial_rate,
            "citation_precision": self.citation_precision,
            "claim_count": self.claim_count,
            "context_citation_recall": self.context_citation_recall,
            "coverage_rate": self.coverage_rate,
            "false_owner_attribution_count": self.false_owner_attribution_count,
            "forbidden_link_violations": self.forbidden_link_violations,
            "generated_cases": self.generated_cases,
            "meaning_fidelity_mean": self.meaning_fidelity_mean,
            "meaning_fidelity_median": self.meaning_fidelity_median,
            "mean_wall_seconds": self.mean_wall_seconds,
            "missed_context_count": self.missed_context_count,
            "negative_citation_count": self.negative_citation_count,
            "output_tokens": self.output_tokens,
            "owner_forbidden_composite_count": self.owner_forbidden_composite_count,
            "prompt_tokens": self.prompt_tokens,
            "relevant_citation_recall": self.relevant_citation_recall,
            "retrieval": self.retrieval.to_dict(),
            "reviewed_cases": self.reviewed_cases,
            "severe_error_count": self.severe_error_count,
            "total_cases": self.total_cases,
            "unsupported_claim_count": self.unsupported_claim_count,
            "unsupported_referent_count": self.unsupported_referent_count,
            "usefulness_mean": self.usefulness_mean,
            "usefulness_median": self.usefulness_median,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hArmSummary":
        raw_retrieval = value.get("retrieval", {})
        if not isinstance(raw_retrieval, Mapping):
            raise ValueError("Stage 4h retrieval summary must be an object")
        return cls(
            arm=value.get("arm", ""),
            total_cases=value.get("total_cases", 0),
            generated_cases=value.get("generated_cases", 0),
            reviewed_cases=value.get("reviewed_cases", 0),
            claim_count=value.get("claim_count", 0),
            accepted_or_partial_rate=value.get("accepted_or_partial_rate"),
            meaning_fidelity_mean=value.get("meaning_fidelity_mean"),
            meaning_fidelity_median=value.get("meaning_fidelity_median"),
            usefulness_mean=value.get("usefulness_mean"),
            usefulness_median=value.get("usefulness_median"),
            citation_precision=value.get("citation_precision"),
            citation_partial_rate=value.get("citation_partial_rate"),
            relevant_citation_recall=value.get("relevant_citation_recall"),
            context_citation_recall=value.get("context_citation_recall"),
            negative_citation_count=value.get("negative_citation_count", 0),
            forbidden_link_violations=value.get("forbidden_link_violations", 0),
            unsupported_claim_count=value.get("unsupported_claim_count", 0),
            false_owner_attribution_count=value.get(
                "false_owner_attribution_count", 0
            ),
            unsupported_referent_count=value.get("unsupported_referent_count", 0),
            owner_forbidden_composite_count=value.get(
                "owner_forbidden_composite_count", 0
            ),
            missed_context_count=value.get("missed_context_count", 0),
            abstention_preferable_count=value.get("abstention_preferable_count", 0),
            severe_error_count=value.get("severe_error_count", 0),
            mean_wall_seconds=value.get("mean_wall_seconds"),
            prompt_tokens=value.get("prompt_tokens"),
            output_tokens=value.get("output_tokens"),
            retrieval=Stage4hRetrievalSummary.from_dict(raw_retrieval),
        )


@dataclass(frozen=True)
class Stage4hPairedSummary:
    left_arm: Stage4hArm
    right_arm: Stage4hArm
    paired_cases: int
    meaning_fidelity_mean_delta: float | None
    meaning_fidelity_ci95_lower: float | None
    meaning_fidelity_ci95_upper: float | None
    usefulness_mean_delta: float | None
    citation_precision_mean_delta: float | None
    latency_multiplier: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation_precision_mean_delta": self.citation_precision_mean_delta,
            "latency_multiplier": self.latency_multiplier,
            "left_arm": self.left_arm,
            "meaning_fidelity_ci95_lower": self.meaning_fidelity_ci95_lower,
            "meaning_fidelity_ci95_upper": self.meaning_fidelity_ci95_upper,
            "meaning_fidelity_mean_delta": self.meaning_fidelity_mean_delta,
            "paired_cases": self.paired_cases,
            "right_arm": self.right_arm,
            "usefulness_mean_delta": self.usefulness_mean_delta,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hPairedSummary":
        return cls(
            left_arm=value.get("left_arm", ""),
            right_arm=value.get("right_arm", ""),
            paired_cases=value.get("paired_cases", 0),
            meaning_fidelity_mean_delta=value.get("meaning_fidelity_mean_delta"),
            meaning_fidelity_ci95_lower=value.get("meaning_fidelity_ci95_lower"),
            meaning_fidelity_ci95_upper=value.get("meaning_fidelity_ci95_upper"),
            usefulness_mean_delta=value.get("usefulness_mean_delta"),
            citation_precision_mean_delta=value.get("citation_precision_mean_delta"),
            latency_multiplier=value.get("latency_multiplier"),
        )


@dataclass(frozen=True)
class Stage4hAttributionReport:
    report_id: str
    run_id: str
    result_bundle_id: str
    blind_map_id: str
    evaluation_mode: str
    arm_summaries: tuple[Stage4hArmSummary, ...]
    paired_summaries: tuple[Stage4hPairedSummary, ...]
    diagnosis: str
    promoted_arm: Stage4hArm | None
    limitations: tuple[str, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported Stage 4h report version")
        arms = tuple(item.arm for item in self.arm_summaries)
        if arms != tuple(sorted(arms)) or len(arms) != len(set(arms)):
            raise ValueError("Stage 4h arm summaries must be unique and sorted")
        pairs = tuple((item.left_arm, item.right_arm) for item in self.paired_summaries)
        if pairs != tuple(sorted(pairs)) or len(pairs) != len(set(pairs)):
            raise ValueError("Stage 4h paired summaries must be unique and sorted")
        if self.evaluation_mode == "pilot" and self.promoted_arm is not None:
            raise ValueError("pilot reports cannot promote an arm")
        if self.promoted_arm not in {None, "A4"}:
            raise ValueError("Stage 4h may promote only the tested structural arm")
        if self.report_id != content_digest(self._payload()):
            raise ValueError("report_id does not match the Stage 4h report")

    def _payload(self) -> dict[str, Any]:
        return {
            "arm_summaries": [item.to_dict() for item in self.arm_summaries],
            "blind_map_id": self.blind_map_id,
            "diagnosis": self.diagnosis,
            "evaluation_mode": self.evaluation_mode,
            "limitations": list(self.limitations),
            "paired_summaries": [item.to_dict() for item in self.paired_summaries],
            "promoted_arm": self.promoted_arm,
            "result_bundle_id": self.result_bundle_id,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
        }

    @classmethod
    def create(
        cls,
        *,
        spec: Stage4hRunSpec,
        result_bundle_id: str,
        blind_map_id: str,
        arm_summaries: Iterable[Stage4hArmSummary],
        paired_summaries: Iterable[Stage4hPairedSummary],
        diagnosis: str,
        promoted_arm: Stage4hArm | None,
        limitations: tuple[str, ...],
    ) -> "Stage4hAttributionReport":
        arms = tuple(sorted(arm_summaries, key=lambda item: item.arm))
        pairs = tuple(
            sorted(paired_summaries, key=lambda item: (item.left_arm, item.right_arm))
        )
        payload = {
            "arm_summaries": [item.to_dict() for item in arms],
            "blind_map_id": blind_map_id,
            "diagnosis": diagnosis,
            "evaluation_mode": spec.evaluation_mode,
            "limitations": list(limitations),
            "paired_summaries": [item.to_dict() for item in pairs],
            "promoted_arm": promoted_arm,
            "result_bundle_id": result_bundle_id,
            "run_id": spec.run_id,
            "schema_version": 1,
        }
        return cls(
            report_id=content_digest(payload),
            run_id=spec.run_id,
            result_bundle_id=result_bundle_id,
            blind_map_id=blind_map_id,
            evaluation_mode=spec.evaluation_mode,
            arm_summaries=arms,
            paired_summaries=pairs,
            diagnosis=diagnosis,
            promoted_arm=promoted_arm,
            limitations=limitations,
        )

    def to_dict(self) -> dict[str, Any]:
        return {"report_id": self.report_id, **self._payload()}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hAttributionReport":
        raw_arms = value.get("arm_summaries", [])
        raw_pairs = value.get("paired_summaries", [])
        raw_limitations = value.get("limitations", [])
        if not all(isinstance(item, list) for item in (raw_arms, raw_pairs, raw_limitations)):
            raise ValueError("Stage 4h report arrays are invalid")
        return cls(
            report_id=value.get("report_id", ""),
            run_id=value.get("run_id", ""),
            result_bundle_id=value.get("result_bundle_id", ""),
            blind_map_id=value.get("blind_map_id", ""),
            evaluation_mode=value.get("evaluation_mode", ""),
            arm_summaries=tuple(Stage4hArmSummary.from_dict(item) for item in raw_arms),
            paired_summaries=tuple(
                Stage4hPairedSummary.from_dict(item) for item in raw_pairs
            ),
            diagnosis=value.get("diagnosis", ""),
            promoted_arm=value.get("promoted_arm"),
            limitations=tuple(str(item) for item in raw_limitations),
            schema_version=value.get("schema_version", 0),
        )


def _validate_reviews(
    *,
    result_bundle: Stage4hRunResultBundle,
    blind_map: Stage4hBlindMap,
    reviews: Iterable[Stage4hOwnerReview],
) -> tuple[
    dict[str, Stage4hOwnerReview],
    dict[str, Stage4hArmResult],
]:
    review_values = tuple(reviews)
    by_blind = {item.blind_item_id: item for item in review_values}
    if len(by_blind) != len(review_values):
        raise ValueError("Stage 4h reviews contain duplicate blind item ids")
    entries = {item.blind_item_id: item for item in blind_map.entries}
    if set(by_blind) != set(entries):
        raise ValueError("Stage 4h reviews must cover every generated blind item exactly")
    results = {item.result_id: item for item in result_bundle.results}
    review_by_result: dict[str, Stage4hOwnerReview] = {}
    result_by_id: dict[str, Stage4hArmResult] = {}
    for blind_id, review in by_blind.items():
        entry = entries[blind_id]
        result = results.get(entry.result_id)
        if result is None or result.proposal is None:
            raise ValueError("blind map references a missing generated result")
        proposal = result.proposal
        if review.proposal_id != entry.proposal_id or proposal.proposal_id != entry.proposal_id:
            raise ValueError("owner review proposal id does not match the blind map")
        claim_reviews = {item.claim_id: item for item in review.claim_reviews}
        proposal_claims = {item.claim_id: item for item in proposal.claims}
        if set(claim_reviews) != set(proposal_claims):
            raise ValueError("owner review must score every proposal claim exactly")
        for claim_id, claim_review in claim_reviews.items():
            expected_citations = set(proposal_claims[claim_id].citation_ids)
            actual_citations = {item.citation_id for item in claim_review.citations}
            if actual_citations != expected_citations:
                raise ValueError("owner review must score every claim citation exactly")
        review_by_result[result.result_id] = review
        result_by_id[result.result_id] = result
    return review_by_result, result_by_id


def _retrieval_summary(
    *,
    arm: Stage4hArm,
    spec: Stage4hRunSpec,
    cases: tuple[GoldCase, ...],
    candidates: FrozenCandidateBundle,
) -> Stage4hRetrievalSummary:
    rankings = []
    for case in cases:
        candidate_set = candidates.for_case_arm(case.case_id, arm)
        ids = tuple(item.source_id for item in candidate_set.candidates)
        rankings.append(
            RankedSources(
                case_id=case.case_id,
                source_ids=ids,
                abstained=not ids,
            )
        )
    evaluated = evaluate_rankings(GoldSet(schema_version=1, cases=cases), rankings, top_k=spec.top_k)
    return Stage4hRetrievalSummary(
        mrr_at_k=evaluated.mean_reciprocal_rank,
        recall_at_k=evaluated.mean_recall_at_k,
        context_recall_at_k=evaluated.mean_context_recall_at_k,
        negative_hits_at_k=evaluated.negative_hits_at_k,
        abstention_accuracy=evaluated.abstention_accuracy,
    )


def _arm_summary(
    *,
    arm: Stage4hArm,
    spec: Stage4hRunSpec,
    cases: tuple[GoldCase, ...],
    candidates: FrozenCandidateBundle,
    results: Stage4hRunResultBundle,
    review_by_result: Mapping[str, Stage4hOwnerReview],
) -> Stage4hArmSummary:
    case_by_id = {item.case_id: item for item in cases}
    arm_results = tuple(item for item in results.results if item.arm == arm)
    generated = tuple(item for item in arm_results if item.status == "generated")
    reviews = tuple(review_by_result[item.result_id] for item in generated)
    claims = tuple(review for item in reviews for review in item.claim_reviews)
    accepted = sum(
        item.verdict in {"accepted", "partially_accepted"} for item in claims
    )
    citation_reviews = tuple(
        citation for claim in claims for citation in claim.citations
    )
    citation_supports = sum(item.verdict == "supports" for item in citation_reviews)
    citation_partials = sum(item.verdict == "partial" for item in citation_reviews)

    proposal_evaluations = tuple(
        evaluate_interpretation_proposal(case_by_id[item.case_id], item.proposal)
        for item in generated
        if item.proposal is not None
    )
    relevant_recalls = [
        item.relevant_citation_recall
        for item in proposal_evaluations
        if item.relevant_citation_recall is not None
    ]
    context_recalls = [
        item.context_citation_recall
        for item in proposal_evaluations
        if item.context_citation_recall is not None
    ]
    false_owner = sum(item.false_owner_attribution for item in reviews)
    referent = sum(item.unsupported_referent_assumption for item in reviews)
    owner_forbidden = sum(item.forbidden_composite for item in reviews)
    negative_citations = sum(item.negative_citation_count for item in proposal_evaluations)
    forbidden_links = sum(item.forbidden_link_violations for item in proposal_evaluations)
    unsupported_claims = sum(item.unsupported_claim_count for item in proposal_evaluations)
    unsupported_citations = sum(
        item.verdict == "unsupported" for item in citation_reviews
    )
    severe = (
        false_owner
        + referent
        + owner_forbidden
        + negative_citations
        + forbidden_links
        + unsupported_claims
        + unsupported_citations
    )
    telemetry = tuple(item.telemetry for item in generated if item.telemetry is not None)
    prompt_counts = [item.prompt_eval_count for item in telemetry if item.prompt_eval_count is not None]
    output_counts = [item.eval_count for item in telemetry if item.eval_count is not None]
    fidelity = [float(item.meaning_fidelity) for item in reviews]
    usefulness = [float(item.usefulness) for item in reviews]
    return Stage4hArmSummary(
        arm=arm,
        total_cases=len(cases),
        generated_cases=len(generated),
        reviewed_cases=len(reviews),
        claim_count=len(claims),
        accepted_or_partial_rate=_rate(accepted, len(claims)),
        meaning_fidelity_mean=_mean(fidelity),
        meaning_fidelity_median=_median(fidelity),
        usefulness_mean=_mean(usefulness),
        usefulness_median=_median(usefulness),
        citation_precision=_rate(citation_supports, len(citation_reviews)),
        citation_partial_rate=_rate(citation_partials, len(citation_reviews)),
        relevant_citation_recall=_mean(relevant_recalls),
        context_citation_recall=_mean(context_recalls),
        negative_citation_count=negative_citations,
        forbidden_link_violations=forbidden_links,
        unsupported_claim_count=unsupported_claims,
        false_owner_attribution_count=false_owner,
        unsupported_referent_count=referent,
        owner_forbidden_composite_count=owner_forbidden,
        missed_context_count=sum(item.missed_context for item in reviews),
        abstention_preferable_count=sum(item.abstention_preferable for item in reviews),
        severe_error_count=severe,
        mean_wall_seconds=_mean([item.wall_seconds for item in telemetry]),
        prompt_tokens=sum(prompt_counts) if prompt_counts else None,
        output_tokens=sum(output_counts) if output_counts else None,
        retrieval=_retrieval_summary(
            arm=arm,
            spec=spec,
            cases=cases,
            candidates=candidates,
        ),
    )


def _case_citation_precision(review: Stage4hOwnerReview) -> float | None:
    citations = tuple(
        citation for claim in review.claim_reviews for citation in claim.citations
    )
    if not citations:
        return None
    return sum(item.verdict == "supports" for item in citations) / len(citations)


def _paired_summary(
    *,
    left_arm: Stage4hArm,
    right_arm: Stage4hArm,
    results: Stage4hRunResultBundle,
    review_by_result: Mapping[str, Stage4hOwnerReview],
) -> Stage4hPairedSummary:
    by_key = {(item.case_id, item.arm): item for item in results.results}
    fidelity_deltas: list[float] = []
    usefulness_deltas: list[float] = []
    citation_deltas: list[float] = []
    left_latencies: list[float] = []
    right_latencies: list[float] = []
    for case_id in sorted({item.case_id for item in results.results}):
        left = by_key.get((case_id, left_arm))
        right = by_key.get((case_id, right_arm))
        if (
            left is None
            or right is None
            or left.status != "generated"
            or right.status != "generated"
        ):
            continue
        left_review = review_by_result[left.result_id]
        right_review = review_by_result[right.result_id]
        fidelity_deltas.append(
            right_review.meaning_fidelity - left_review.meaning_fidelity
        )
        usefulness_deltas.append(right_review.usefulness - left_review.usefulness)
        left_precision = _case_citation_precision(left_review)
        right_precision = _case_citation_precision(right_review)
        if left_precision is not None and right_precision is not None:
            citation_deltas.append(right_precision - left_precision)
        if left.telemetry is not None and right.telemetry is not None:
            left_latencies.append(left.telemetry.wall_seconds)
            right_latencies.append(right.telemetry.wall_seconds)
    lower, upper = _paired_bootstrap_interval(fidelity_deltas)
    left_latency = _mean(left_latencies)
    right_latency = _mean(right_latencies)
    latency_multiplier = (
        None
        if left_latency is None or right_latency is None or left_latency == 0.0
        else right_latency / left_latency
    )
    return Stage4hPairedSummary(
        left_arm=left_arm,
        right_arm=right_arm,
        paired_cases=len(fidelity_deltas),
        meaning_fidelity_mean_delta=_mean(fidelity_deltas),
        meaning_fidelity_ci95_lower=lower,
        meaning_fidelity_ci95_upper=upper,
        usefulness_mean_delta=_mean(usefulness_deltas),
        citation_precision_mean_delta=_mean(citation_deltas),
        latency_multiplier=latency_multiplier,
    )


def _meets_quality_target(summary: Stage4hArmSummary, spec: Stage4hRunSpec) -> bool:
    thresholds = spec.thresholds
    return (
        summary.coverage_rate == 1.0
        and summary.accepted_or_partial_rate is not None
        and summary.accepted_or_partial_rate
        >= thresholds.oracle_min_accepted_or_partial_rate
        and summary.citation_precision is not None
        and summary.citation_precision >= thresholds.min_citation_precision
        and summary.meaning_fidelity_median is not None
        and summary.meaning_fidelity_median
        >= thresholds.min_median_meaning_fidelity
        and summary.severe_error_count <= thresholds.max_severe_errors
    )


def _diagnosis(
    *,
    summaries: Mapping[str, Stage4hArmSummary],
    structural_pair: Stage4hPairedSummary,
    spec: Stage4hRunSpec,
) -> str:
    oracle = summaries["A2"]
    lexical = summaries["A1"]
    structural = summaries["A4"]
    if oracle.severe_error_count > spec.thresholds.max_severe_errors:
        return "scope_or_interpreter_safety_failure"
    if not _meets_quality_target(oracle, spec):
        return "local_model_or_prompt_ceiling_failure"
    if not _meets_quality_target(lexical, spec):
        return "retrieval_or_context_selection_failure"
    if (
        structural_pair.meaning_fidelity_mean_delta is not None
        and structural_pair.meaning_fidelity_mean_delta
        >= spec.thresholds.structural_min_mean_paired_fidelity_delta
        and structural.severe_error_count <= spec.thresholds.max_severe_errors
    ):
        return "structural_retrieval_candidate"
    return "lexical_default_not_beaten"


def score_stage4h_attribution(
    *,
    spec: Stage4hRunSpec,
    cases: Iterable[GoldCase],
    candidate_bundle: FrozenCandidateBundle,
    result_bundle: Stage4hRunResultBundle,
    blind_map: Stage4hBlindMap,
    reviews: Iterable[Stage4hOwnerReview],
) -> Stage4hAttributionReport:
    if candidate_bundle.run_id != spec.run_id or result_bundle.run_id != spec.run_id:
        raise ValueError("Stage 4h scoring inputs do not share one run id")
    if result_bundle.candidate_bundle_id != candidate_bundle.bundle_id:
        raise ValueError("Stage 4h results do not match the candidate bundle")
    if blind_map.run_id != spec.run_id:
        raise ValueError("Stage 4h blind map does not match the run")
    case_values = tuple(cases)
    by_case = {item.case_id: item for item in case_values}
    if set(by_case) != set(spec.case_ids) or len(by_case) != len(case_values):
        raise ValueError("Stage 4h scoring cases do not match the manifest")
    ordered_cases = tuple(by_case[case_id] for case_id in spec.case_ids)
    review_by_result, _ = _validate_reviews(
        result_bundle=result_bundle,
        blind_map=blind_map,
        reviews=reviews,
    )
    summaries = tuple(
        _arm_summary(
            arm=arm,
            spec=spec,
            cases=ordered_cases,
            candidates=candidate_bundle,
            results=result_bundle,
            review_by_result=review_by_result,
        )
        for arm in spec.arms
    )
    by_arm = {item.arm: item for item in summaries}
    pairs = (
        _paired_summary(
            left_arm="A1",
            right_arm="A2",
            results=result_bundle,
            review_by_result=review_by_result,
        ),
        _paired_summary(
            left_arm="A1",
            right_arm="A4",
            results=result_bundle,
            review_by_result=review_by_result,
        ),
    )
    structural_pair = next(item for item in pairs if item.right_arm == "A4")
    diagnosis = _diagnosis(
        summaries=by_arm,
        structural_pair=structural_pair,
        spec=spec,
    )
    promoted: Stage4hArm | None = None
    if spec.evaluation_mode == "confirmatory" and diagnosis == "structural_retrieval_candidate":
        structural = by_arm["A4"]
        lexical = by_arm["A1"]
        citation_drop = (
            None
            if structural.citation_precision is None or lexical.citation_precision is None
            else lexical.citation_precision - structural.citation_precision
        )
        if (
            structural_pair.meaning_fidelity_ci95_lower is not None
            and structural_pair.meaning_fidelity_ci95_lower > 0.0
            and citation_drop is not None
            and citation_drop <= spec.thresholds.max_citation_precision_drop
            and structural_pair.latency_multiplier is not None
            and structural_pair.latency_multiplier
            <= spec.thresholds.max_latency_multiplier
            and structural.severe_error_count <= spec.thresholds.max_severe_errors
        ):
            promoted = "A4"
    limitation = (
        "Pilot results are diagnostic only and cannot promote a representation."
        if spec.evaluation_mode == "pilot"
        else "Confirmatory result applies only to the preregistered corpus, questions, and model."
    )
    return Stage4hAttributionReport.create(
        spec=spec,
        result_bundle_id=result_bundle.bundle_id,
        blind_map_id=blind_map.mapping_id,
        arm_summaries=summaries,
        paired_summaries=pairs,
        diagnosis=diagnosis,
        promoted_arm=promoted,
        limitations=(limitation,),
    )


def attribution_report_json(report: Stage4hAttributionReport) -> str:
    return json.dumps(
        report.to_dict(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )


__all__ = [
    "Stage4hArmSummary",
    "Stage4hAttributionReport",
    "Stage4hPairedSummary",
    "Stage4hRetrievalSummary",
    "attribution_report_json",
    "score_stage4h_attribution",
]
