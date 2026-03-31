# -*- coding: utf-8 -*-
"""
T9: Evaluation framework — precision/recall of judgment extraction.

Gold-standard sentences with manually annotated S→V→O judgments.
Compares extracted judgments against gold, reports precision/recall/F1.

Usage: python -X utf8 evaluation.py
"""

import sys
import os
import time
from dataclasses import dataclass, field

try:
    from .density_core import Judgment
    from .tree_extractor import extract_judgments_recursive
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from density_core import Judgment
    from tree_extractor import extract_judgments_recursive


# ---------------------------------------------------------------------------
# Gold standard: (sentence, [expected judgments])
# Each expected judgment: (subject, verb, object, quality)
# quality: "A" = AFFIRMATIVE, "N" = NEGATIVE
# ---------------------------------------------------------------------------

GOLD_STANDARD = [
    # === L0: Direct S→V→O ===
    ("Свобода требует ответственности.",
     [("свобода", "требовать", "ответственность", "A")]),

    ("Любовь не требует жертв.",
     [("любовь", "требовать", "жертва", "N")]),

    ("Человек должен быть свободен.",
     [("человек", "быть", "свободен", "A")]),

    ("Свобода и ответственность требуют мужества.",
     [("свобода", "требовать", "мужество", "A"),
      ("ответственность", "требовать", "мужество", "A")]),

    ("Выбор порождает ответственность.",
     [("выбор", "порождать", "ответственность", "A")]),

    ("Честность укрепляет доверие.",
     [("честность", "укреплять", "доверие", "A")]),

    ("Ложь разрушает отношения.",
     [("ложь", "разрушать", "отношение", "A")]),

    ("Страх ограничивает свободу.",
     [("страх", "ограничивать", "свобода", "A")]),

    ("Одиночество даёт время для размышлений.",
     [("одиночество", "давать", "время", "A")]),

    ("Терпение приносит результаты.",
     [("терпение", "приносить", "результат", "A")]),

    # === Negation ===
    ("Свобода не означает вседозволенность.",
     [("свобода", "означать", "вседозволенность", "N")]),

    ("Сила не подразумевает агрессию.",
     [("сила", "подразумевать", "агрессия", "N")]),

    # === Modal envelopes ===
    ("Я думаю, что свобода важна.",
     [("свобода", "важна", "важна", "A")]),  # inner clause extracted with EPISTEMIC

    ("Я верю, что добро побеждает зло.",
     [("добро", "побеждать", "зло", "A")]),

    # === Copula ===
    ("Свобода — это ответственность.",
     [("свобода", "cop:это", "ответственность", "A")]),

    ("Любовь — не слабость.",
     [("любовь", "cop:это", "слабость", "N")]),

    ("Доверие — основа отношений.",
     [("доверие", "cop:это", "основа", "A")]),

    # === Conditionals ===
    ("Если человек свободен, он ответственен.",
     []),  # both conditional halves extracted with reduced modality

    # === Coordination (multiple objects) ===
    ("Мужество требует силы и терпения.",
     [("мужество", "требовать", "сила", "A"),
      ("мужество", "требовать", "терпение", "A")]),

    ("Свобода включает выбор и ответственность.",
     [("свобода", "включать", "выбор", "A"),
      ("свобода", "включать", "ответственность", "A")]),

    # === Intensity variations ===
    ("Ненависть разрушает душу.",
     [("ненависть", "разрушать", "душа", "A")]),

    ("Надежда помогает выстоять.",
     [("надежда", "помогать", "выстоять", "A")]),

    # === Prepositional/adjectival ===
    ("Важная свобода.",
     [("свобода", "amod", "важный", "A")]),

    # === Generic "ты" ===
    ("Когда ты свободен, ты ответственен.",
     []),  # generic ты in conditional — tricky

    # === Self ===
    ("Я свободен.",
     []),  # self-characterization, routed to [self]

    ("Я люблю свободу.",
     []),  # self-relation

    # === Quote ===
    ("Кант говорил, что свобода требует морали.",
     [("свобода", "требовать", "мораль", "A")]),  # citation, reduced weight

    # === Habitual ===
    ("Обычно свобода порождает ответственность.",
     [("свобода", "порождать", "ответственность", "A")]),

    # === Episodic (should be filtered) ===
    ("Вчера этот человек пришёл.",
     []),  # REFERENTIAL + EPISODIC → no judgment expected

    ("Один знакомый сказал мне это.",
     []),  # REFERENTIAL → no judgment

    # === Complex ===
    ("Ответственность перед другими укрепляет характер.",
     [("ответственность", "укреплять", "характер", "A")]),

    ("Добро и зло существуют одновременно.",
     [("добро", "существовать", "одновременно", "A"),
      ("зло", "существовать", "одновременно", "A")]),

    # === Quantifiers ===
    ("Все люди стремятся к свободе.",
     [("люди", "стремиться", "свобода", "A")]),  # universal, weight boosted

    ("Некоторые люди боятся свободы.",
     [("люди", "бояться", "свобода", "A")]),  # existential, weight reduced

    # === Double negation ===
    ("Нельзя не признать важность свободы.",
     [("важность", "признать", "свобода", "A")]),  # double neg → AFFIRM (tricky)

    # === Passive ===
    ("Свобода ценится обществом.",
     [("общество", "ценить", "свобода", "A")]),  # passive inversion

    # === More direct S→V→O ===
    ("Мудрость приходит с опытом.",
     [("мудрость", "приходить", "опыт", "A")]),

    ("Знание освобождает человека.",
     [("знание", "освобождать", "человек", "A")]),

    ("Творчество требует дисциплины.",
     [("творчество", "требовать", "дисциплина", "A")]),

    ("Дружба основана на доверии.",
     [("дружба", "основать", "доверие", "A")]),

    ("Гордость мешает пониманию.",
     [("гордость", "мешать", "понимание", "A")]),

    ("Жадность порождает конфликты.",
     [("жадность", "порождать", "конфликт", "A")]),

    ("Смелость вдохновляет окружающих.",
     [("смелость", "вдохновлять", "окружающие", "A")]),

    ("Лень убивает потенциал.",
     [("лень", "убивать", "потенциал", "A")]),

    ("Искренность привлекает людей.",
     [("искренность", "привлекать", "люди", "A")]),

    ("Зависть отравляет жизнь.",
     [("зависть", "отравлять", "жизнь", "A")]),

    ("Благодарность наполняет смыслом.",
     [("благодарность", "наполнять", "смысл", "A")]),

    ("Сострадание объединяет людей.",
     [("сострадание", "объединять", "люди", "A")]),

    ("Упрямство мешает развитию.",
     [("упрямство", "мешать", "развитие", "A")]),

    ("Вера поддерживает в трудные времена.",
     [("вера", "поддерживать", "время", "A")]),

    ("Справедливость требует беспристрастности.",
     [("справедливость", "требовать", "беспристрастность", "A")]),
]


