"""
Extract ~200 diverse Russian sentences from Telegram chats for judgment extraction evaluation.

Pipeline: raw message → normalize_text() → content filter → diversity sampling → gold_extended.py
"""
import json
import re
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))
from text_normalizer import normalize_text

random.seed(42)

FILES = [
    ('экспорты чатов/result (Davurr and key7).json', 'key7'),
    ('экспорты чатов/result глубокий (Davurr and Sqmos).json', 'sqmos'),
    ('экспорты чатов/result длинный (Davurr and shkshotr).json', 'shkshotr'),
]

DAVURR_ID = 'user897138734'

# Trivial messages to skip
TRIVIAL = {
    'привет', 'прив', 'здарова', 'хай', 'ок', 'окей', 'ладно', 'лан',
    'ахах', 'ахахах', 'ахахахах', 'хаха', 'хахах', 'хахаха', 'лол', 'кек',
    'ну', 'да', 'нет', 'не', 'а', 'ага', 'угу', 'ну да', 'ну ок',
    'спасибо', 'спс', 'пасиб', 'хорош', 'норм', 'круто', 'класс',
    'пока', 'ночи', 'доброе утро', 'добрый день', 'хм', 'ммм',
    'жиза', 'кста', 'кстати', 'бля', 'блин', 'хз', 'хех', 'хехе',
    'хехех', 'эм', 'ээ', 'мм', 'ммм', 'оо', 'ооо', 'аа', 'ааа',
    'найс', 'го', 'давай', 'ясно', 'понятно', 'понял', 'поняла',
}

# Verb-like endings (heuristic for Russian)
VERB_PATTERNS = re.compile(
    r'(?:'
    r'\w+(?:ть|ти|чь)'  # infinitives
    r'|\w+(?:ет|ёт|ит|ат|ят|ут|ют|ешь|ёшь|ишь|ем|ём|им|ете|ёте|ите)'  # present
    r'|\w+(?:ал|ала|ало|али|ил|ила|ило|или|ел|ела|ело|ели|ул|ула|уло|ули|ял|яла|яло|яли)'  # past
    r'|\w+(?:ает|яет|ует|ёет|оет|ивает|ывает)'  # present detailed
    r'|\w+(?:ться|тся)'  # reflexive
    r'|\w+(?:нет|дет|зет|бет|мет|пет|вет|жет|шет|щет|чет)'  # more present
    r'|(?:есть|был|была|было|были|стал|стала|стало|стали|может|могут|должен|должна|должны|хочет|хотят|нужно|надо|можно|нельзя|стоит)'
    r')', re.IGNORECASE
)

# Russian letter check
RUSSIAN_RE = re.compile(r'[а-яёА-ЯЁ]')

# Categories for diversity
CATEGORY_PATTERNS = {
    'negation': re.compile(r'\bне\b|\bни\b|\bнет\b|\bнельзя\b|\bникогда\b|\bничего\b|\bникак\b', re.I),
    'modal': re.compile(r'\bдолж\w+\b|\bмож\w+\b|\bхоч\w+\b|\bнужно\b|\bнадо\b|\bможно\b|\bнельзя\b|\bстоит\b|\bследует\b', re.I),
    'copular': re.compile(r'\bэто\b|\bявляется\b|\bесть\b|\b—\b|\b-\s', re.I),
    'conditional': re.compile(r'\bесли\b|\bкогда\b|\bпока\b|\bраз\b.*\bто\b', re.I),
    'coordination': re.compile(r'\bи\b|\bили\b|\bа\b|\bно\b|\bлибо\b', re.I),
    'passive': re.compile(r'\w+(?:ется|ются|ен|ена|ено|ены|ан|ана|ано|аны)\b', re.I),
    'reported': re.compile(r'\bговорит\b|\bсказал\b|\bсчитает\b|\bдумает\b|\bпо-моему\b|\bмне кажется\b|\bтипа\b', re.I),
    'generic': re.compile(r'\bвсегда\b|\bникогда\b|\bобычно\b|\bвообще\b|\bв принципе\b|\bлюди\b|\bчеловек\b|\bмир\b|\bжизнь\b', re.I),
    'simple_svo': re.compile(r'^[А-ЯЁа-яё]+ \w+ \w+', re.I),  # fallback
}


def extract_text(text_field):
    """Extract plain text from message text field (can be str or list)."""
    if isinstance(text_field, str):
        return text_field
    if isinstance(text_field, list):
        parts = []
        for item in text_field:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get('text', ''))
        return ''.join(parts)
    return ''


def is_url_only(text):
    """Check if text is just a URL."""
    stripped = text.strip()
    return bool(re.match(r'^https?://\S+$', stripped))


def split_sentences(text):
    """Split message into individual sentences."""
    # Split on newlines first, then on sentence-ending punctuation
    lines = text.split('\n')
    sentences = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Split on . ! but keep ? for filtering later
        parts = re.split(r'(?<=[.!])\s+', line)
        sentences.extend(parts)
    return sentences


