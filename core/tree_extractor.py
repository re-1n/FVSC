# -*- coding: utf-8 -*-
"""
FVSC Tree Extractor — Recursive judgment extraction from spaCy dependency trees.

Replaces the flat extract_judgments() with a recursive tree walk that preserves:
- Negation scoping (neg-raising verbs propagate negation to inner clauses)
- Modal envelopes (верить/думать/хотеть set modality on inner clause)
- Conditional constructions (если→то linked by condition_id)
- Quantifiers (все/каждый strengthen, некоторый/один weaken)
- Coordination unfolding (conj → separate judgments)

See FVSC whitepaper, Section V Step 3: "Извлечение суждений — рекурсивный обход дерева"

Usage: extract_judgments_recursive(nlp, texts) -> list[Judgment]
"""

from __future__ import annotations
import re
from dataclasses import dataclass, replace
from typing import Optional

from density_core import Judgment
from context_classifier import (
    classify_clause, classify_np, RefStatus, ClauseType,
)


# ---------------------------------------------------------------------------
# Extraction context — flows top-down through the dependency tree
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExtractionContext:
    """Logical context passed down the dependency tree. Immutable — create new via replace()."""
    negated: bool = False
    modality: float = 1.0
    modality_type: str = "FACTUAL"
    conditional: bool = False
    condition_id: int | None = None
    quantifier: str = "NONE"
    quant_weight: float = 1.0
    citation: bool = False
    citation_src: str | None = None


DEFAULT_CTX = ExtractionContext()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Verb lemma -> base intensity (from whitepaper Section IV.4)
RELATION_MAP = {
    "требовать": 0.9, "нуждаться": 0.8, "просить": 0.6,
    "включать": 0.8, "содержать": 0.8, "иметь": 0.7,
    "являться": 1.0, "быть": 0.7,
    "создавать": 0.9, "порождать": 0.9, "вызывать": 0.8,
    "давать": 0.7, "позволять": 0.7, "помогать": 0.6,
    "разрушать": 0.8, "мешать": 0.7, "отрицать": 0.8,
    "любить": 0.7, "ненавидеть": 0.9, "хотеть": 0.6,
    "думать": 0.5, "считать": 0.6, "знать": 0.8,
    "делать": 0.6, "использовать": 0.7, "строить": 0.7,
}

# Modal envelope verbs: (modality_type, weight, is_neg_raising)
MODAL_ENVELOPE_MAP = {
    "знать":       ("FACTUAL",      1.0, False),
    "верить":      ("EPISTEMIC",    0.5, False),
    "думать":      ("EPISTEMIC",    0.5, True),
    "считать":     ("EPISTEMIC",    0.6, True),
    "полагать":    ("EPISTEMIC",    0.5, True),
    "хотеть":      ("DESIDERATIVE", 0.6, False),
    "мечтать":     ("DESIDERATIVE", 0.5, False),
    "бояться":     ("EPISTEMIC",    0.4, False),
    "сомневаться": ("EPISTEMIC",    0.3, False),
    "надеяться":   ("DESIDERATIVE", 0.5, False),
}

# Quantifiers
UNIVERSAL_QUANTIFIERS = {
    "все": 1.3, "весь": 1.3, "каждый": 1.4, "любой": 1.2, "всегда": 1.3,
}
EXISTENTIAL_QUANTIFIERS = {
    "некоторый": 0.7, "какой-то": 0.6, "один": 0.5, "иногда": 0.6,
}

MODALITY_FLOOR = 0.05

NEG_PARTICLES = {"не", "ни"}
NEG_PRONOUNS = {"никто", "ничто", "никогда", "нигде", "никак", "никакой"}

# Pronouns to skip as subjects (but allow я/себя — routed to [self])
SKIP_SUBJECT_PRONOUNS = {"он", "она", "мы", "они", "это", "что", "кто"}

CONDITIONAL_MARKS = {"если", "когда", "раз"}

SPEECH_VERBS = {"говорить", "сказать", "утверждать", "писать", "заявлять"}

