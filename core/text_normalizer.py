# -*- coding: utf-8 -*-
"""
FVSC Text Normalizer — preprocessing for chat/social media text before spaCy.

Handles:
  1. Chat slang and abbreviations (deterministic dictionary)
  2. Repeated characters (крутаааа → круто)
  3. Spelling correction (conservative, only clear misspellings)
  4. Basic cleanup (extra spaces, garbage)

Inserted BEFORE spaCy in the pipeline:
    raw text → normalize_text() → spaCy → context_classifier → ...

Design: deterministic, no ML, preserves meaning.
Only fixes FORM, never changes CONTENT (stenographic principle).
"""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# 1. Chat slang dictionary (most common Russian chat abbreviations)
# ---------------------------------------------------------------------------

SLANG_DICT = {
    # Сокращения
    "норм": "нормально",
    "нзч": "не за что",
    "спс": "спасибо",
    "пж": "пожалуйста",
    "плз": "пожалуйста",
    "пжл": "пожалуйста",
    "пжлст": "пожалуйста",
    "оч": "очень",
    "ооч": "очень",
    "чё": "что",
    "чо": "что",
    "шо": "что",
    "щас": "сейчас",
    "ща": "сейчас",
    "скок": "сколько",
    "скока": "сколько",
    "чел": "человек",
    "челик": "человек",
    "комп": "компьютер",
    "ноут": "ноутбук",
    "инфа": "информация",
    "универ": "университет",
    "препод": "преподаватель",
    "контра": "контрольная",
    "лаба": "лабораторная",
    "домашка": "домашняя работа",
    "тыща": "тысяча",
    "чат": "чат",
    "лан": "ладно",
    "ладн": "ладно",
    "канеш": "конечно",
    "канешн": "конечно",
    "конеш": "конечно",
    "наверн": "наверное",
    "наверно": "наверное",
    "прост": "просто",
    "проста": "просто",
    "ваще": "вообще",
    "вааще": "вообще",
    "вобще": "вообще",
    "вобщем": "в общем",
    "впринципе": "в принципе",
    "кста": "кстати",
    "кстат": "кстати",
    "оке": "окей",
    "ок": "окей",
    "ага": "ага",
    "угу": "угу",
    "ахах": "ахах",
    "хах": "хах",
    "кор": "короче",
    "короч": "короче",
    "мб": "может быть",
    "имхо": "по моему мнению",
    "кмк": "как мне кажется",
    "хз": "не знаю",
    "бро": "брат",
    "братан": "брат",
    "сорян": "извини",
    "сори": "извини",
    "сорри": "извини",
    "здрасте": "здравствуйте",
    "здрасьте": "здравствуйте",
    "прив": "привет",
    "привки": "привет",
    "даров": "привет",
    "дарова": "привет",
    "пок": "пока",
    "покеда": "пока",
    "покедова": "пока",
    "досвидос": "до свидания",
    "тк": "так как",
    "тп": "типа",
    "типо": "типа",
    "чтоб": "чтобы",
    "штоб": "чтобы",
    "штобы": "чтобы",
    "што": "что",
    "шта": "что",
    "ктото": "кто-то",
    "чтото": "что-то",
    "гдето": "где-то",
    "когдато": "когда-то",
    "какойто": "какой-то",
    "какието": "какие-то",
    "изза": "из-за",
    "нибудь": "нибудь",
    "ченибудь": "что-нибудь",
    "когданибудь": "когда-нибудь",
    "ктонибудь": "кто-нибудь",
    # Разговорные формы
    "щя": "сейчас",
    "седня": "сегодня",
    "сёдня": "сегодня",
    "тож": "тоже",
    "тожа": "тоже",
    "чёт": "что-то",
    "чет": "что-то",
    "ниче": "ничего",
    "ничё": "ничего",
    "нич": "ничего",
    "нифига": "ничего",
    "пофиг": "всё равно",
    "пофигу": "всё равно",
    "збс": "замечательно",
    "зашибись": "замечательно",
    "блин": "блин",
    "бля": "блин",
    "нах": "зачем",
    "нафиг": "зачем",
    "нахрен": "зачем",
    "пипец": "ужас",
    "капец": "ужас",
    "фигня": "ерунда",
    "херня": "ерунда",
    "прикол": "забавно",
    "прикольно": "забавно",
    "кайф": "удовольствие",
    "кайфово": "прекрасно",
    "топ": "отлично",
    "крч": "короче",
}


# ---------------------------------------------------------------------------
# 2. Repeated character reduction
# ---------------------------------------------------------------------------