def normalize_judgment(s, v, o, q):
    """Normalize for comparison: lowercase, strip."""
    return (s.lower().strip(), v.lower().strip(), o.lower().strip(), q)


def judgment_to_tuple(j: Judgment) -> tuple:
    """Convert extracted Judgment to comparable tuple."""
    q = "A" if j.quality == "AFFIRMATIVE" else "N"
    return normalize_judgment(j.subject, j.verb, j.object, q)


def match_judgment(extracted: tuple, gold: tuple) -> bool:
    """Fuzzy match: subject and object must match, verb can be partial."""
    es, ev, eo, eq = extracted
    gs, gv, go, gq = gold

    # Quality must match
    if eq != gq:
        return False

    # Subject must match (allow lemma variations)
    if es != gs and not es.startswith(gs[:4]) and not gs.startswith(es[:4]):
        return False

    # Object must match
    if eo != go and not eo.startswith(go[:4]) and not go.startswith(eo[:4]):
        return False

    # Verb: exact or partial match (allow "cop:это" ≈ "cop:это")
    if ev == gv:
        return True
    if ev.startswith(gv[:4]) or gv.startswith(ev[:4]):
        return True

    return False


def evaluate(nlp, gold_set=None) -> dict:
    """Run evaluation on gold standard. Returns metrics dict."""
    if gold_set is None:
        gold_set = GOLD_STANDARD
    total_gold = 0
    total_extracted = 0
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    details = []

    for sentence, expected in gold_set:
        # Extract
        extracted = extract_judgments_recursive(nlp, [sentence], normalize=False)
        extracted_tuples = [judgment_to_tuple(j) for j in extracted]

        # Normalize gold
        gold_tuples = [normalize_judgment(s, v, o, q) for s, v, o, q in expected]

        total_gold += len(gold_tuples)
        total_extracted += len(extracted_tuples)

        # Match: greedy bipartite
        matched_gold = set()
        matched_ext = set()

        for i, gt in enumerate(gold_tuples):
            for j, et in enumerate(extracted_tuples):
                if j not in matched_ext and match_judgment(et, gt):
                    matched_gold.add(i)
                    matched_ext.add(j)
                    true_positives += 1
                    break

        fn = len(gold_tuples) - len(matched_gold)
        fp = len(extracted_tuples) - len(matched_ext)
        false_negatives += fn
        false_positives += fp

        status = "OK" if fn == 0 and fp == 0 else "MISS" if fn > 0 else "EXTRA"
        details.append({
            "sentence": sentence,
            "expected": gold_tuples,
            "extracted": extracted_tuples,
            "tp": len(matched_gold),
            "fp": fp,
            "fn": fn,
            "status": status,
        })

    precision = true_positives / max(1, total_extracted)
    recall = true_positives / max(1, total_gold)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)

    return {
        "total_sentences": len(GOLD_STANDARD),
        "total_gold": total_gold,
        "total_extracted": total_extracted,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "details": details,
    }