# Discourse pointers — don't fill the concept, redirect content
DISCOURSE_POINTERS = {
    "проблема", "вопрос", "суть", "дело", "причина", "цель",
    "задача", "смысл", "итог", "вывод", "результат", "следствие",
    "условие", "основа", "главное", "важное", "интересное",
}

# Adverb intensity modifiers
INTENSITY_MODIFIERS = {
    "немного": 0.5, "слегка": 0.5, "чуть": 0.5,
    "очень": 1.3, "крайне": 1.4, "абсолютно": 1.5,
    "совершенно": 1.5, "весьма": 1.2, "довольно": 1.1,
}


# ---------------------------------------------------------------------------
# Condition ID generator
# ---------------------------------------------------------------------------

_condition_counter = 0

def _next_condition_id() -> int:
    global _condition_counter
    _condition_counter += 1
    return _condition_counter


# ---------------------------------------------------------------------------
# Core: recursive tree walk
# ---------------------------------------------------------------------------

def extract_judgments_recursive(nlp, texts: list[str]) -> list[Judgment]:
    """Extract S→V→O judgments from texts using recursive dependency tree walk.

    Drop-in replacement for the flat extract_judgments().
    """
    results: list[Judgment] = []

    for doc in nlp.pipe(texts, batch_size=50):
        for sent in doc.sents:
            _walk(sent.root, DEFAULT_CTX, results, sent.text.strip()[:200])

    return results


def _walk(node, ctx: ExtractionContext, results: list[Judgment], sent_text: str):
    """Recursively walk the dependency tree, extracting judgments."""
    ctx = _apply_context_modifiers(node, ctx)

    if node.pos_ in ("VERB", "AUX") and node.dep_ != "conj":
        _handle_clause(node, ctx, results, sent_text)

    elif node.dep_ == "conj" and node.pos_ in ("VERB", "AUX"):
        # Coordinated verb — treat as its own clause
        _handle_clause(node, ctx, results, sent_text)

    elif node.dep_ == "ROOT" and node.pos_ in ("NOUN", "ADJ"):
        # Nominal/adjectival predicate: "Свобода — это ответственность"
        _handle_copula(node, ctx, results, sent_text)

    else:
        # Non-judgment node — recurse into children
        for child in node.children:
            _walk(child, ctx, results, sent_text)

    # amod on nouns — always extract regardless of node type
    if node.pos_ == "NOUN" and len(node.lemma_) >= 3:
        _handle_amod(node, ctx, results, sent_text)


# ---------------------------------------------------------------------------
# Context modifier detection
# ---------------------------------------------------------------------------

