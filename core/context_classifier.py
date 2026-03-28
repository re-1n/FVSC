# -*- coding: utf-8 -*-
"""
FVSC Context Classifier — determines referential status of NPs before extraction.

This is a LINGUISTIC layer, not a semantic one. It classifies HOW words behave
grammatically, not what they mean. The stenographic principle is preserved:
the layer determines WHAT is being talked about (generic vs specific, self vs other),
not what the speaker MEANS.

Two-level classification (Friedrich & Pinkal 2015):
  1. Clause-level: GENERIC / HABITUAL / EPISODIC (from tense, aspect, mood, predicate type)
  2. NP-level: CONCEPTUAL / SELF / INTERLOCUTOR / GENERIC / REFERENTIAL / QUOTE

Academic basis:
  - ACE Entity Classes (LDC 2005): SPC/GEN/USP
  - Reiter & Frank 2010 (ACL): Identifying Generic NPs
  - Friedrich & Pinkal 2015 (ACL): Discourse-sensitive genericity
  - Krifka et al. 1995 "The Generic Book": ILP vs SLP
  - Обобщённо-личные предложения (Russian grammar)
  - Derczynski et al. 2015: impersonal 2nd person in Russian

See FVSC whitepaper, Section V Step 3: "Контекстная классификация"
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ClauseType(Enum):
    GENERIC = "GENERIC"       # characterizing: "человек смертен"
    HABITUAL = "HABITUAL"     # habitual: "он обычно приходит в 8"
    EPISODIC = "EPISODIC"     # specific event: "он пришёл вчера"
    UNKNOWN = "UNKNOWN"


class RefStatus(Enum):
    CONCEPTUAL = "CONCEPTUAL"       # abstract concept → extract normally
    SELF = "SELF"                   # about the speaker → speaker's [self]
    INTERLOCUTOR = "INTERLOCUTOR"   # about the addressee → addressee's [self]
    GENERIC = "GENERIC"             # universal "you"/"one" → extract, weight * 0.7
    REFERENTIAL = "REFERENTIAL"     # specific instance → skip
    QUOTE = "QUOTE"                 # inside reported speech → source=citation


# ---------------------------------------------------------------------------
# Linguistic lexicons (language BEHAVIOR, not meanings)
# ---------------------------------------------------------------------------

# Individual-level predicates (stative, permanent → generic context)
# These describe inherent properties, not events.
ILP_ADJECTIVES = {
    "смертный", "разумный", "свободный", "живой", "сильный", "слабый",
    "способный", "достойный", "виновный", "ответственный", "честный",
    "умный", "глупый", "добрый", "злой", "красивый", "прекрасный",
    "счастливый", "несчастный", "одинокий", "важный", "нужный",
}

# Stage-level verbs (events, temporary → episodic context)
SLP_VERBS = {
    "прийти", "уйти", "упасть", "сказать", "увидеть", "взять",
    "дать", "купить", "продать", "найти", "потерять", "позвонить",
    "написать", "отправить", "получить", "начать", "закончить",
}

# Habituality markers (adverbs/particles that signal habitual/generic)
# Note: only single-token lemmas — spaCy tokenizes multi-word expressions
HABITUALITY_MARKERS = {
    "обычно", "часто", "всегда", "иногда", "редко", "бывает",
    "случается", "порой", "нередко",
}
# Multi-word habituality markers checked separately via bigram scan
HABITUALITY_MARKERS_MW = {"как правило"}

# Temporal specificity markers (signal episodic/specific)
# Note: only single-token lemmas — spaCy tokenizes multi-word expressions
TEMPORAL_SPECIFIC = {
    "вчера", "сегодня", "завтра", "потом", "тогда", "сейчас",
    "недавно", "утром", "вечером",
}
# Multi-word temporal markers checked separately via bigram scan
TEMPORAL_SPECIFIC_MW = {"только что"}

# Generic "ты" signals — conditional/temporal subordinators
GENERIC_TY_MARKS = {"если", "когда", "пока", "раз", "как только"}

# Specific "ты" signals — imperative or direct question
IMPERATIVE_SIGNALS = {"Imp"}  # spaCy Mood feature

# Referential determiners (make quasi-generic nouns specific)
REFERENTIAL_DETERMINERS = {
    "этот", "тот", "один", "какой-то", "некий", "такой",
    "другой", "мой", "твой", "наш", "ваш", "свой", "его", "её", "их",
}

# Quasi-generic nouns (need context to determine ref status)
QUASI_GENERIC_NOUNS = {
    "человек", "люди", "вещь", "штука", "место", "раз",
    "часть", "пара", "тип", "чувак", "девушка", "парень",
    "мужчина", "женщина", "ребёнок", "друг", "знакомый",
}

# Abstract nouns (almost always conceptual)
ABSTRACT_NOUNS = {
    "свобода", "любовь", "ответственность", "справедливость",
    "истина", "правда", "ложь", "счастье", "страдание",
    "смысл", "жизнь", "смерть", "время", "пространство",
    "сознание", "мышление", "душа", "разум", "воля",
    "красота", "добро", "зло", "вера", "надежда",
    "мужество", "честь", "долг", "достоинство",
}

# Speech verbs (signal QUOTE for their ccomp)
SPEECH_VERBS = {
    "говорить", "сказать", "утверждать", "писать", "заявлять",
    "считать", "полагать", "объяснять", "рассказывать",
}

# Self-pronouns
SELF_PRONOUNS = {"я", "себя"}

# Interlocutor pronouns
INTERLOCUTOR_PRONOUNS = {"ты", "вы"}


# ---------------------------------------------------------------------------
# Clause-level classifier
# ---------------------------------------------------------------------------

def classify_clause(verb_token) -> ClauseType:
    """Classify a clause as GENERIC, HABITUAL, or EPISODIC based on its verb.

    Uses: aspect (imperfective/perfective), tense, mood, predicate type.
    This is the PRIMARY signal for Russian (Friedrich & Pinkal 2015).
    """
    if verb_token is None:
        return ClauseType.UNKNOWN

    # Morphological features
    aspect = _morph_get(verb_token, "Aspect")   # Imp / Perf
    tense = _morph_get(verb_token, "Tense")     # Past / Pres / Fut
    mood = _morph_get(verb_token, "Mood")        # Ind / Imp / Cnd

    # Check for habituality markers in clause (single-token)
    has_habitual_marker = any(
        child.lemma_.lower() in HABITUALITY_MARKERS
        for child in verb_token.children
        if child.dep_ == "advmod"
    )

    has_temporal_specific = any(
        child.lemma_.lower() in TEMPORAL_SPECIFIC
        for child in verb_token.children
        if child.dep_ in ("advmod", "obl")
    )

    # Multi-word marker check via bigram scan (lazy — only if needed)
    if not has_habitual_marker or not has_temporal_specific:
        sent_tokens = [t.text.lower() for t in verb_token.sent]
        sent_bigrams = {f"{sent_tokens[i]} {sent_tokens[i+1]}" for i in range(len(sent_tokens) - 1)}
        if not has_habitual_marker and (sent_bigrams & HABITUALITY_MARKERS_MW):
            has_habitual_marker = True
        if not has_temporal_specific and (sent_bigrams & TEMPORAL_SPECIFIC_MW):
            has_temporal_specific = True

    # Conditional mood → generic
    if mood == "Cnd":
        return ClauseType.GENERIC

    # Habitual markers override
    if has_habitual_marker:
        return ClauseType.HABITUAL

    # Temporal specificity → episodic
    if has_temporal_specific:
        return ClauseType.EPISODIC

    # Present tense + imperfective → generic or habitual
    if tense == "Pres" and aspect == "Imp":
        return ClauseType.GENERIC

    # Past tense + perfective → episodic
    if tense == "Past" and aspect == "Perf":
        return ClauseType.EPISODIC

    # Past tense + imperfective → habitual
    if tense == "Past" and aspect == "Imp":
        return ClauseType.HABITUAL

    # Copula with adjective → check if ILP
    if verb_token.lemma_.lower() in ("быть", "являться", "стать"):
        for child in verb_token.children:
            if child.pos_ == "ADJ" and child.lemma_.lower() in ILP_ADJECTIVES:
                return ClauseType.GENERIC

    # Check predicate as ROOT adjective/noun (copular sentence)
    if verb_token.pos_ in ("ADJ", "NOUN") and verb_token.dep_ == "ROOT":
        if verb_token.lemma_.lower() in ILP_ADJECTIVES:
            return ClauseType.GENERIC

    return ClauseType.UNKNOWN


# ---------------------------------------------------------------------------
# NP-level classifier
# ---------------------------------------------------------------------------

def classify_np(token, clause_type: ClauseType = ClauseType.UNKNOWN,
                speaker_id: str | None = None) -> RefStatus:
    """Classify a noun/pronoun's referential status.

    Args:
        token: spaCy token (the noun/pronoun head)
        clause_type: result of classify_clause() on the governing verb
        speaker_id: ID of the message sender (for self/interlocutor detection)

    Returns:
        RefStatus enum value
    """
    lemma = token.lemma_.lower()
    pos = token.pos_

    # --- Pronouns ---
    if pos == "PRON":
        # "Я" / "себя" → SELF
        if lemma in SELF_PRONOUNS:
            return RefStatus.SELF

        # "Ты" / "вы" → INTERLOCUTOR or GENERIC
        if lemma in INTERLOCUTOR_PRONOUNS:
            return _classify_ty(token, clause_type)

        # Other pronouns (он, она, etc.) → REFERENTIAL (skip)
        return RefStatus.REFERENTIAL

    # --- Proper nouns → REFERENTIAL ---
    if pos == "PROPN":
        return RefStatus.REFERENTIAL

    # --- Common nouns ---
    if pos in ("NOUN", "ADJ"):

        # Abstract nouns → almost always CONCEPTUAL
        if lemma in ABSTRACT_NOUNS:
            return RefStatus.CONCEPTUAL

        # Quasi-generic nouns → check context
        if lemma in QUASI_GENERIC_NOUNS:
            return _classify_quasi_generic(token, clause_type)

        # Check for referential determiners
        if _has_referential_determiner(token):
            return RefStatus.REFERENTIAL

        # In a generic clause → CONCEPTUAL
        if clause_type in (ClauseType.GENERIC, ClauseType.HABITUAL):
            return RefStatus.CONCEPTUAL

        # Default for nouns: CONCEPTUAL
        return RefStatus.CONCEPTUAL

    return RefStatus.CONCEPTUAL


# ---------------------------------------------------------------------------
# "Ты" classifier (обобщённо-личное vs конкретное)
# ---------------------------------------------------------------------------

def _classify_ty(token, clause_type: ClauseType) -> RefStatus:
    """Classify "ты" as INTERLOCUTOR (specific addressee) or GENERIC (impersonal).

    Based on: Derczynski et al. 2015, обобщённо-личное предложение criteria.
    """
    verb = token.head if token.head.pos_ == "VERB" else None

    # --- Strong GENERIC signals ---

    # Inside conditional/temporal clause: "если ты...", "когда ты..."
    if verb and verb.dep_ == "advcl":
        for child in verb.children:
            if child.dep_ == "mark" and child.lemma_.lower() in GENERIC_TY_MARKS:
                return RefStatus.GENERIC

    # Generic clause type (present imperfective, conditional)
    if clause_type == ClauseType.GENERIC:
        # But check for specific override signals
        if verb and _morph_get(verb, "Mood") == "Imp":
            return RefStatus.INTERLOCUTOR  # imperative is specific
        return RefStatus.GENERIC

    # --- Strong INTERLOCUTOR signals ---

    # Imperative mood
    if verb and _morph_get(verb, "Mood") == "Imp":
        return RefStatus.INTERLOCUTOR

    # Past tense + perfective → specific event about addressee
    if verb:
        aspect = _morph_get(verb, "Aspect")
        tense = _morph_get(verb, "Tense")
        if tense == "Past" and aspect == "Perf":
            return RefStatus.INTERLOCUTOR

    # Temporal specificity marker in clause
    if verb:
        for child in verb.children:
            if child.dep_ in ("advmod", "obl") and child.lemma_.lower() in TEMPORAL_SPECIFIC:
                return RefStatus.INTERLOCUTOR

    # Habitual clause → generic "ты"
    if clause_type == ClauseType.HABITUAL:
        return RefStatus.GENERIC

    # Default: INTERLOCUTOR (in dialogue, "ты" is usually the addressee)
    return RefStatus.INTERLOCUTOR


# ---------------------------------------------------------------------------
# Quasi-generic noun classifier
# ---------------------------------------------------------------------------

def _classify_quasi_generic(token, clause_type: ClauseType) -> RefStatus:
    """Classify "человек", "вещь", etc. as CONCEPTUAL, GENERIC, or REFERENTIAL."""

    # Referential determiners → REFERENTIAL
    if _has_referential_determiner(token):
        return RefStatus.REFERENTIAL

    # Numeral → REFERENTIAL ("3 человека")
    for child in token.children:
        if child.dep_ == "nummod" or child.pos_ == "NUM":
            return RefStatus.REFERENTIAL
        # Proper noun modifier → REFERENTIAL
        if child.pos_ == "PROPN" and child.dep_ in ("appos", "flat:name", "nmod"):
            return RefStatus.REFERENTIAL
        # Relative clause → REFERENTIAL ("человек, который младше тебя")
        # A relative clause anchors the noun to a specific context
        if child.dep_ in ("acl:relcl", "acl"):
            return RefStatus.REFERENTIAL

    # In generic/habitual clause → CONCEPTUAL
    if clause_type in (ClauseType.GENERIC, ClauseType.HABITUAL):
        return RefStatus.CONCEPTUAL

    # Governing verb is SLP + perfective → REFERENTIAL (specific event)
    verb = token.head
    if verb and verb.pos_ == "VERB":
        if verb.lemma_.lower() in SLP_VERBS and _morph_get(verb, "Aspect") == "Perf":
            return RefStatus.REFERENTIAL

    # Default for quasi-generic without clear context: CONCEPTUAL
    # (better to record than to miss — stenographic principle applies to concepts)
    return RefStatus.CONCEPTUAL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_referential_determiner(token) -> bool:
    """Check if a noun has a referential determiner (этот, мой, etc.)."""
    for child in token.children:
        if child.dep_ in ("det", "amod") and child.lemma_.lower() in REFERENTIAL_DETERMINERS:
            return True
    return False


def _morph_get(token, feature: str) -> str | None:
    """Safely get a morphological feature from a spaCy token."""
    val = token.morph.get(feature)
    if val:
        return val[0] if isinstance(val, list) else val
    return None


# ---------------------------------------------------------------------------
# Convenience: annotate all tokens in a sentence
# ---------------------------------------------------------------------------

@dataclass
class TokenAnnotation:
    """Referential status annotation for a single token."""
    token_i: int
    lemma: str
    ref_status: RefStatus
    clause_type: ClauseType


def annotate_sentence(sent) -> dict[int, TokenAnnotation]:
    """Annotate all nouns/pronouns in a sentence with referential status.

    Returns: dict mapping token.i → TokenAnnotation
    """
    annotations = {}

    # First pass: classify clause for each verb
    clause_types = {}
    for token in sent:
        if token.pos_ in ("VERB", "AUX"):
            clause_types[token.i] = classify_clause(token)
        elif token.dep_ == "ROOT" and token.pos_ in ("ADJ", "NOUN"):
            clause_types[token.i] = classify_clause(token)

    # Second pass: classify each NP
    for token in sent:
        if token.pos_ not in ("NOUN", "PROPN", "PRON", "ADJ"):
            continue

        # Find governing verb's clause type
        head = token.head
        ct = ClauseType.UNKNOWN
        if head.i in clause_types:
            ct = clause_types[head.i]
        elif head.head.i in clause_types:
            ct = clause_types[head.head.i]

        ref = classify_np(token, ct)
        annotations[token.i] = TokenAnnotation(
            token_i=token.i,
            lemma=token.lemma_.lower(),
            ref_status=ref,
            clause_type=ct,
        )

    return annotations
