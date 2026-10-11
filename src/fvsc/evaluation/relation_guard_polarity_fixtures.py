"""Frozen polarity and modality audit for the six registered S6 relations."""

from __future__ import annotations

from dataclasses import dataclass

from .relation_support_guard import GuardedRelation


@dataclass(frozen=True)
class RelationGuardPolarityFixture:
    case_id: str
    relation: GuardedRelation
    requirement: str
    source_text: str
    should_be_eligible: bool
    contrast: str


PUBLIC_RELATION_GUARD_POLARITY_FIXTURES = (
    RelationGuardPolarityFixture("polarity-confirmed-positive", "confirmed", "what is confirmed", "The west room is confirmed for Tuesday.", True, "affirmed"),
    RelationGuardPolarityFixture("polarity-confirmed-negated", "confirmed", "what is confirmed", "The west room is not confirmed for Tuesday.", False, "negated"),
    RelationGuardPolarityFixture("polarity-confirmed-modal", "confirmed", "what is confirmed", "The west room may be confirmed after inspection.", False, "modal"),
    RelationGuardPolarityFixture("polarity-conditional-positive", "conditional", "what remains conditional", "The terrace opens only if the permit arrives.", True, "affirmed"),
    RelationGuardPolarityFixture("polarity-conditional-negated", "conditional", "what remains conditional", "Terrace access does not depend on a permit.", False, "negated"),
    RelationGuardPolarityFixture("polarity-conditional-modal", "conditional", "what remains conditional", "Terrace access may become subject to a permit.", False, "modal"),
    RelationGuardPolarityFixture("polarity-accepted-positive", "accepted", "what was accepted", "The panel accepted the oak finish.", True, "affirmed"),
    RelationGuardPolarityFixture("polarity-accepted-negated", "accepted", "what was accepted", "The panel did not accept the oak finish.", False, "negated"),
    RelationGuardPolarityFixture("polarity-accepted-modal", "accepted", "what was accepted", "The panel might accept the oak finish later.", False, "modal"),
    RelationGuardPolarityFixture("polarity-declined-positive", "declined", "what was declined", "The panel declined the glass canopy.", True, "affirmed"),
    RelationGuardPolarityFixture("polarity-declined-negated", "declined", "what was declined", "The panel did not decline the glass canopy.", False, "negated"),
    RelationGuardPolarityFixture("polarity-declined-modal", "declined", "what was declined", "The panel could decline the glass canopy later.", False, "modal"),
    RelationGuardPolarityFixture("polarity-retained-positive", "retained", "what was retained", "The paper receipt was retained.", True, "affirmed"),
    RelationGuardPolarityFixture("polarity-retained-negated", "retained", "what was retained", "The paper receipt was not retained.", False, "negated"),
    RelationGuardPolarityFixture("polarity-retained-modal", "retained", "what was retained", "The paper receipt would be retained after approval.", False, "modal"),
    RelationGuardPolarityFixture("polarity-replaced-positive", "replaced", "what was replaced", "A kiosk replaced the staffed desk.", True, "affirmed"),
    RelationGuardPolarityFixture("polarity-replaced-negated", "replaced", "what was replaced", "A kiosk has not replaced the staffed desk.", False, "negated"),
    RelationGuardPolarityFixture("polarity-replaced-modal", "replaced", "what was replaced", "A kiosk might replace the staffed desk next year.", False, "modal"),
)


__all__ = [
    "PUBLIC_RELATION_GUARD_POLARITY_FIXTURES",
    "RelationGuardPolarityFixture",
]