def _apply_context_modifiers(node, parent_ctx: ExtractionContext) -> ExtractionContext:
    """Detect logical operators at this node and update context for its subtree."""
    negated = parent_ctx.negated
    modality = parent_ctx.modality
    modality_type = parent_ctx.modality_type
    conditional = parent_ctx.conditional
    condition_id = parent_ctx.condition_id
    quantifier = parent_ctx.quantifier
    quant_weight = parent_ctx.quant_weight
    citation = parent_ctx.citation
    citation_src = parent_ctx.citation_src

    for child in node.children:
        # --- Negation ---
        if child.dep_ == "advmod" and child.lemma_.lower() in NEG_PARTICLES:
            negated = not negated  # toggle for double negation
        if child.lemma_.lower() in NEG_PRONOUNS:
            negated = True

        # --- Quantifiers (on noun children) ---
        if child.dep_ in ("det", "amod"):
            lemma = child.lemma_.lower()
            if lemma in UNIVERSAL_QUANTIFIERS:
                quantifier = "UNIVERSAL"
                quant_weight = UNIVERSAL_QUANTIFIERS[lemma]
            elif lemma in EXISTENTIAL_QUANTIFIERS:
                quantifier = "EXISTENTIAL"
                quant_weight = EXISTENTIAL_QUANTIFIERS[lemma]

    # --- Modal verbs (мочь, должен) — modify modality for xcomp children ---
    if node.pos_ == "VERB":
        lemma = node.lemma_.lower()
        if lemma in ("мочь", "суметь"):
            modality = min(modality, 0.5)
            modality_type = "EPISTEMIC"
        elif lemma in ("должен", "обязан", "следовать"):
            modality = min(modality, 0.7)
            modality_type = "DEONTIC"

    # --- Conditional: advcl with mark "если" ---
    if node.dep_ == "advcl":
        for child in node.children:
            if child.dep_ == "mark" and child.lemma_.lower() in CONDITIONAL_MARKS:
                conditional = True
                modality = min(modality, 0.4)
                modality_type = "CONDITIONAL"
                break

    # --- Morphological mood ---
    mood = node.morph.get("Mood")
    if mood:
        mood_val = mood[0] if isinstance(mood, list) else mood
        if mood_val == "Cnd":
            conditional = True
            modality = min(modality, 0.4)
            modality_type = "CONDITIONAL"
        elif mood_val == "Imp":
            modality = min(modality, 0.7)
            modality_type = "DEONTIC"

    # --- Citation: ccomp under speech verb ---
    if node.dep_ in ("ccomp", "parataxis"):
        head = node.head
        if head.lemma_.lower() in SPEECH_VERBS:
            citation = True
            for sibling in head.children:
                if sibling.dep_ == "nsubj" and sibling.pos_ == "PROPN":
                    citation_src = sibling.lemma_

    if (negated == parent_ctx.negated and modality == parent_ctx.modality
            and modality_type == parent_ctx.modality_type
            and conditional == parent_ctx.conditional
            and quantifier == parent_ctx.quantifier
            and quant_weight == parent_ctx.quant_weight
            and citation == parent_ctx.citation):
        return parent_ctx  # no change — reuse object

    return ExtractionContext(
        negated=negated, modality=modality, modality_type=modality_type,
        conditional=conditional, condition_id=condition_id,
        quantifier=quantifier, quant_weight=quant_weight,
        citation=citation, citation_src=citation_src,
    )


# ---------------------------------------------------------------------------
# Clause handler — the main extraction point
# ---------------------------------------------------------------------------

