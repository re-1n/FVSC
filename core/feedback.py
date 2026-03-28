"""
FVSC Feedback Engine — Interactive calibration of personal semantic maps.

Generates gentle, exploratory questions based on the state of the semantic map.
Processes user answers to refine the map: confirm, reject, contextualize, promote.

Design principles:
- Never accusatory ("you contradicted yourself" → "interesting nuance here")
- Always skippable ("you can skip this" is always an option)
- Indirect questions: "what feels closer?" not "confirm/reject"
- Exploratory: questions open reflection, not close it
- Gamified milestones: "you taught me something new"
"""

import time
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

try:
    from .density_core import (
        Judgment, Component, Concept, SemanticSpace,
        trace_inner_product, containment
    )
except ImportError:
    from density_core import (
        Judgment, Component, Concept, SemanticSpace,
        trace_inner_product, containment
    )


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FeedbackQuestion:
    """A question generated for the user by the feedback engine."""
    question_type: str          # "anomaly", "contradiction", "archive", "contrast", etc.
    priority: float             # 0.0–1.0 (higher = more important)
    prompt_text: str            # gentle question text
    options: list[str]          # answer choices
    related_judgments: list[Judgment] = field(default_factory=list)
    related_concepts: list[str] = field(default_factory=list)
    context: dict = field(default_factory=dict)


@dataclass
class FeedbackEvent:
    """A record of user interaction with their semantic map."""
    event_type: str             # "confirm", "reject", "promote", "contextualize", "reactivate", "calibrate"
    judgment_key: str           # "subject:verb:object"
    timestamp: float
    user_response: str          # chosen option or free text
    antourage_prompt: str       # what question triggered this
    old_value: Optional[str] = None
    new_value: Optional[str] = None


# ---------------------------------------------------------------------------
# Feedback Engine
# ---------------------------------------------------------------------------

