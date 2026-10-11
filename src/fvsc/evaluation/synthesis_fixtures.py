"""Frozen public, wholly synthetic fixtures for the synthesis coverage gate."""

from __future__ import annotations

from .synthesis import GoldFacet, SynthesisFixture, SyntheticSource


PUBLIC_SYNTHESIS_FIXTURES = (
    SynthesisFixture(
        case_id="public-synthesis-001",
        question="What changed in the release plan, and what constraint stayed fixed?",
        sources=(
            SyntheticSource("S1", "The release moved from Tuesday to Friday."),
            SyntheticSource("S2", "The testing budget remains capped at 40 hours."),
            SyntheticSource("S3", "If compliance signs off, Thursday is an alternative."),
        ),
        facets=(
            GoldFacet("release-friday", "required", ("S1",)),
            GoldFacet("testing-cap", "required", ("S2",)),
            GoldFacet("thursday-alternative", "alternative", ("S3",), "release-date"),
            GoldFacet("budget-increased", "prohibited"),
        ),
    ),
    SynthesisFixture(
        case_id="public-synthesis-002",
        question="How should the archive be opened and then handled?",
        sources=(
            SyntheticSource("S1", "Open the archive with the blue hardware key."),
            SyntheticSource("S2", "After opening, mount it read-only."),
            SyntheticSource("S3", "Do not export any record marked amber."),
        ),
        facets=(
            GoldFacet("blue-key", "required", ("S1",)),
            GoldFacet("read-only", "required", ("S2",)),
            GoldFacet("no-amber-export", "guard", ("S3",)),
            GoldFacet("cloud-upload", "prohibited"),
        ),
    ),
    SynthesisFixture(
        case_id="public-synthesis-003",
        question="What two effects did the garden change have?",
        sources=(
            SyntheticSource("S1", "The new hedge reduced afternoon wind on the patio."),
            SyntheticSource("S2", "It also blocked the kitchen's winter light."),
            SyntheticSource("S3", "The gardener happened to use hand tools."),
        ),
        facets=(
            GoldFacet("less-wind", "required", ("S1",)),
            GoldFacet("less-winter-light", "required", ("S2",)),
            GoldFacet("hand-tools", "optional", ("S3",)),
            GoldFacet("lower-water-use", "prohibited"),
        ),
    ),
    SynthesisFixture(
        case_id="public-synthesis-004",
        question="Summarize the sensor's operating range and reporting behavior.",
        sources=(
            SyntheticSource("S1", "The sensor is calibrated from −10°C to 45°C."),
            SyntheticSource("S2", "It reports a five-minute median, not raw samples."),
            SyntheticSource("S3", "Above 40°C, readings carry a high-temperature flag."),
        ),
        facets=(
            GoldFacet("temperature-range", "required", ("S1",)),
            GoldFacet("five-minute-median", "required", ("S2",)),
            GoldFacet("high-temperature-flag", "guard", ("S3",)),
            GoldFacet("one-second-stream", "prohibited"),
        ),
    ),
    SynthesisFixture(
        case_id="public-synthesis-005",
        question="What was decided about the workshop's place, format, and capacity?",
        sources=(
            SyntheticSource("S1", "The workshop will be held in the east library."),
            SyntheticSource("S2", "It will be in person rather than streamed."),
            SyntheticSource("S3", "Registration is limited to eighteen participants."),
        ),
        facets=(
            GoldFacet("east-library", "required", ("S1",)),
            GoldFacet("in-person", "required", ("S2",)),
            GoldFacet("capacity-eighteen", "required", ("S3",)),
            GoldFacet("recording-available", "prohibited"),
        ),
    ),
    SynthesisFixture(
        case_id="public-synthesis-006",
        question="Which coating was selected for the bridge rail?",
        sources=(
            SyntheticSource("S1", "The zinc coating passed the salt-spray test."),
            SyntheticSource("S2", "The ceramic coating passed the abrasion test."),
            SyntheticSource("S3", "The selection meeting is scheduled for next week."),
        ),
        facets=(
            GoldFacet("zinc-selected", "prohibited"),
            GoldFacet("ceramic-selected", "prohibited"),
        ),
        should_abstain=True,
    ),
)


__all__ = ["PUBLIC_SYNTHESIS_FIXTURES"]