def _handle_clause(verb_node, ctx: ExtractionContext, results: list[Judgment],
                   sent_text: str):
    """Handle a verb node: extract judgments or delegate to envelope/conditional."""

    verb_lemma = verb_node.lemma_.lower()

    # --- Check for modal envelope ---
    if _is_modal_envelope(verb_node):
        _handle_modal_envelope(verb_node, ctx, results, sent_text)
        return

    # --- Check for conditional construction ---
    condition_clauses = []
    for child in verb_node.children:
        if child.dep_ == "advcl":
            for mark in child.children:
                if mark.dep_ == "mark" and mark.lemma_.lower() in CONDITIONAL_MARKS:
                    condition_clauses.append(child)
                    break

    if condition_clauses:
        _handle_conditional(verb_node, condition_clauses, ctx, results, sent_text)
        return

    # --- Collect subjects and objects ---
    subjects_raw = []
    objects_raw = []
    has_passive = False

    for child in verb_node.children:
        if child.dep_ in ("nsubj", "nsubj:pass") and child.pos_ in ("NOUN", "PROPN", "PRON"):
            subjects_raw.extend(_expand_coordination(child))
            if child.dep_ == "nsubj:pass":
                has_passive = True

        if child.dep_ in ("obj", "dobj", "obl", "iobj") and child.pos_ in ("NOUN", "PROPN"):
            objects_raw.extend(_expand_coordination(child))

    # Fallback: adjectival/clausal complements as objects
    if not objects_raw:
        for child in verb_node.children:
            if child.dep_ in ("xcomp", "ccomp", "acomp") and child.pos_ in ("NOUN", "ADJ", "PROPN"):
                objects_raw.extend(_expand_coordination(child))

    # --- Passive voice inversion ---
    if has_passive:
        # Look for agent in obl
        agents = []
        for child in verb_node.children:
            if child.dep_ == "obl" and child.pos_ in ("NOUN", "PROPN"):
                agents.append(child)
        if agents:
            subjects_raw, objects_raw = agents, subjects_raw
        else:
            subjects_raw, objects_raw = objects_raw, subjects_raw

    # --- Classify clause ---
    clause_type = classify_clause(verb_node)

    # --- Generate judgments ---
    intensity = RELATION_MAP.get(verb_lemma, 0.5)
    effective_quality = "NEGATIVE" if ctx.negated else "AFFIRMATIVE"
    effective_modality = max(MODALITY_FLOOR, ctx.modality * ctx.quant_weight)

    for subj in subjects_raw:
        subj_lemma = subj.lemma_.lower()
        if len(subj_lemma) < 2 and subj_lemma not in ("я",):
            continue

        # Context classifier: determine referential status
        subj_ref = classify_np(subj, clause_type)

        # REFERENTIAL → skip (specific instance, not a concept)
        if subj_ref == RefStatus.REFERENTIAL:
            continue

        # Discourse pointer check (supplements classifier)
        if subj_lemma in DISCOURSE_POINTERS and _is_discourse_pointer_usage(subj):
            continue

        # GENERIC "ты" / "человек" → extract but reduce weight
        subj_modality = effective_modality
        if subj_ref == RefStatus.GENERIC:
            subj_modality *= 0.7

        # INTERLOCUTOR → remap subject to interlocutor marker
        effective_subj = subj_lemma
        if subj_ref == RefStatus.INTERLOCUTOR:
            effective_subj = "ты"  # keep as "ты", materialize_judgment will handle

        for obj in objects_raw:
            obj_lemma = obj.lemma_.lower()
            if len(obj_lemma) < 2 or obj_lemma == subj_lemma:
                continue

            # Classify object too
            obj_ref = classify_np(obj, clause_type)
            if obj_ref == RefStatus.REFERENTIAL:
                continue

            obj_modality = subj_modality
            if obj_ref == RefStatus.GENERIC:
                obj_modality *= 0.7

            results.append(Judgment(
                subject=effective_subj,
                verb=verb_lemma,
                object=obj_lemma,
                quality=effective_quality,
                modality=obj_modality,
                intensity=min(1.0, intensity),
                source_text=sent_text,
                condition_id=ctx.condition_id,
                condition_role="CONSEQUENT" if ctx.conditional and ctx.condition_id else None,
            ))

    # --- Recurse into subordinate clauses (but not condition_clauses) ---
    for child in verb_node.children:
        if child.dep_ in ("ccomp", "xcomp", "advcl", "acl", "acl:relcl"):
            if child not in condition_clauses:
                _walk(child, ctx, results, sent_text)


# ---------------------------------------------------------------------------
# Modal envelope handler
# ---------------------------------------------------------------------------

def _is_modal_envelope(verb_node) -> bool:
    """A verb is a modal envelope if it's in MODAL_ENVELOPE_MAP and has ccomp/xcomp."""
    if verb_node.lemma_.lower() not in MODAL_ENVELOPE_MAP:
        return False
    return any(child.dep_ in ("ccomp", "xcomp") for child in verb_node.children)


def _handle_modal_envelope(verb_node, ctx: ExtractionContext,
                           results: list[Judgment], sent_text: str):
    """Process modal envelope: propagate modality (and possibly negation) to inner clause."""
    lemma = verb_node.lemma_.lower()
    mod_type, mod_weight, is_neg_raising = MODAL_ENVELOPE_MAP[lemma]

    # Build inner context
    inner_negated = ctx.negated
    if ctx.negated and is_neg_raising:
        inner_negated = True   # negation pushes down
    elif ctx.negated and not is_neg_raising:
        inner_negated = False  # negation stays on envelope
        mod_weight *= 0.3      # strongly reduce modality — speaker rejects content

    inner_ctx = ExtractionContext(
        negated=inner_negated,
        modality=ctx.modality * mod_weight,
        modality_type=mod_type,
        conditional=ctx.conditional,
        condition_id=ctx.condition_id,
        quantifier=ctx.quantifier,
        quant_weight=ctx.quant_weight,
        citation=ctx.citation,
        citation_src=ctx.citation_src,
    )

    # Recurse into inner clause(s)
    for child in verb_node.children:
        if child.dep_ in ("ccomp", "xcomp"):
            _walk(child, inner_ctx, results, sent_text)