class FeedbackEngine:
    """Analyzes a SemanticSpace and generates calibration questions.

    Does not depend on any UI — works through FeedbackQuestion/FeedbackEvent
    data structures. Can be driven by HTML, terminal, or Antourage API.
    """

    def __init__(self, space: SemanticSpace):
        self.space = space
        self.history: list[FeedbackEvent] = []
        self._asked_keys: set[str] = set()  # avoid asking twice about same thing

    # -------------------------------------------------------------------
    # Question generation
    # -------------------------------------------------------------------

    def generate_questions(self, max_count: int = 5) -> list[FeedbackQuestion]:
        """Analyze the map and generate prioritized questions."""
        questions: list[FeedbackQuestion] = []
        questions += self._anomaly_questions()
        questions += self._contradiction_questions()
        questions += self._archive_questions()
        questions += self._defeasible_questions()
        questions += self._contrast_questions()
        questions += self._milestone_questions()

        # Deduplicate by source text + concepts
        seen = set()
        unique = []
        for q in questions:
            # Use source texts of related judgments for dedup
            src_key = "|".join(sorted(j.source_text[:40] for j in q.related_judgments)) if q.related_judgments else ""
            key = f"{q.question_type}:{'|'.join(sorted(q.related_concepts))}:{src_key}"
            if key not in seen and key not in self._asked_keys:
                seen.add(key)
                unique.append(q)

        unique.sort(key=lambda q: -q.priority)
        return unique[:max_count]

    def _anomaly_questions(self) -> list[FeedbackQuestion]:
        """High anomaly = something new or contradictory. Ask gently."""
        questions = []
        for term, concept in self.space.concepts.items():
            for c in concept.components:
                if c.archived or c.judgment.confirmation_status != "unreviewed":
                    continue
                if c.judgment.anomaly_score is not None and c.judgment.anomaly_score > 0.7:
                    j = c.judgment
                    questions.append(FeedbackQuestion(
                        question_type="anomaly",
                        priority=0.9,
                        prompt_text=(
                            f"Интересное наблюдение: «{j.source_text[:80]}». "
                            f"Это что-то новое для тебя, или я неправильно понял контекст?"
                        ),
                        options=[
                            "Да, это важно для меня",
                            "Нет, это было сказано не всерьёз",
                            "Зависит от ситуации",
                            "Пропустить",
                        ],
                        related_judgments=[j],
                        related_concepts=[term],
                        context={"anomaly_score": j.anomaly_score},
                    ))
        return questions

    def _contradiction_questions(self) -> list[FeedbackQuestion]:
        """Two judgments with same S→O but different quality (AFFIRM vs NEGATIVE)."""
        questions = []
        # Collect judgments by (subject, object) pair
        pairs: dict[tuple[str, str], list[Judgment]] = {}
        for term, concept in self.space.concepts.items():
            for c in concept.components:
                if c.archived:
                    continue
                j = c.judgment
                key = (j.subject, j.object)
                pairs.setdefault(key, []).append(j)

        for (subj, obj), judgments in pairs.items():
            affirm = [j for j in judgments if j.quality == "AFFIRMATIVE"]
            negative = [j for j in judgments if j.quality == "NEGATIVE"]
            if affirm and negative:
                j_a = affirm[0]
                j_n = negative[0]
                questions.append(FeedbackQuestion(
                    question_type="contradiction",
                    priority=0.85,
                    prompt_text=(
                        f"Тут есть нюанс: в одном месте {subj} связан с {obj}, "
                        f"в другом — нет. Что ближе к правде?"
                    ),
                    options=[
                        f"Скорее да: {j_a.source_text[:60]}",
                        f"Скорее нет: {j_n.source_text[:60]}",
                        "Зависит от контекста",
                        "Пропустить",
                    ],
                    related_judgments=[j_a, j_n],
                    related_concepts=[subj, obj],
                ))
        return questions

    def _archive_questions(self) -> list[FeedbackQuestion]:
        """Archived components that were once significant."""
        questions = []
        for term, concept in self.space.concepts.items():
            for c in concept.components:
                if not c.archived:
                    continue
                # Only ask about formerly significant (high original weight)
                if c.weight * c.activation_count < 0.5:
                    continue
                j = c.judgment
                questions.append(FeedbackQuestion(
                    question_type="archive",
                    priority=0.5,
                    prompt_text=(
                        f"Раньше для тебя было важно: «{j.source_text[:80]}». "
                        f"Это по-прежнему так?"
                    ),
                    options=[
                        "Да, по-прежнему",
                        "Нет, уже нет",
                        "Частично",
                        "Пропустить",
                    ],
                    related_judgments=[j],
                    related_concepts=[term],
                ))
        return questions

    def _defeasible_questions(self) -> list[FeedbackQuestion]:
        """L1/L2 inferences that haven't been validated."""
        questions = []
        for term, concept in self.space.concepts.items():
            for c in concept.components:
                if c.archived:
                    continue
                j = c.judgment
                if j.defeasible and j.confirmation_status == "unreviewed":
                    layer_name = "лингвистическая догадка" if j.interpretation_layer == 1 else "наблюдение Антуража"
                    questions.append(FeedbackQuestion(
                        question_type="defeasible",
                        priority=0.6,
                        prompt_text=(
                            f"У меня есть {layer_name}: {j.subject} → {j.verb} → {j.object}. "
                            f"Это похоже на правду?"
                        ),
                        options=[
                            "Да, запиши как факт",
                            "Нет, убери это",
                            "Может быть, оставь как предположение",
                            "Пропустить",
                        ],
                        related_judgments=[j],
                        related_concepts=[term],
                    ))
        return questions

    def _contrast_questions(self) -> list[FeedbackQuestion]:
        """Two similar concepts — Kelly's repertory grid technique."""
        questions = []
        queryable = self.space._queryable_concepts(include_verbs=False)
        checked = set()
        for term_a, concept_a in queryable:
            for term_b, concept_b in queryable:
                if term_a >= term_b:
                    continue
                pair_key = f"{term_a}:{term_b}"
                if pair_key in checked:
                    continue
                checked.add(pair_key)
                rho_a = concept_a.rho_deep_norm
                rho_b = concept_b.rho_deep_norm
                if rho_a is None or rho_b is None:
                    continue
                sim = trace_inner_product(rho_a, rho_b)
                # High similarity = worth asking about the difference
                if 0.3 < sim < 0.8:
                    questions.append(FeedbackQuestion(
                        question_type="contrast",
                        priority=0.3,
                        prompt_text=(
                            f"'{term_a}' и '{term_b}' в твоей карте похожи. "
                            f"Чем они отличаются для тебя?"
                        ),
                        options=[
                            "Это почти одно и то же",
                            "Они разные, расскажу подробнее",
                            "Пропустить",
                        ],
                        related_concepts=[term_a, term_b],
                    ))
        return questions

    def _milestone_questions(self) -> list[FeedbackQuestion]:
        """Celebrate milestones — personal grounding, top concepts."""
        questions = []
        for term, concept in self.space.concepts.items():
            active = [c for c in concept.components if not c.archived]
            count = len(active)
            # Personal grounding milestone
            if count == self.space.PERSONAL_GROUNDING_THRESHOLD:
                questions.append(FeedbackQuestion(
                    question_type="milestone",
                    priority=0.2,
                    prompt_text=(
                        f"Я начинаю по-настоящему понимать, что для тебя значит "
                        f"'{term}'. Хочешь посмотреть, как я это вижу?"
                    ),
                    options=[
                        "Покажи",
                        "Потом",
                    ],
                    related_concepts=[term],
                ))
        return questions

    # -------------------------------------------------------------------
    # Answer processing
    # -------------------------------------------------------------------

    def process_answer(self, question: FeedbackQuestion, answer_index: int):
        """Process user's answer and update the semantic map.

        answer_index: 0-based index into question.options.
        Last option is always "skip".
        """
        answer = question.options[answer_index] if answer_index < len(question.options) else "skip"
        now = time.time()

        # Mark as asked (key format must match generate_questions dedup)
        src_key = "|".join(sorted(j.source_text[:40] for j in question.related_judgments)) if question.related_judgments else ""
        key = f"{question.question_type}:{'|'.join(sorted(question.related_concepts))}:{src_key}"
        self._asked_keys.add(key)

        # Skip
        if "пропустить" in answer.lower() or "потом" in answer.lower():
            return

        # --- Anomaly ---
        if question.question_type == "anomaly":
            j = question.related_judgments[0]
            if answer_index == 0:  # "Да, это важно"
                self._confirm_judgment(j, now)
            elif answer_index == 1:  # "Не всерьёз"
                self._reject_judgment(j, now)
            elif answer_index == 2:  # "Зависит от ситуации"
                self._contextualize_judgment(j, now)

        # --- Contradiction ---
        elif question.question_type == "contradiction":
            if answer_index == 0:  # Affirm wins
                self._confirm_judgment(question.related_judgments[0], now)
                self._reject_judgment(question.related_judgments[1], now)
            elif answer_index == 1:  # Negative wins
                self._confirm_judgment(question.related_judgments[1], now)
                self._reject_judgment(question.related_judgments[0], now)
            elif answer_index == 2:  # Context-dependent
                for j in question.related_judgments:
                    self._contextualize_judgment(j, now)

        # --- Archive ---
        elif question.question_type == "archive":
            j = question.related_judgments[0]
            if answer_index == 0:  # "По-прежнему"
                self._reactivate_judgment(j, now)
            elif answer_index == 1:  # "Уже нет"
                pass  # stays archived, mark as explicitly rejected
                j.confirmation_status = "rejected"
            elif answer_index == 2:  # "Частично"
                self._reactivate_judgment(j, now)
                self._contextualize_judgment(j, now)

        # --- Defeasible ---
        elif question.question_type == "defeasible":
            j = question.related_judgments[0]
            if answer_index == 0:  # "Запиши как факт"
                self._promote_to_core(j, now)
            elif answer_index == 1:  # "Убери"
                self._reject_judgment(j, now)
            # index 2 = "оставь как предположение" — no change

        # --- Contrast ---
        elif question.question_type == "contrast":
            if answer_index == 0:  # "Почти одно и то же"
                # Could merge concepts in future; for now just log
                pass
            # index 1 = "разные, расскажу" — would open dialogue, stub for now

        # Record event
        self.history.append(FeedbackEvent(
            event_type=question.question_type,
            judgment_key=":".join(question.related_concepts),
            timestamp=now,
            user_response=answer,
            antourage_prompt=question.prompt_text,
        ))

    # -------------------------------------------------------------------
    # Internal actions
    # -------------------------------------------------------------------

    def _confirm_judgment(self, j: Judgment, now: float):
        """User confirmed a judgment — strengthen it."""
        j.confirmation_status = "confirmed"
        j.timestamp = now  # refresh decay
        # Find and reinforce corresponding component
        for term in (j.subject, j.object):
            concept = self.space.concepts.get(term)
            if concept is None:
                continue
            for c in concept.components:
                if c.judgment is j:
                    c.activation_count += 1
                    c.timestamp = now
                    concept.invalidate()

    def _reject_judgment(self, j: Judgment, now: float):
        """User rejected a judgment — archive its components."""
        j.confirmation_status = "rejected"
        for term in (j.subject, j.object):
            concept = self.space.concepts.get(term)
            if concept is None:
                continue
            for c in concept.components:
                if c.judgment is j:
                    c.archived = True
                    concept.invalidate()

    def _contextualize_judgment(self, j: Judgment, now: float):
        """Mark judgment as context-dependent (needs tags later)."""
        j.confirmation_status = "contextualized"

    def _promote_to_core(self, j: Judgment, now: float):
        """User confirmed a defeasible inference — promote to L0."""
        j.interpretation_layer = 0
        j.defeasible = False
        j.confirmation_status = "confirmed"
        j.timestamp = now
        # Reinforce
        for term in (j.subject, j.object):
            concept = self.space.concepts.get(term)
            if concept is None:
                continue
            for c in concept.components:
                if c.judgment is j:
                    c.activation_count += 1
                    c.timestamp = now
                    concept.invalidate()

    def _reactivate_judgment(self, j: Judgment, now: float):
        """User confirmed an archived belief — reactivate it."""
        j.confirmation_status = "confirmed"
        j.timestamp = now
        for term in (j.subject, j.object):
            concept = self.space.concepts.get(term)
            if concept is None:
                continue
            for c in concept.components:
                if c.judgment is j and c.archived:
                    c.archived = False
                    c.activation_count += 1
                    c.timestamp = now
                    concept.invalidate()

    # -------------------------------------------------------------------
    # Stats & export
    # -------------------------------------------------------------------

    def stats(self) -> dict:
        """Summary statistics for the feedback session."""
        total = len(self.history)
        by_type = {}
        for e in self.history:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1

        # Count reviewed vs unreviewed
        reviewed = 0
        total_judgments = 0
        for concept in self.space.concepts.values():
            for c in concept.components:
                total_judgments += 1
                if c.judgment.confirmation_status != "unreviewed":
                    reviewed += 1

        return {
            "total_interactions": total,
            "by_type": by_type,
            "reviewed_judgments": reviewed,
            "total_judgments": total_judgments,
            "review_pct": (reviewed / total_judgments * 100) if total_judgments > 0 else 0,
        }

    def export_history(self) -> list[dict]:
        """Export feedback history as list of dicts (for JSON serialization)."""
        return [
            {
                "event_type": e.event_type,
                "judgment_key": e.judgment_key,
                "timestamp": e.timestamp,
                "user_response": e.user_response,
                "antourage_prompt": e.antourage_prompt,
            }
            for e in self.history
        ]