def main():
    import spacy

    # Check for --extended flag
    extended = "--extended" in sys.argv or "-e" in sys.argv

    print("=" * 70)
    print("T9: Evaluation — Judgment Extraction Precision/Recall")
    print("=" * 70)

    if extended:
        try:
            from gold_extended import GOLD_EXTENDED
        except ImportError:
            from .gold_extended import GOLD_EXTENDED
        gold_set = GOLD_STANDARD + GOLD_EXTENDED
        print(f"\nExtended gold standard: {len(GOLD_STANDARD)} base + {len(GOLD_EXTENDED)} extended = {len(gold_set)} sentences")
    else:
        gold_set = GOLD_STANDARD
        print(f"\nGold standard: {len(gold_set)} sentences")

    print("Loading spaCy ru_core_news_md...")
    t0 = time.time()
    nlp = spacy.load("ru_core_news_md")
    print(f"  Loaded in {time.time()-t0:.1f}s")

    print("\nEvaluating...\n")
    result = evaluate(nlp, gold_set)

    # Print details
    for d in result["details"]:
        marker = {"OK": "+", "MISS": "-", "EXTRA": "~"}[d["status"]]
        print(f"  [{marker}] \"{d['sentence'][:60]}\"")
        if d["status"] != "OK":
            if d["fn"] > 0:
                missed = [g for i, g in enumerate(d["expected"])
                          if not any(match_judgment(e, g) for e in d["extracted"])]
                for m in missed:
                    print(f"       MISSED: {m[0]} → {m[1]} → {m[2]} [{m[3]}]")
            if d["fp"] > 0:
                extra = [e for i, e in enumerate(d["extracted"])
                         if not any(match_judgment(e, g) for g in d["expected"])]
                for e in extra:
                    print(f"       EXTRA:  {e[0]} → {e[1]} → {e[2]} [{e[3]}]")

    # Summary
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    print(f"  Sentences:       {result['total_sentences']}")
    print(f"  Gold judgments:   {result['total_gold']}")
    print(f"  Extracted:        {result['total_extracted']}")
    print(f"  True positives:   {result['true_positives']}")
    print(f"  False positives:  {result['false_positives']}")
    print(f"  False negatives:  {result['false_negatives']}")
    print(f"  Precision:        {result['precision']:.1%}")
    print(f"  Recall:           {result['recall']:.1%}")
    print(f"  F1:               {result['f1']:.1%}")

    return result


if __name__ == "__main__":
    main()