# ---------------------------------------------------------------------------
# Conditional handler
# ---------------------------------------------------------------------------

def _handle_conditional(main_verb, condition_clauses: list,
                        ctx: ExtractionContext, results: list[Judgment],
                        sent_text: str):
    """Handle "если X, то Y" — link antecedent and consequent with condition_id."""
    cond_id = _next_condition_id()

    # Process antecedent(s) — the "если" clause(s)
    for cond_clause in condition_clauses:
        ante_ctx = ExtractionContext(
            negated=ctx.negated,
            modality=min(ctx.modality, 0.4),
            modality_type="CONDITIONAL",
            conditional=True,
            condition_id=cond_id,
            quantifier=ctx.quantifier,
            quant_weight=ctx.quant_weight,
            citation=ctx.citation,
            citation_src=ctx.citation_src,
        )
        _walk(cond_clause, ante_ctx, results, sent_text)

    # Mark antecedent judgments
    for j in results:
        if j.condition_id == cond_id and j.condition_role is None:
            j.condition_role = "ANTECEDENT"

    # Process consequent — the main clause
    cons_ctx = ExtractionContext(
        negated=ctx.negated,
        modality=min(ctx.modality, 0.4),
        modality_type="CONDITIONAL",
        conditional=True,
        condition_id=cond_id,
        quantifier=ctx.quantifier,
        quant_weight=ctx.quant_weight,
        citation=ctx.citation,
        citation_src=ctx.citation_src,
    )

    # Extract main clause arguments directly (without re-checking for conditionals)
    _extract_clause_arguments(main_verb, cons_ctx, results, sent_text)


def _extract_clause_arguments(verb_node, ctx: ExtractionContext,
                              results: list[Judgment], sent_text: str):
    """Extract judgments from a verb node without checking for envelope/conditional."""
    verb_lemma = verb_node.lemma_.lower()

    subjects_raw = []
    objects_raw = []

    for child in verb_node.children:
        if child.dep_ in ("nsubj", "nsubj:pass") and child.pos_ in ("NOUN", "PROPN", "PRON"):
            subjects_raw.extend(_expand_coordination(child))
        if child.dep_ in ("obj", "dobj", "obl", "iobj") and child.pos_ in ("NOUN", "PROPN"):
            objects_raw.extend(_expand_coordination(child))

    if not objects_raw:
        for child in verb_node.children:
            if child.dep_ in ("xcomp", "ccomp", "acomp") and child.pos_ in ("NOUN", "ADJ", "PROPN"):
                objects_raw.extend(_expand_coordination(child))

    clause_type = classify_clause(verb_node)
    intensity = RELATION_MAP.get(verb_lemma, 0.5)
    effective_quality = "NEGATIVE" if ctx.negated else "AFFIRMATIVE"
    effective_modality = max(MODALITY_FLOOR, ctx.modality * ctx.quant_weight)

    for subj in subjects_raw:
        subj_lemma = subj.lemma_.lower()
        if len(subj_lemma) < 2 and subj_lemma not in ("я",):
            continue

        subj_ref = classify_np(subj, clause_type)
        if subj_ref == RefStatus.REFERENTIAL:
            continue

        for obj in objects_raw:
            obj_lemma = obj.lemma_.lower()
            if len(obj_lemma) < 2 or obj_lemma == subj_lemma:
                continue

            obj_ref = classify_np(obj, clause_type)
            if obj_ref == RefStatus.REFERENTIAL:
                continue

            results.append(Judgment(
                subject=subj_lemma,
                verb=verb_lemma,
                object=obj_lemma,
                quality=effective_quality,
                modality=effective_modality,
                intensity=min(1.0, intensity),
                source_text=sent_text,
                condition_id=ctx.condition_id,
                condition_role="CONSEQUENT",
            ))


# ---------------------------------------------------------------------------
# Copula handler (nominal predicates)
# ---------------------------------------------------------------------------

