"""Public fixtures for missing-link abstention and answer/claim consistency."""

from __future__ import annotations

from .synthesis import GoldFacet, SynthesisFixture, SyntheticSource


PUBLIC_CONSISTENCY_FIXTURES = (
    SynthesisFixture(
        case_id="public-consistency-001",
        question="Which coating was selected, and when will application begin?",
        sources=(
            SyntheticSource("S1", "The committee selected the ceramic coating."),
            SyntheticSource("S2", "Application will begin on 14 September."),
            SyntheticSource("S3", "The zinc coating passed the salt-spray test."),
        ),
        facets=(
            GoldFacet("ceramic-selected", "required", ("S1",)),
            GoldFacet("application-date", "required", ("S2",)),
            GoldFacet("zinc-test", "optional", ("S3",)),
            GoldFacet("zinc-selected", "prohibited"),
        ),
    ),
    SynthesisFixture(
        case_id="public-consistency-002",
        question="Which coating was selected for the bridge rail?",
        sources=(
            SyntheticSource("S1", "The zinc coating passed the salt-spray test."),
            SyntheticSource("S2", "The ceramic coating passed the abrasion test."),
            SyntheticSource("S3", "The selection meeting is next week."),
        ),
        facets=(
            GoldFacet("zinc-selected", "prohibited"),
            GoldFacet("ceramic-selected", "prohibited"),
        ),
        should_abstain=True,
    ),
    SynthesisFixture(
        case_id="public-consistency-003",
        question="What caused the outage, and how long did recovery take?",
        sources=(
            SyntheticSource("S1", "A cracked coolant pipe caused the outage."),
            SyntheticSource("S2", "Service recovered after thirty-eight minutes."),
            SyntheticSource("S3", "A software update finished shortly before the outage."),
        ),
        facets=(
            GoldFacet("pipe-cause", "required", ("S1",)),
            GoldFacet("recovery-duration", "required", ("S2",)),
            GoldFacet("update-timing", "optional", ("S3",)),
            GoldFacet("update-cause", "prohibited"),
        ),
    ),
    SynthesisFixture(
        case_id="public-consistency-004",
        question="What caused the greenhouse alarm?",
        sources=(
            SyntheticSource("S1", "A delivery arrived three minutes before the alarm."),
            SyntheticSource("S2", "The humidity sensor was inspected after the alarm."),
            SyntheticSource("S3", "The incident review has not determined a cause."),
        ),
        facets=(
            GoldFacet("delivery-cause", "prohibited"),
            GoldFacet("sensor-cause", "prohibited"),
        ),
        should_abstain=True,
    ),
    SynthesisFixture(
        case_id="public-consistency-005",
        question="Which proposal was approved, and what limit was attached?",
        sources=(
            SyntheticSource("S1", "The board approved the north entrance proposal."),
            SyntheticSource("S2", "Approval limits construction noise to daytime hours."),
            SyntheticSource("S3", "The south entrance proposal was cheaper."),
        ),
        facets=(
            GoldFacet("north-approved", "required", ("S1",)),
            GoldFacet("daytime-limit", "required", ("S2",)),
            GoldFacet("south-cheaper", "optional", ("S3",)),
            GoldFacet("south-approved", "prohibited"),
        ),
    ),
    SynthesisFixture(
        case_id="public-consistency-006",
        question="Which entrance proposal was approved?",
        sources=(
            SyntheticSource("S1", "The north entrance proposal passed structural review."),
            SyntheticSource("S2", "The south entrance proposal was cheaper."),
            SyntheticSource("S3", "The board vote is scheduled for Monday."),
        ),
        facets=(
            GoldFacet("north-approved", "prohibited"),
            GoldFacet("south-approved", "prohibited"),
        ),
        should_abstain=True,
    ),
    SynthesisFixture(
        case_id="public-consistency-007",
        question="What task was completed, and who verified it?",
        sources=(
            SyntheticSource("S1", "Replacement of the west valve was completed."),
            SyntheticSource("S2", "Engineer Mira Chen verified the replacement."),
            SyntheticSource("S3", "Replacement of the east valve is planned for winter."),
        ),
        facets=(
            GoldFacet("west-completed", "required", ("S1",)),
            GoldFacet("chen-verified", "required", ("S2",)),
            GoldFacet("east-planned", "optional", ("S3",)),
            GoldFacet("east-completed", "prohibited"),
        ),
    ),
    SynthesisFixture(
        case_id="public-consistency-008",
        question="Which valve replacement has been completed?",
        sources=(
            SyntheticSource("S1", "Replacement of the west valve is budgeted."),
            SyntheticSource("S2", "Parts for the east valve have arrived."),
            SyntheticSource("S3", "Installation work begins next month."),
        ),
        facets=(
            GoldFacet("west-completed", "prohibited"),
            GoldFacet("east-completed", "prohibited"),
        ),
        should_abstain=True,
    ),
)


__all__ = ["PUBLIC_CONSISTENCY_FIXTURES"]
