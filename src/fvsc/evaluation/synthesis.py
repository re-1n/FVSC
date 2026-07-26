"""Preregistered coverage-aware synthesis contracts and deterministic scoring.

Gold facet roles are evaluation-only data.  They must never be rendered into a
generation prompt: the treatment changes only the synthesis instruction, while
both arms receive the same question and source texts.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal, Mapping, Sequence


FacetRole = Literal["required", "optional", "alternative", "guard", "prohibited"]
SynthesisArm = Literal["baseline", "coverage"]

_FACET_ROLES = frozenset(
    {"required", "optional", "alternative", "guard", "prohibited"}
)

BASELINE_INSTRUCTION = (
    "Answer the question briefly from the supplied sources. Cite every supported "
    "claim with its source labels. Abstain when the sources are insufficient."
)

COVERAGE_INSTRUCTION = (
    "Answer briefly from the supplied sources. Before writing, silently identify "
    "the distinct source-supported points needed to answer the question and preserve "
    "each independently relevant point. Keep caveats, guards, and alternatives in "
    "their proper role; do not turn them into positive claims. Cite every supported "
    "claim with its source labels. Abstain when the sources are insufficient."
)


def _nonempty(value: object, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must not be empty")
    return result


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


@dataclass(frozen=True)
class SyntheticSource:
    label: str
    text: str

    def __post_init__(self) -> None:
        label = _nonempty(self.label, field="source label")
        if not label.startswith("S") or not label[1:].isdigit() or label == "S0":
            raise ValueError("source label must use S<number> format")
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "text", _nonempty(self.text, field="source text"))


@dataclass(frozen=True)
class GoldFacet:
    facet_id: str
    role: FacetRole
    supporting_labels: tuple[str, ...] = ()
    alternative_group: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "facet_id", _nonempty(self.facet_id, field="facet id")
        )
        if self.role not in _FACET_ROLES:
            raise ValueError(f"unknown facet role: {self.role!r}")
        labels = tuple(_nonempty(item, field="supporting label") for item in self.supporting_labels)
        if len(labels) != len(set(labels)):
            raise ValueError("facet supporting labels must be unique")
        if self.role == "prohibited" and labels:
            raise ValueError("prohibited facets cannot have supporting labels")
        if self.role != "prohibited" and not labels:
            raise ValueError("non-prohibited facets require supporting labels")
        group = (
            None
            if self.alternative_group is None
            else _nonempty(self.alternative_group, field="alternative group")
        )
        if (self.role == "alternative") != (group is not None):
            raise ValueError("only alternative facets require an alternative group")
        object.__setattr__(self, "supporting_labels", labels)
        object.__setattr__(self, "alternative_group", group)


@dataclass(frozen=True)
class SynthesisFixture:
    case_id: str
    question: str
    sources: tuple[SyntheticSource, ...]
    facets: tuple[GoldFacet, ...]
    should_abstain: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", _nonempty(self.case_id, field="case id"))
        object.__setattr__(
            self, "question", _nonempty(self.question, field="fixture question")
        )
        if not self.sources:
            raise ValueError("fixture requires sources")
        labels = tuple(item.label for item in self.sources)
        if len(labels) != len(set(labels)):
            raise ValueError("fixture source labels must be unique")
        facet_ids = tuple(item.facet_id for item in self.facets)
        if len(facet_ids) != len(set(facet_ids)):
            raise ValueError("fixture facet ids must be unique")
        known_labels = set(labels)
        for facet in self.facets:
            if not set(facet.supporting_labels) <= known_labels:
                raise ValueError("facet references an unknown source label")
        required_count = sum(item.role == "required" for item in self.facets)
        if self.should_abstain:
            if required_count:
                raise ValueError("abstention fixture cannot contain required facets")
        elif required_count < 2:
            raise ValueError("positive fixture requires at least two required facets")


@dataclass(frozen=True)
class FacetObservation:
    """Human or deterministic-fixture annotation of one generated answer."""

    expressed_facet_ids: tuple[str, ...]
    citations_by_facet: Mapping[str, tuple[str, ...]]
    promoted_role_facet_ids: tuple[str, ...] = ()
    unsupported_facet_count: int = 0
    abstained: bool = False
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    latency_seconds: float | None = None

    def __post_init__(self) -> None:
        ids = tuple(_nonempty(item, field="expressed facet id") for item in self.expressed_facet_ids)
        if len(ids) != len(set(ids)):
            raise ValueError("expressed facet ids must be unique")
        promoted = tuple(
            _nonempty(item, field="promoted role facet id")
            for item in self.promoted_role_facet_ids
        )
        if len(promoted) != len(set(promoted)):
            raise ValueError("promoted role facet ids must be unique")
        if not set(promoted) <= set(ids):
            raise ValueError("promoted role facets must also be expressed")
        if isinstance(self.unsupported_facet_count, bool) or self.unsupported_facet_count < 0:
            raise ValueError("unsupported facet count must be non-negative")
        for field in ("prompt_tokens", "output_tokens"):
            value = getattr(self, field)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{field} must be a non-negative integer or None")
        if self.latency_seconds is not None and (
            not math.isfinite(float(self.latency_seconds))
            or float(self.latency_seconds) < 0.0
        ):
            raise ValueError("latency_seconds must be finite and non-negative")
        object.__setattr__(self, "expressed_facet_ids", ids)
        object.__setattr__(self, "promoted_role_facet_ids", promoted)


@dataclass(frozen=True)
class SynthesisCaseScore:
    case_id: str
    required_recall: float | None
    unsupported_facet_rate: float
    citation_correctness: float | None
    prohibited_violations: int
    role_violations: int
    abstention_correct: bool
    prompt_tokens: int | None
    output_tokens: int | None
    latency_seconds: float | None


@dataclass(frozen=True)
class SynthesisArmSummary:
    arm: SynthesisArm
    case_count: int
    macro_required_recall: float | None
    mean_unsupported_facet_rate: float
    mean_citation_correctness: float | None
    prohibited_violations: int
    role_violations: int
    abstention_accuracy: float
    prompt_tokens: int | None
    output_tokens: int | None
    mean_latency_seconds: float | None


@dataclass(frozen=True)
class SynthesisGateDecision:
    passed: bool
    reasons: tuple[str, ...]


def score_synthesis_case(
    fixture: SynthesisFixture,
    observation: FacetObservation,
) -> SynthesisCaseScore:
    """Score coverage without rewarding optional/guard/alternative promotion."""

    gold = {item.facet_id: item for item in fixture.facets}
    unknown = set(observation.expressed_facet_ids) - set(gold)
    if unknown:
        raise ValueError(f"observation contains unknown facet ids: {sorted(unknown)}")
    if not set(observation.citations_by_facet) <= set(observation.expressed_facet_ids):
        raise ValueError("citations may only be attached to expressed facets")

    expressed = set(observation.expressed_facet_ids)
    required = {item.facet_id for item in fixture.facets if item.role == "required"}
    required_recall = _rate(len(required & expressed), len(required))
    prohibited_violations = sum(
        item.role == "prohibited" and item.facet_id in expressed
        for item in fixture.facets
    )
    # Guards and alternatives may be mentioned only if their role remains explicit.
    # A flat facet annotation means they were promoted to ordinary positive prose.
    promoted = set(observation.promoted_role_facet_ids)
    invalid_promotions = promoted - {
        item.facet_id
        for item in fixture.facets
        if item.role in {"guard", "alternative"}
    }
    if invalid_promotions:
        raise ValueError(
            "only guard or alternative facets may be marked as promoted"
        )
    role_violations = len(promoted)

    cited = 0
    correct = 0
    for facet_id in expressed:
        facet = gold[facet_id]
        labels = tuple(observation.citations_by_facet.get(facet_id, ()))
        if facet.role == "prohibited":
            continue
        cited += 1
        if labels and set(labels) <= set(facet.supporting_labels):
            correct += 1
    citation_correctness = _rate(correct, cited)
    expressed_claim_count = len(expressed) + observation.unsupported_facet_count
    unsupported_rate = (
        0.0
        if expressed_claim_count == 0
        else (observation.unsupported_facet_count + prohibited_violations)
        / expressed_claim_count
    )
    return SynthesisCaseScore(
        case_id=fixture.case_id,
        required_recall=required_recall,
        unsupported_facet_rate=unsupported_rate,
        citation_correctness=citation_correctness,
        prohibited_violations=prohibited_violations,
        role_violations=role_violations,
        abstention_correct=observation.abstained == fixture.should_abstain,
        prompt_tokens=observation.prompt_tokens,
        output_tokens=observation.output_tokens,
        latency_seconds=observation.latency_seconds,
    )


def instruction_for_arm(arm: SynthesisArm) -> str:
    if arm == "baseline":
        return BASELINE_INSTRUCTION
    if arm == "coverage":
        return COVERAGE_INSTRUCTION
    raise ValueError(f"unknown synthesis arm: {arm!r}")


def summarize_synthesis_arm(
    arm: SynthesisArm,
    scores: Sequence[SynthesisCaseScore],
) -> SynthesisArmSummary:
    if not scores:
        raise ValueError("synthesis arm summary requires at least one case")
    case_ids = tuple(item.case_id for item in scores)
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("synthesis arm scores require unique case ids")

    def mean(values: Sequence[float]) -> float | None:
        return None if not values else math.fsum(values) / len(values)

    recalls = [item.required_recall for item in scores if item.required_recall is not None]
    citations = [
        item.citation_correctness
        for item in scores
        if item.citation_correctness is not None
    ]
    latencies = [
        item.latency_seconds for item in scores if item.latency_seconds is not None
    ]
    prompt_counts = [item.prompt_tokens for item in scores]
    output_counts = [item.output_tokens for item in scores]
    return SynthesisArmSummary(
        arm=arm,
        case_count=len(scores),
        macro_required_recall=mean(recalls),
        mean_unsupported_facet_rate=math.fsum(
            item.unsupported_facet_rate for item in scores
        )
        / len(scores),
        mean_citation_correctness=mean(citations),
        prohibited_violations=sum(item.prohibited_violations for item in scores),
        role_violations=sum(item.role_violations for item in scores),
        abstention_accuracy=sum(item.abstention_correct for item in scores) / len(scores),
        prompt_tokens=(
            sum(item for item in prompt_counts if item is not None)
            if all(item is not None for item in prompt_counts)
            else None
        ),
        output_tokens=(
            sum(item for item in output_counts if item is not None)
            if all(item is not None for item in output_counts)
            else None
        ),
        mean_latency_seconds=mean(latencies),
    )


def evaluate_synthesis_gate(
    baseline: SynthesisArmSummary,
    coverage: SynthesisArmSummary,
) -> SynthesisGateDecision:
    if baseline.arm != "baseline" or coverage.arm != "coverage":
        raise ValueError("gate requires baseline and coverage summaries")
    if baseline.case_count != coverage.case_count:
        raise ValueError("gate arms must contain the same number of cases")
    reasons: list[str] = []
    if (
        baseline.macro_required_recall is None
        or coverage.macro_required_recall is None
        or coverage.macro_required_recall <= baseline.macro_required_recall
    ):
        reasons.append("required facet recall did not improve")
    if coverage.prohibited_violations:
        reasons.append("coverage arm introduced prohibited facets")
    if coverage.role_violations:
        reasons.append("coverage arm promoted guards or alternatives")
    if (
        baseline.mean_citation_correctness is not None
        and (
            coverage.mean_citation_correctness is None
            or coverage.mean_citation_correctness
            < baseline.mean_citation_correctness
        )
    ):
        reasons.append("citation correctness decreased")
    if coverage.abstention_accuracy < baseline.abstention_accuracy:
        reasons.append("abstention accuracy decreased")
    return SynthesisGateDecision(passed=not reasons, reasons=tuple(reasons))


__all__ = [
    "BASELINE_INSTRUCTION",
    "COVERAGE_INSTRUCTION",
    "FacetObservation",
    "FacetRole",
    "GoldFacet",
    "SynthesisArm",
    "SynthesisArmSummary",
    "SynthesisCaseScore",
    "SynthesisFixture",
    "SynthesisGateDecision",
    "SyntheticSource",
    "evaluate_synthesis_gate",
    "instruction_for_arm",
    "score_synthesis_case",
    "summarize_synthesis_arm",
]