def _reduce_repeats(text: str) -> str:
    """Reduce 3+ repeated characters to 1: крутаааа → крута, ооочень → очень.
    Aggressive: valid doubles (ванна, масса) are unaffected since they have
    exactly 2 repeats. Only 3+ triggers the reduction.
    """
    # 3+ same char → 1 char (aggressive but effective for chat)
    return re.sub(r'(.)\1{2,}', r'\1', text)


# ---------------------------------------------------------------------------
# 3. Spelling correction (conservative)
# ---------------------------------------------------------------------------

_spellchecker = None

def _get_spellchecker():
    global _spellchecker
    if _spellchecker is None:
        from spellchecker import SpellChecker
        _spellchecker = SpellChecker(language='ru')
        # Add FVSC-relevant terms that might not be in dictionary
        _spellchecker.word_frequency.load_words([
            'семантика', 'матрица', 'плотность', 'вектор', 'контейнер',
            'полисемия', 'энтропия', 'гипонимия', 'рекурсивный',
        ])
    return _spellchecker


def _correct_word(word: str, spell) -> str:
    """Conservatively correct a single word. Only correct if:
    - Word is not in dictionary
    - Correction exists within edit distance 1
    - Word is long enough (>=5 chars) to avoid false positives
    - Correction is same length ±1 (prevents wild substitutions)
    """
    if len(word) < 5:
        return word
    if word in spell:
        return word
    correction = spell.correction(word)
    if correction and correction != word:
        # Strict: edit distance exactly 1, similar length
        if _edit_distance(word, correction) <= 1 and abs(len(word) - len(correction)) <= 1:
            return correction
    return word


def _edit_distance(a: str, b: str) -> int:
    """Simple Levenshtein distance."""
    if len(a) < len(b):
        return _edit_distance(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
        prev = curr
    return prev[len(b)]


# ---------------------------------------------------------------------------
# 4. Main normalizer
# ---------------------------------------------------------------------------

# Regex patterns
_WHITESPACE_RE = re.compile(r'\s+')
_URL_RE = re.compile(r'https?://\S+|www\.\S+')
_EMOJI_JUNK_RE = re.compile(r'[^\w\s\-.,!?;:()\"\'«»—–…/]', re.UNICODE)


def normalize_text(text: str, fix_slang: bool = True,
                   fix_repeats: bool = True,
                   fix_spelling: bool = False) -> str:
    """Normalize a chat/social media text for better spaCy parsing.

    Args:
        text: Raw input text
        fix_slang: Replace chat abbreviations from dictionary
        fix_repeats: Reduce repeated characters (крутаааа → крута)
        fix_spelling: Apply conservative spell correction

    Returns:
        Normalized text. Original meaning preserved.
    """
    if not text or not text.strip():
        return text

    # Preserve URLs (replace temporarily)
    urls = []
    def _save_url(m):
        urls.append(m.group())
        return f" __URL{len(urls)-1}__ "
    text = _URL_RE.sub(_save_url, text)

    # Reduce repeated characters BEFORE slang lookup
    if fix_repeats:
        text = _reduce_repeats(text)

    # Normalize whitespace
    text = _WHITESPACE_RE.sub(' ', text).strip()

    if fix_slang or fix_spelling:
        words = text.split()
        spell = _get_spellchecker() if fix_spelling else None
        result = []

        for word in words:
            # Skip punctuation-only tokens and URL placeholders
            clean = word.strip('.,!?;:()«»"\'—–…')
            if not clean or clean.startswith('__URL'):
                result.append(word)
                continue

            lower = clean.lower()

            # Step 1: Slang dictionary (exact match)
            if fix_slang and lower in SLANG_DICT:
                replacement = SLANG_DICT[lower]
                # Preserve surrounding punctuation
                prefix = word[:word.lower().index(lower)] if lower in word.lower() else ''
                suffix = word[word.lower().index(lower) + len(lower):] if lower in word.lower() else ''
                result.append(prefix + replacement + suffix)
                continue

            # Step 2: Spelling correction (conservative)
            if fix_spelling and spell and clean.isalpha():
                corrected = _correct_word(lower, spell)
                if corrected != lower:
                    prefix = word[:word.lower().index(lower)] if lower in word.lower() else ''
                    suffix = word[word.lower().index(lower) + len(lower):] if lower in word.lower() else ''
                    result.append(prefix + corrected + suffix)
                    continue

            result.append(word)

        text = ' '.join(result)

    # Restore URLs
    for i, url in enumerate(urls):
        text = text.replace(f'__URL{i}__', url)

    return text


def normalize_texts(texts: list[str], **kwargs) -> list[str]:
    """Normalize a list of texts."""
    return [normalize_text(t, **kwargs) for t in texts]