def qualifies(sentence):
    """Check if a sentence is a good candidate."""
    s = sentence.strip()

    # Must have Russian chars
    if not RUSSIAN_RE.search(s):
        return False

    # Min 4 words
    words = s.split()
    if len(words) < 4:
        return False

    # Max length - skip walls of text
    if len(words) > 60:
        return False

    # Skip URL-only
    if is_url_only(s):
        return False

    # Skip if mostly non-Russian (e.g., English messages)
    russian_chars = len(RUSSIAN_RE.findall(s))
    alpha_chars = len(re.findall(r'[a-zA-Zа-яёА-ЯЁ]', s))
    if alpha_chars > 0 and russian_chars / alpha_chars < 0.5:
        return False

    # Skip trivial
    normalized = re.sub(r'[^\w\s]', '', s.lower()).strip()
    if normalized in TRIVIAL:
        return False

    # Must contain a verb (heuristic)
    if not VERB_PATTERNS.search(s):
        return False

    # Skip pure questions (only ? at end, but allow some)
    if s.endswith('?') and not any(kw in s.lower() for kw in ['потому', 'значит', 'получается', 'считаю', 'думаю']):
        # Allow ~20% questions through
        if random.random() > 0.2:
            return False

    # Skip "я пошёл спать" type trivial episodic
    trivial_episodic = [
        r'^я пош[ёе]л\b', r'^я сплю\b', r'^я ем\b', r'^я дома\b',
        r'^я на работе\b', r'^я в школе\b', r'^пошёл спать\b',
        r'^спокойной ночи\b', r'^доброе утро\b',
    ]
    for pat in trivial_episodic:
        if re.search(pat, s.lower()):
            return False

    # Content filter: profanity, sexual content, slurs, graphic violence
    # Covers ё/е variants via [её] groups
    CONTENT_FILTER = re.compile(
        # --- Мат (все корни и производные) ---
        r'[её]б(?:а[тлнш]|у[чтн]|[её]т|ну[тл]|ли|ло|ла|ись|[её]ш|ан|ён|[её]н)'
        r'|за[её]б|про[её]б|от[её]б|вы[её]б|у[её]б|на[её]б|об[её]б|пере[её]б'
        r'|[её]бать|[её]бёт|[её]бут|[её]бись|[её]бал|[её]бло|[её]бла'
        r'|пизд|хуй|хуя|хуе|хую|хуёв|бляд|блять|сук[аи]\b|сучк|сучар'
        r'|муда[кч]|пидор|пидар|пидр'
        # --- Сексуальное ---
        r'|сперм|оргазм|порн|минет|фелляц|куннил|анал(?:ьн)|пенис|вагин'
        r'|дроч|подроч|надроч|задроч|передроч'
        r'|трахал|трахну|трахать|сосал[аи]|сосут'
        r'|секс(?:ом|а|у|е|уальн)|изнасил|педофил'
        # --- Телесное вульгарное ---
        r'|срать|ссать|посра|посре|поссы|насра|обосра|засра'
        r'|говн[оауе]|дерьм[оауе]|залуп|жоп[аеуыо]'
        # --- Этнические/расовые оскорбления ---
        r'|чурк[аиео]|чурбан|нигер|нигг|хач[аиео]?\b|жид[аыов]?\b'
        r'|хохол|хохл|москал|кацап|узкоглаз'
        # --- Шлюхи/проституция ---
        r'|шлюх|шалав|проститу',
        re.I
    )
    if CONTENT_FILTER.search(s):
        return False

    # Fragment filter: skip incomplete sentences
    # Sentence must not end with a dangling conjunction/preposition/particle
    stripped = s.rstrip('.!?,;: ')
    last_word = stripped.split()[-1].lower() if stripped.split() else ''
    DANGLING = {'и', 'а', 'но', 'или', 'что', 'как', 'в', 'на', 'с', 'к', 'у',
                'по', 'из', 'за', 'от', 'до', 'при', 'для', 'о', 'об', 'ни', 'не',
                'бы', 'же', 'то', 'ведь', 'вот', 'так', 'ну', 'м', 'ещ', 'еще'}
    if last_word in DANGLING or len(last_word) == 1:
        return False

    return True


def categorize(sentence):
    """Assign categories to a sentence for diversity tracking."""
    cats = []
    for cat, pat in CATEGORY_PATTERNS.items():
        if pat.search(sentence):
            cats.append(cat)
    if not cats:
        cats = ['simple_svo']
    return cats


