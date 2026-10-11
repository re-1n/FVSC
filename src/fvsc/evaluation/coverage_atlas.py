"""Public horizontal minimal-pair atlas for compositional synthesis coverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from .synthesis import (
    GoldFacet,
    SynthesisCaseScore,
    SynthesisFixture,
    SyntheticSource,
)


CoveragePhenomenon = Literal[
    "negative_constraint",
    "temporal_contrast",
    "mixed_polarity",
    "conditional_scope",
    "distributed_rationale",
    "acceptance_boundary",
]


@dataclass(frozen=True)
class CoverageMinimalPair:
    pair_id: str
    phenomenon: CoveragePhenomenon
    easy: SynthesisFixture
    hard: SynthesisFixture

    def __post_init__(self) -> None:
        if self.easy.case_id == self.hard.case_id:
            raise ValueError("atlas pair variants require distinct case ids")
        easy_roles = {
            (facet.facet_id, facet.role) for facet in self.easy.facets
        }
        hard_roles = {
            (facet.facet_id, facet.role) for facet in self.hard.facets
        }
        if easy_roles != hard_roles:
            raise ValueError("atlas pair variants must preserve facet ids and roles")
        if self.easy.should_abstain != self.hard.should_abstain:
            raise ValueError("atlas pair variants must preserve abstention Gold")


def _source(label: str, text: str) -> SyntheticSource:
    return SyntheticSource(label, text)


def _facet(
    facet_id: str,
    role: str,
    label: str | None = None,
) -> GoldFacet:
    return GoldFacet(
        facet_id,
        role,  # type: ignore[arg-type]
        () if label is None else (label,),
    )


PUBLIC_COVERAGE_ATLAS = (
    CoverageMinimalPair(
        pair_id="atlas-negative-constraint",
        phenomenon="negative_constraint",
        easy=SynthesisFixture(
            case_id="atlas-negative-constraint-easy",
            question="What response protocol did the help desk request?",
            sources=(
                _source("S1", "First acknowledge the incident report."),
                _source("S2", "Do not suggest a repair until the reporter confirms the symptoms."),
            ),
            facets=(
                _facet("acknowledge-first", "required", "S1"),
                _facet("delay-repair", "required", "S2"),
                _facet("repair-immediately", "prohibited"),
            ),
        ),
        hard=SynthesisFixture(
            case_id="atlas-negative-constraint-hard",
            question="What response protocol did the help desk request?",
            sources=(
                _source("S1", "The opening move should show that the report was heard."),
                _source(
                    "S2",
                    "Troubleshooting was to wait on the far side of the reporter's symptom confirmation.",
                ),
            ),
            facets=(
                _facet("acknowledge-first", "required", "S1"),
                _facet("delay-repair", "required", "S2"),
                _facet("repair-immediately", "prohibited"),
            ),
        ),
    ),
    CoverageMinimalPair(
        pair_id="atlas-temporal-contrast",
        phenomenon="temporal_contrast",
        easy=SynthesisFixture(
            case_id="atlas-temporal-contrast-easy",
            question="How did the delivery policy change?",
            sources=(
                _source("S1", "Before May, invoices were delivered on paper."),
                _source("S2", "Since May, invoices are delivered electronically."),
            ),
            facets=(
                _facet("paper-before", "required", "S1"),
                _facet("electronic-now", "required", "S2"),
                _facet("paper-still-default", "prohibited"),
            ),
        ),
        hard=SynthesisFixture(
            case_id="atlas-temporal-contrast-hard",
            question="How did the delivery policy change?",
            sources=(
                _source("S1", "Paper carried invoices up to the April close."),
                _source("S2", "May marks the point from which delivery lives in the electronic channel."),
            ),
            facets=(
                _facet("paper-before", "required", "S1"),
                _facet("electronic-now", "required", "S2"),
                _facet("paper-still-default", "prohibited"),
            ),
        ),
    ),
    CoverageMinimalPair(
        pair_id="atlas-mixed-polarity",
        phenomenon="mixed_polarity",
        easy=SynthesisFixture(
            case_id="atlas-mixed-polarity-easy",
            question="Which contact channels are and are not included in the service?",
            sources=(
                _source("S1", "Email support is included."),
                _source("S2", "Telephone support is not included."),
            ),
            facets=(
                _facet("email-included", "required", "S1"),
                _facet("telephone-excluded", "required", "S2"),
                _facet("telephone-included", "prohibited"),
            ),
        ),
        hard=SynthesisFixture(
            case_id="atlas-mixed-polarity-hard",
            question="Which contact channels are and are not included in the service?",
            sources=(
                _source("S1", "Email remains within the service's remit."),
                _source("S2", "Telephone contact sits outside that remit."),
            ),
            facets=(
                _facet("email-included", "required", "S1"),
                _facet("telephone-excluded", "required", "S2"),
                _facet("telephone-included", "prohibited"),
            ),
        ),
    ),
    CoverageMinimalPair(
        pair_id="atlas-conditional-scope",
        phenomenon="conditional_scope",
        easy=SynthesisFixture(
            case_id="atlas-conditional-scope-easy",
            question="What is the deployment plan, including the backup condition?",
            sources=(
                _source("S1", "The primary deployment is Friday."),
                _source("S2", "Saturday is a backup only if compliance approves it."),
            ),
            facets=(
                _facet("friday-primary", "required", "S1"),
                _facet("saturday-conditional", "required", "S2"),
                _facet("saturday-confirmed", "prohibited"),
            ),
        ),
        hard=SynthesisFixture(
            case_id="atlas-conditional-scope-hard",
            question="What is the deployment plan, including the backup condition?",
            sources=(
                _source("S1", "Friday carries the primary deployment."),
                _source("S2", "Saturday enters the plan solely downstream of compliance approval."),
            ),
            facets=(
                _facet("friday-primary", "required", "S1"),
                _facet("saturday-conditional", "required", "S2"),
                _facet("saturday-confirmed", "prohibited"),
            ),
        ),
    ),
    CoverageMinimalPair(
        pair_id="atlas-distributed-rationale",
        phenomenon="distributed_rationale",
        easy=SynthesisFixture(
            case_id="atlas-distributed-rationale-easy",
            question="What scheduling decision was made, and why?",
            sources=(
                _source("S1", "The rehearsal was moved to the north hall."),
                _source("S2", "It was moved because the south hall's cooling system is unavailable."),
            ),
            facets=(
                _facet("north-hall", "required", "S1"),
                _facet("cooling-reason", "required", "S2"),
                _facet("acoustic-reason", "prohibited"),
            ),
        ),
        hard=SynthesisFixture(
            case_id="atlas-distributed-rationale-hard",
            question="What scheduling decision was made, and why?",
            sources=(
                _source("S1", "The north hall now holds the rehearsal slot."),
                _source("S2", "The displacement traces back to the south hall cooling outage."),
            ),
            facets=(
                _facet("north-hall", "required", "S1"),
                _facet("cooling-reason", "required", "S2"),
                _facet("acoustic-reason", "prohibited"),
            ),
        ),
    ),
    CoverageMinimalPair(
        pair_id="atlas-acceptance-boundary",
        phenomenon="acceptance_boundary",
        easy=SynthesisFixture(
            case_id="atlas-acceptance-boundary-easy",
            question="Which parts of the design did the reviewer accept and reject?",
            sources=(
                _source("S1", "The reviewer accepted the structural plan."),
                _source("S2", "The reviewer rejected the colour scheme."),
            ),
            facets=(
                _facet("structure-accepted", "required", "S1"),
                _facet("colour-rejected", "required", "S2"),
                _facet("whole-design-accepted", "prohibited"),
            ),
        ),
        hard=SynthesisFixture(
            case_id="atlas-acceptance-boundary-hard",
            question="Which parts of the design did the reviewer accept and reject?",
            sources=(
                _source("S1", "Approval attached to the design's structural plan."),
                _source("S2", "That approval did not extend to its colour scheme."),
            ),
            facets=(
                _facet("structure-accepted", "required", "S1"),
                _facet("colour-rejected", "required", "S2"),
                _facet("whole-design-accepted", "prohibited"),
            ),
        ),
    ),
)


def atlas_fixtures() -> tuple[SynthesisFixture, ...]:
    return tuple(
        fixture
        for pair in PUBLIC_COVERAGE_ATLAS
        for fixture in (pair.easy, pair.hard)
    )


@dataclass(frozen=True)
class CoveragePhenomenonSummary:
    pair_id: str
    phenomenon: CoveragePhenomenon
    easy_required_recall: float
    hard_required_recall: float
    easy_complete: bool
    hard_complete: bool
    completion_gap: int
    prohibited_violations: int


@dataclass(frozen=True)
class CoverageAtlasSummary:
    phenomena: tuple[CoveragePhenomenonSummary, ...]
    selected_phenomenon: CoveragePhenomenon | None
    selection_reason: str


def summarize_coverage_atlas(
    scores_by_case: Mapping[str, SynthesisCaseScore],
) -> CoverageAtlasSummary:
    expected = {fixture.case_id for fixture in atlas_fixtures()}
    if set(scores_by_case) != expected:
        raise ValueError("atlas scores must contain every frozen case exactly once")
    summaries: list[CoveragePhenomenonSummary] = []
    for pair in PUBLIC_COVERAGE_ATLAS:
        easy = scores_by_case[pair.easy.case_id]
        hard = scores_by_case[pair.hard.case_id]
        if easy.required_recall is None or hard.required_recall is None:
            raise ValueError("atlas positive cases require defined recall")
        easy_complete = easy.required_recall == 1.0
        hard_complete = hard.required_recall == 1.0
        summaries.append(
            CoveragePhenomenonSummary(
                pair_id=pair.pair_id,
                phenomenon=pair.phenomenon,
                easy_required_recall=easy.required_recall,
                hard_required_recall=hard.required_recall,
                easy_complete=easy_complete,
                hard_complete=hard_complete,
                completion_gap=int(easy_complete) - int(hard_complete),
                prohibited_violations=(
                    easy.prohibited_violations + hard.prohibited_violations
                ),
            )
        )
    maximum_gap = max(item.completion_gap for item in summaries)
    leaders = [item for item in summaries if item.completion_gap == maximum_gap]
    if maximum_gap <= 0:
        selected = None
        reason = "no hard-minus-easy completion gap"
    elif len(leaders) != 1:
        selected = None
        reason = "completion-gap tie requires more public fixtures"
    else:
        selected = leaders[0].phenomenon
        reason = f"unique maximum completion gap: {leaders[0].pair_id}"
    return CoverageAtlasSummary(
        phenomena=tuple(summaries),
        selected_phenomenon=selected,
        selection_reason=reason,
    )


__all__ = [
    "CoverageAtlasSummary",
    "CoverageMinimalPair",
    "CoveragePhenomenon",
    "CoveragePhenomenonSummary",
    "PUBLIC_COVERAGE_ATLAS",
    "atlas_fixtures",
    "summarize_coverage_atlas",
]