def _handle_copula(node, ctx: ExtractionContext, results: list[Judgment],
                   sent_text: str):
    """Handle nominal sentences: "Свобода — это ответственность"."""
    # In UD Russian, copular sentences have the predicate as ROOT
    # and the subject as nsubj child
    subjects = []
    for child in node.children:
        if child.dep_ == "nsubj" and child.pos_ in ("NOUN", "PROPN", "PRON"):
            subjects.extend(_expand_coordination(child))

    if not subjects:
        # No subject found — recurse into children
        for child in node.children:
            _walk(child, ctx, results, sent_text)
        return

    # Classify clause for the copular predicate
    clause_type = classify_clause(node)

    effective_quality = "NEGATIVE" if ctx.negated else "AFFIRMATIVE"
    effective_modality = max(MODALITY_FLOOR, ctx.modality * ctx.quant_weight)

    predicate_lemma = node.lemma_.lower()
    if len(predicate_lemma) < 2:
        return

    for subj in subjects:
        subj_lemma = subj.lemma_.lower()
        if len(subj_lemma) < 2 and subj_lemma not in ("я",):
            continue

        # Context classifier on subject
        subj_ref = classify_np(subj, clause_type)
        if subj_ref == RefStatus.REFERENTIAL:
            continue

        if subj_ref == RefStatus.GENERIC:
            effective_modality *= 0.7

        verb = "cop:это"
        # Check if there's an explicit copula
        for child in node.children:
            if child.dep_ == "cop":
                verb = f"cop:{child.lemma_.lower()}"
                break

        results.append(Judgment(
            subject=subj_lemma,
            verb=verb,
            object=predicate_lemma,
            quality=effective_quality,
            modality=effective_modality,
            intensity=0.7,
            source_text=sent_text,
            condition_id=ctx.condition_id,
            condition_role=ctx.condition_id and "CONSEQUENT" or None,
        ))

    # Recurse into children for subordinate clauses
    for child in node.children:
        if child.dep_ in ("ccomp", "xcomp", "advcl", "acl", "acl:relcl"):
            _walk(child, ctx, results, sent_text)


# ---------------------------------------------------------------------------
# Adjective modifier handler
# ---------------------------------------------------------------------------

def _handle_amod(node, ctx: ExtractionContext, results: list[Judgment],
                 sent_text: str):
    """Extract amod judgments: "важная свобода" → свобода contains важный."""
    effective_quality = "NEGATIVE" if ctx.negated else "AFFIRMATIVE"
    effective_modality = max(MODALITY_FLOOR, ctx.modality * ctx.quant_weight)

    for child in node.children:
        if child.dep_ == "amod" and child.pos_ == "ADJ":
            adj_lemma = child.lemma_.lower()
            if len(adj_lemma) < 2:
                continue

            # Check for intensity modifier: "очень важный"
            intensity = 0.5
            for adv in child.children:
                if adv.dep_ == "advmod" and adv.lemma_.lower() in INTENSITY_MODIFIERS:
                    intensity *= INTENSITY_MODIFIERS[adv.lemma_.lower()]

            results.append(Judgment(
                subject=node.lemma_.lower(),
                verb="amod",
                object=adj_lemma,
                quality=effective_quality,
                modality=effective_modality,
                intensity=min(1.0, intensity),
                source_text=sent_text,
            ))


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _expand_coordination(node) -> list:
    """Expand coordination: return [node] + all conj children."""
    result = [node]
    for child in node.children:
        if child.dep_ == "conj":
            result.append(child)
    return result


def _is_discourse_pointer_usage(node) -> bool:
    """Check if a noun is used as a discourse pointer: "проблема в том, что..."."""
    # Check for patterns like "X в том, что", "X заключается в", "X состоит в"
    sent_text = node.sent.text.lower()
    lemma = node.lemma_.lower()

    for pattern in (f"{lemma} в том", f"{lemma} заключается", f"{lemma} состоит"):
        if re.search(r'\b' + re.escape(pattern), sent_text):
            return True

    # Check for determiner + abstract noun pattern: "эта проблема", "моя цель"
    for child in node.children:
        if child.dep_ == "det" and child.lemma_.lower() in ("этот", "тот", "наш", "мой", "свой"):
            return True

    return False


