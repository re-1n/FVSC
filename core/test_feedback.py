"""FeedbackEngine coverage: the third cascade layer.

The engine existed but was imported by nothing — these tests pin down its
contract before wiring it into the service: question generation, answer
processing (confirm / reject / contextualize / promote / reactivate),
dedup of asked questions, and that map updates actually invalidate ρ.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from density_core import SemanticSpace, Judgment  # noqa: E402
from feedback import FeedbackEngine  # noqa: E402

DIM = 32


def _make_space() -> SemanticSpace:
    s = SemanticSpace(dim=DIM)
    s.materialize_judgment(Judgment(
        subject="свобода", verb="требует", object="ответственность",
        source_text="note_a.md",
    ))
    s.materialize_judgment(Judgment(
        subject="свобода", verb="требует", object="ответственность",
        quality="NEGATIVE", source_text="note_b.md",
    ))
    return s


def test_contradiction_question_generated():
    engine = FeedbackEngine(_make_space())
    questions = engine.generate_questions()
    kinds = {q.question_type for q in questions}
    assert "contradiction" in kinds


def test_confirm_reinforces_and_reject_archives():
    space = _make_space()
    engine = FeedbackEngine(space)
    q = next(q for q in engine.generate_questions()
             if q.question_type == "contradiction")

    engine.process_answer(q, 0)  # affirm wins

    j_affirm, j_negative = q.related_judgments
    assert j_affirm.confirmation_status == "confirmed"
    assert j_negative.confirmation_status == "rejected"

    concept = space.concepts["свобода"]
    archived = [c for c in concept.components if c.archived]
    active = [c for c in concept.components if not c.archived]
    assert any(c.judgment is j_negative for c in archived)
    assert any(c.judgment is j_affirm for c in active)
    # ρ must rebuild cleanly after invalidation
    rho = concept.rho
    assert rho is not None and np.isfinite(rho).all()


def test_answered_question_not_asked_again():
    engine = FeedbackEngine(_make_space())
    q = next(q for q in engine.generate_questions()
             if q.question_type == "contradiction")
    engine.process_answer(q, 2)  # contextualize both
    remaining = {x.question_type for x in engine.generate_questions()}
    assert "contradiction" not in remaining


def test_defeasible_promotion_to_core():
    space = SemanticSpace(dim=DIM)
    space.materialize_judgment(Judgment(
        subject="код", verb="выражает", object="мышление",
        source_text="note_c.md", defeasible=True, interpretation_layer=1,
    ))
    engine = FeedbackEngine(space)
    q = next(q for q in engine.generate_questions()
             if q.question_type == "defeasible")

    engine.process_answer(q, 0)  # "запиши как факт"

    j = q.related_judgments[0]
    assert j.interpretation_layer == 0
    assert j.defeasible is False
    assert j.confirmation_status == "confirmed"


def test_reactivate_archived_belief():
    space = _make_space()
    concept = space.concepts["свобода"]
    target = concept.components[0]
    target.archived = True
    target.weight = 1.0
    target.activation_count = 2
    concept.invalidate()

    engine = FeedbackEngine(space)
    q = next(q for q in engine.generate_questions()
             if q.question_type == "archive")
    engine.process_answer(q, 0)  # "да, по-прежнему"

    assert target.archived is False
    assert q.related_judgments[0].confirmation_status == "confirmed"


def test_skip_changes_nothing():
    space = _make_space()
    engine = FeedbackEngine(space)
    q = next(q for q in engine.generate_questions()
             if q.question_type == "contradiction")
    statuses_before = [j.confirmation_status for j in q.related_judgments]

    engine.process_answer(q, len(q.options) - 1)  # "Пропустить"

    assert [j.confirmation_status for j in q.related_judgments] == statuses_before
    assert len(engine.history) == 0


def test_stats_reflect_review_progress():
    space = _make_space()
    engine = FeedbackEngine(space)
    before = engine.stats()
    assert before["reviewed_judgments"] == 0

    q = next(q for q in engine.generate_questions()
             if q.question_type == "contradiction")
    engine.process_answer(q, 0)

    after = engine.stats()
    # NOTE: stats() counts components, and each judgment materializes into
    # both its subject's and object's concepts — so the count is a
    # per-component figure, not unique judgments.
    assert after["reviewed_judgments"] > before["reviewed_judgments"]
    assert after["total_interactions"] == 1