def main():
    all_candidates = {}  # label -> list of (sentence, categories)

    for fname, label in FILES:
        with open(fname, 'r', encoding='utf-8') as f:
            data = json.load(f)

        candidates = []
        seen = set()

        for msg in data['messages']:
            if msg.get('from_id') != DAVURR_ID:
                continue
            if msg.get('type') != 'message':
                continue

            text = extract_text(msg.get('text', ''))
            if not text:
                continue

            sentences = split_sentences(text)
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                # Normalize before evaluation
                sent = normalize_text(sent, fix_slang=True, fix_repeats=True, fix_spelling=False)
                # Deduplicate
                norm = sent.lower().strip()
                if norm in seen:
                    continue
                seen.add(norm)

                if qualifies(sent):
                    cats = categorize(sent)
                    candidates.append((sent, cats))

        all_candidates[label] = candidates
        print(f"[{label}] Found {len(candidates)} candidate sentences")

    # Now select ~70 from each, prioritizing diversity
    TARGET_PER_CHAT = 70
    selected = []

    for label, candidates in all_candidates.items():
        if not candidates:
            continue

        # Group by primary category
        by_cat = {}
        for sent, cats in candidates:
            primary = cats[0]
            by_cat.setdefault(primary, []).append(sent)

        print(f"\n[{label}] Category distribution:")
        for cat, sents in sorted(by_cat.items(), key=lambda x: -len(x[1])):
            print(f"  {cat}: {len(sents)}")

        # Select proportionally from each category, but ensure at least a few from each
        chosen = []
        cat_names = list(by_cat.keys())

        # First pass: at least 3 from each category (or all if fewer)
        for cat in cat_names:
            pool = by_cat[cat]
            random.shuffle(pool)
            n = min(3, len(pool))
            chosen.extend([(s, label, cat) for s in pool[:n]])
            by_cat[cat] = pool[n:]

        # Second pass: fill remaining quota proportionally
        remaining = TARGET_PER_CHAT - len(chosen)
        if remaining > 0:
            # Pool all remaining
            all_remaining = []
            for cat in cat_names:
                all_remaining.extend([(s, label, cat) for s in by_cat[cat]])
            random.shuffle(all_remaining)
            chosen.extend(all_remaining[:remaining])

        # Trim to target
        chosen = chosen[:TARGET_PER_CHAT]
        selected.extend(chosen)

    # Write to file
    random.shuffle(selected)

    out_path = 'eval_sentences_200.txt'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"SELECTED {len(selected)} SENTENCES FOR EVALUATION\n")
        f.write(f"{'='*80}\n\n")
        for i, (sent, label, cat) in enumerate(selected, 1):
            f.write(f"{i}. [{label}] {sent}\n")

        f.write(f"\n{'='*80}\n")
        f.write("STATS:\n")
        from collections import Counter
        label_counts = Counter(label for _, label, _ in selected)
        cat_counts = Counter(cat for _, _, cat in selected)
        f.write(f"  By source: {dict(label_counts)}\n")
        f.write(f"  By category: {dict(cat_counts)}\n")

    print(f"Written {len(selected)} sentences to {out_path}")

    # --- Generate gold_extended.py with pre-annotations ---
    print("\nGenerating gold_extended.py with pre-annotations...")
    import spacy
    from tree_extractor import extract_judgments_recursive

    nlp = spacy.load("ru_core_news_md")

    # Group by source label
    by_label = {}
    for sent, label, cat in selected:
        by_label.setdefault(label, []).append(sent)

    gold_path = os.path.join('core', 'gold_extended.py')
    with open(gold_path, 'w', encoding='utf-8') as f:
        f.write('# -*- coding: utf-8 -*-\n')
        f.write('"""\n')
        f.write(f'Расширенный eval set — {len(selected)} нормализованных предложений из Telegram-чатов.\n')
        f.write('\n')
        f.write('PRE-ANNOTATED: auto-extracted judgments для ручной проверки.\n')
        f.write('Статус: # AUTO = автоматически извлечено, требует ревью\n')
        f.write('        # EMPTY = автоэкстракция пуста, разметить вручную если есть суждение\n')
        f.write('        # CONFIRMED = проверено человеком\n')
        f.write('\n')
        f.write('Глаголы в инфинитиве (лемме): "требует" → "требовать".\n')
        f.write('Копулы: "X — это Y" → verb="cop:это".\n')
        f.write('Прилагательные: "важная свобода" → verb="amod".\n')
        f.write('Quality: A=утвердительное, N=отрицательное.\n')
        f.write('"""\n\n')
        f.write('GOLD_EXTENDED = [\n')

        for label in ['shkshotr', 'sqmos', 'key7']:
            sents = by_label.get(label, [])
            if not sents:
                continue
            f.write(f'    # --- [{label}] ---\n\n')
            for sent in sents:
                extracted = extract_judgments_recursive(nlp, [sent], normalize=False)
                tuples = []
                for j in extracted:
                    q = 'A' if j.quality != 'NEGATIVE' else 'N'
                    s_esc = j.subject.replace('"', '\\"')
                    v_esc = j.verb.replace('"', '\\"')
                    o_esc = j.object.replace('"', '\\"')
                    tuples.append(f'("{s_esc}", "{v_esc}", "{o_esc}", "{q}")')

                sent_esc = sent.replace('\\', '\\\\').replace('"', '\\"')
                if tuples:
                    joined = ',\n      '.join(tuples)
                    f.write(f'    # AUTO — review needed\n')
                    f.write(f'    ("{sent_esc}",\n')
                    f.write(f'     [{joined}]),\n\n')
                else:
                    f.write(f'    # EMPTY — annotate manually if judgment exists\n')
                    f.write(f'    ("{sent_esc}",\n')
                    f.write(f'     []),\n\n')

        f.write(']\n')

    print(f"Written {len(selected)} pre-annotated sentences to {gold_path}")


if __name__ == '__main__':
    main()
