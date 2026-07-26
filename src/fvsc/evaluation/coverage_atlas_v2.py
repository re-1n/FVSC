"""Versioned public extension for the tied coverage-atlas phenomena."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from .coverage_atlas import CoverageMinimalPair, CoveragePhenomenon
from .synthesis import GoldFacet, SynthesisCaseScore, SynthesisFixture, SyntheticSource


def _fixture(
    case_id: str,
    question: str,
    source_1: str,
    source_2: str,
    facet_1: str,
    facet_2: str,
    prohibited: str,
) -> SynthesisFixture:
    return SynthesisFixture(
        case_id=case_id,
        question=question,
        sources=(SyntheticSource("S1", source_1), SyntheticSource("S2", source_2)),
        facets=(
            GoldFacet(facet_1, "required", ("S1",)),
            GoldFacet(facet_2, "required", ("S2",)),
            GoldFacet(prohibited, "prohibited"),
        ),
    )


PUBLIC_COVERAGE_ATLAS_V2_EXTENSION = (
    CoverageMinimalPair(
        "atlas-v2-temporal-pricing",
        "temporal_contrast",
        _fixture(
            "atlas-v2-temporal-pricing-easy",
            "How did the storage pricing policy change?",
            "Before July, storage used one flat monthly price.",
            "From July onward, storage uses three usage tiers.",
            "flat-price-before",
            "tiered-price-now",
            "flat-price-now",
        ),
        _fixture(
            "atlas-v2-temporal-pricing-hard",
            "How did the storage pricing policy change?",
            "A single monthly figure governed storage through the June close.",
            "July opens the era in which storage cost follows three usage bands.",
            "flat-price-before",
            "tiered-price-now",
            "flat-price-now",
        ),
    ),
    CoverageMinimalPair(
        "atlas-v2-temporal-badges",
        "temporal_contrast",
        _fixture(
            "atlas-v2-temporal-badges-easy",
            "How did visitor badge validity change?",
            "Previously, visitor badges did not expire.",
            "Now, visitor badges expire after twenty-four hours.",
            "badges-permanent-before",
            "badges-expire-now",
            "badges-permanent-now",
        ),
        _fixture(
            "atlas-v2-temporal-badges-hard",
            "How did visitor badge validity change?",
            "The earlier badge regime placed no end time on visitor access.",
            "Under the present regime, a visitor badge reaches its limit after one day.",
            "badges-permanent-before",
            "badges-expire-now",
            "badges-permanent-now",
        ),
    ),
    CoverageMinimalPair(
        "atlas-v2-conditional-overflow",
        "conditional_scope",
        _fixture(
            "atlas-v2-conditional-overflow-easy",
            "What is the room plan, including the overflow condition?",
            "Room A is the main room.",
            "Room B opens only if registration exceeds fifty people.",
            "room-a-primary",
            "room-b-conditional",
            "room-b-confirmed",
        ),
        _fixture(
            "atlas-v2-conditional-overflow-hard",
            "What is the room plan, including the overflow condition?",
            "The event is anchored in Room A.",
            "Room B joins the arrangement solely beyond the fifty-registration threshold.",
            "room-a-primary",
            "room-b-conditional",
            "room-b-confirmed",
        ),
    ),
    CoverageMinimalPair(
        "atlas-v2-conditional-rollback",
        "conditional_scope",
        _fixture(
            "atlas-v2-conditional-rollback-easy",
            "What is the publication plan and its rollback condition?",
            "Publication is scheduled for Monday.",
            "Rollback happens Tuesday only if checksum verification fails.",
            "monday-publication",
            "tuesday-rollback-conditional",
            "tuesday-rollback-confirmed",
        ),
        _fixture(
            "atlas-v2-conditional-rollback-hard",
            "What is the publication plan and its rollback condition?",
            "Monday carries the publication step.",
            "Tuesday acquires a rollback step exclusively downstream of checksum failure.",
            "monday-publication",
            "tuesday-rollback-conditional",
            "tuesday-rollback-confirmed",
        ),
    ),
    CoverageMinimalPair(
        "atlas-v2-rationale-route",
        "distributed_rationale",
        _fixture(
            "atlas-v2-rationale-route-easy",
            "What route decision was made, and why?",
            "Freight was redirected to the east road.",
            "The change was made because the west bridge has a weight restriction.",
            "east-road",
            "bridge-weight-reason",
            "traffic-reason",
        ),
        _fixture(
            "atlas-v2-rationale-route-hard",
            "What route decision was made, and why?",
            "The east road now carries the freight route.",
            "That displacement traces to the weight ceiling on the western bridge.",
            "east-road",
            "bridge-weight-reason",
            "traffic-reason",
        ),
    ),
    CoverageMinimalPair(
        "atlas-v2-rationale-archive",
        "distributed_rationale",
        _fixture(
            "atlas-v2-rationale-archive-easy",
            "What archive decision was made, and why?",
            "The archive was relocated to the upper floor.",
            "It was relocated because the basement humidity is too high.",
            "upper-floor",
            "humidity-reason",
            "space-reason",
        ),
        _fixture(
            "atlas-v2-rationale-archive-hard",
            "What archive decision was made, and why?",
            "The upper floor now houses the archive.",
            "The move answers to the basement's excessive humidity.",
            "upper-floor",
            "humidity-reason",
            "space-reason",
        ),
    ),
)


def atlas_v2_extension_fixtures() -> tuple[SynthesisFixture, ...]:
    return tuple(
        fixture
        for pair in PUBLIC_COVERAGE_ATLAS_V2_EXTENSION
        for fixture in (pair.easy, pair.hard)
    )


@dataclass(frozen=True)
class CoverageExtensionPhenomenonSummary:
    phenomenon: CoveragePhenomenon
    pair_count: int
    completion_drop_count: int
    hard_mean_required_recall: float


@dataclass(frozen=True)
class CoverageExtensionSummary:
    phenomena: tuple[CoverageExtensionPhenomenonSummary, ...]
    selected_phenomenon: CoveragePhenomenon | None
    selection_reason: str


def summarize_coverage_extension(
    scores_by_case: Mapping[str, SynthesisCaseScore],
) -> CoverageExtensionSummary:
    expected = {item.case_id for item in atlas_v2_extension_fixtures()}
    if set(scores_by_case) != expected:
        raise ValueError("extension scores must contain every frozen case")
    rows: list[CoverageExtensionPhenomenonSummary] = []
    phenomena = sorted({pair.phenomenon for pair in PUBLIC_COVERAGE_ATLAS_V2_EXTENSION})
    for phenomenon in phenomena:
        pairs = [
            pair
            for pair in PUBLIC_COVERAGE_ATLAS_V2_EXTENSION
            if pair.phenomenon == phenomenon
        ]
        hard_recalls: list[float] = []
        drops = 0
        for pair in pairs:
            easy = scores_by_case[pair.easy.case_id].required_recall
            hard = scores_by_case[pair.hard.case_id].required_recall
            if easy is None or hard is None:
                raise ValueError("extension cases require defined recall")
            hard_recalls.append(hard)
            drops += int(easy == 1.0 and hard < 1.0)
        rows.append(
            CoverageExtensionPhenomenonSummary(
                phenomenon=phenomenon,
                pair_count=len(pairs),
                completion_drop_count=drops,
                hard_mean_required_recall=math.fsum(hard_recalls) / len(hard_recalls),
            )
        )
    maximum_drops = max(row.completion_drop_count for row in rows)
    leaders = [row for row in rows if row.completion_drop_count == maximum_drops]
    if maximum_drops == 0:
        selected = None
        reason = "no easy-to-hard completion drops"
    elif len(leaders) == 1:
        selected = leaders[0].phenomenon
        reason = "unique maximum completion-drop count"
    else:
        lowest_recall = min(row.hard_mean_required_recall for row in leaders)
        recall_leaders = [
            row for row in leaders if row.hard_mean_required_recall == lowest_recall
        ]
        if len(recall_leaders) == 1:
            selected = recall_leaders[0].phenomenon
            reason = "drop-count tie broken by lowest hard mean recall"
        else:
            selected = None
            reason = "extension remains tied; no target selected"
    return CoverageExtensionSummary(tuple(rows), selected, reason)


__all__ = [
    "CoverageExtensionPhenomenonSummary",
    "CoverageExtensionSummary",
    "PUBLIC_COVERAGE_ATLAS_V2_EXTENSION",
    "atlas_v2_extension_fixtures",
    "summarize_coverage_extension",
]
