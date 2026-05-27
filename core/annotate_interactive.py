# -*- coding: utf-8 -*-
"""
Интерактивный аннотатор для gold_extended.py с поддержкой meta_type.

Использование:
  python annotate_interactive.py [start_idx]

Команды:
  s — пропустить (skip)
  q — выход (quit)
  ? — помощь (help)
"""

import sys
import json
from gold_extended import GOLD_EXTENDED

def show_help():
    print("""
╔════════════════════════════════════════════════════════════════╗
║ АННОТАЦИЯ С META_TYPE                                          ║
╚════════════════════════════════════════════════════════════════╝

ФОРМАТ ВВОДА:
  S→V→O | meta_type

ПРИМЕРЫ:
  я|пропустить|строчка|A | None
  я|назвать|эксперимент|A ; эксперимент|amod|мысленный|A | generalization
  она|иметь|шнурки|A ; я|иметь|шнурки|A | similarity

META_TYPE:
  None — обычное суждение
  generalization — обобщение предыдущего контекста
  classification — классификация явления
  similarity — связь через общий атрибут
  interpretation — интерпретация
  reference — прямая ссылка на предыдущее

КОМАНДЫ:
  s — пропустить (skip)
  q — выход (quit)
  ? — помощь (help)
  
СИНТАКСИС S→V→O:
  subject|verb|object|quality
  
  subject — подлежащее (я, она, это, ...)
  verb — глагол в инфинитиве или cop:это, amod
  object — дополнение
  quality — A (утвердительное) или N (отрицательное)

НЕСКОЛЬКО СУЖДЕНИЙ:
  Разделяй точкой с запятой (;)
  я|видеть|землю|A ; земля|amod|красивый|A
""")

def parse_judgment_line(line):
    """Парсит строку вида 'S|V|O|Q ; S|V|O|Q | meta_type'"""
    if '|' not in line:
        return None, None
    
    # Разделяем на суждения и meta_type
    parts = line.split('|')
    
    # Последняя часть может быть meta_type (если после последнего |)
    # Формат: S|V|O|Q | meta_type
    # или: S|V|O|Q ; S|V|O|Q | meta_type
    
    # Ищем meta_type (после последнего |)
    meta_type = None
    judgments_str = line
    
    # Если есть | в конце (meta_type)
    if line.count('|') % 4 != 0:  # Не кратно 4 → есть meta_type
        last_pipe = line.rfind('|')
        meta_type_candidate = line[last_pipe+1:].strip()
        if meta_type_candidate in [None, 'None', 'generalization', 'classification', 'similarity', 'interpretation', 'reference']:
            meta_type = meta_type_candidate if meta_type_candidate != 'None' else None
            judgments_str = line[:last_pipe]
    
    # Парсим суждения (разделены ;)
    judgments = []
    for judgment_part in judgments_str.split(';'):
        judgment_part = judgment_part.strip()
        if not judgment_part:
            continue
        
        parts = judgment_part.split('|')
        if len(parts) != 4:
            print(f"  ✗ Неверный формат: {judgment_part}")
            return None, None
        
        s, v, o, q = [p.strip() for p in parts]
        if q not in ['A', 'N']:
            print(f"  ✗ Quality должна быть A или N, получено: {q}")
            return None, None
        
        judgments.append((s, v, o, q))
    
    return judgments, meta_type

def annotate_interactive(start_idx=0):
    """Интерактивная разметка"""
    
    annotated_count = 0
    skipped_count = 0
    
    for idx in range(start_idx, len(GOLD_EXTENDED)):
        sentence, judgments, meta_type = GOLD_EXTENDED[idx]
        
        # Пропускаем уже размеченные
        if judgments or meta_type is not None:
            continue
        
        print(f"\n{'='*70}")
        print(f"[{idx+1}/{len(GOLD_EXTENDED)}] {sentence}")
        print(f"{'='*70}")
        
        while True:
            user_input = input("\n> ").strip()
            
            if user_input == 'q':
                print(f"\n✓ Размечено: {annotated_count}, пропущено: {skipped_count}")
                return
            
            if user_input == 's':
                skipped_count += 1
                break
            
            if user_input == '?':
                show_help()
                continue
            
            if not user_input:
                continue
            
            # Парсим ввод
            new_judgments, new_meta_type = parse_judgment_line(user_input)
            
            if new_judgments is None:
                print("  ✗ Ошибка парсинга. Введи ? для помощи")
                continue
            
            # Обновляем entry
            GOLD_EXTENDED[idx] = (sentence, new_judgments, new_meta_type)
            annotated_count += 1
            print(f"  ✓ Сохранено: {new_judgments}, meta={new_meta_type}")
            break
    
    print(f"\n✓ Размечено: {annotated_count}, пропущено: {skipped_count}")

if __name__ == '__main__':
    start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    
    print("""
╔════════════════════════════════════════════════════════════════╗
║ ИНТЕРАКТИВНЫЙ АННОТАТОР GOLD_EXTENDED                         ║
║ Введи ? для помощи                                             ║
╚════════════════════════════════════════════════════════════════╝
""")
    
    annotate_interactive(start_idx)
    
    # Сохраняем обратно в файл
    print("\n💾 Сохраняю в gold_extended.py...")
    
    # Генерируем новый код
    code_lines = [
        "# -*- coding: utf-8 -*-",
        '"""',
        "Расширенный eval set — 210 нормализованных предложений из Telegram-чатов.",
        "",
        "ФОРМАТ: (sentence, [judgments], meta_type)",
        "",
        "PRE-ANNOTATED: auto-extracted judgments для ручной проверки.",
        "Статус: # AUTO = автоматически извлечено, требует ревью",
        "        # EMPTY = автоэкстракция пуста, разметить вручную если есть суждение",
        "        # CONFIRMED = проверено человеком",
        "",
        'Глаголы в инфинитиве (лемме): "требует" → "требовать".',
        'Копулы: "X — это Y" → verb="cop:это".',
        'Прилагательные: "важная свобода" → verb="amod".',
        "Quality: A=утвердительное, N=отрицательное.",
        "",
        "META_TYPE (новое поле):",
        "  None — обычное суждение (нет метаслоя)",
        '  "generalization" — обобщение предыдущего контекста',
        '  "classification" — классификация явления',
        '  "similarity" — связь через общий атрибут',
        '  "interpretation" — интерпретация',
        '  "reference" — прямая ссылка на предыдущее',
        "",
        "Примеры:",
        '  ("я пропустил строчку", [("я", "пропустить", "строчка", "A")], None)',
        '  ("но я бы назвал это мысленными экспериментами", [...], "generalization")',
        '  ("у неё были шнурки разные как и у меня", [...], "similarity")',
        '"""',
        "",
        "GOLD_EXTENDED = [",
    ]
    
    for sentence, judgments, meta_type in GOLD_EXTENDED:
        meta_repr = repr(meta_type)
        code_lines.append(f"    ({repr(sentence)}, {repr(judgments)}, {meta_repr}),")
    
    code_lines.append("]")
    
    with open('gold_extended.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(code_lines))
    
    print("✓ Сохранено!")
