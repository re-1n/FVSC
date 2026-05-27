# -*- coding: utf-8 -*-
"""
Annotation tool для gold_extended_davur_key7.py
Создаёт интерактивный интерфейс для разметки с контекстом.
"""

import sys
from gold_extended_davur_key7 import GOLD_EXTENDED

def format_entry(idx, entry):
    """Форматирует entry для показа"""
    sentence, context, judgments, meta_type = entry
    
    output = f"\n{'='*80}\n"
    output += f"[{idx+1}/50] ENTRY #{idx}\n"
    output += f"{'='*80}\n\n"
    
    if context:
        output += "📌 CONTEXT (previous messages):\n"
        for i, ctx_msg in enumerate(context, 1):
            # Обрезаем длинные сообщения
            ctx_preview = ctx_msg[:100] + "..." if len(ctx_msg) > 100 else ctx_msg
            output += f"   [{i}] {ctx_preview}\n"
        output += "\n"
    
    output += "📝 SENTENCE (to annotate):\n"
    output += f"   {sentence}\n\n"
    
    output += "CURRENT ANNOTATION:\n"
    if judgments:
        output += f"   Judgments: {judgments}\n"
    else:
        output += f"   Judgments: (empty)\n"
    output += f"   Meta type: {meta_type}\n\n"
    
    return output

def show_help():
    print("""
╔════════════════════════════════════════════════════════════════╗
║ ANNOTATION FORMAT                                              ║
╚════════════════════════════════════════════════════════════════╝

INPUT FORMAT:
  S|V|O|Q | meta_type

EXAMPLES:
  я|пропустить|строчка|A | None
  я|назвать|эксперимент|A ; эксперимент|amod|мысленный|A | generalization
  она|иметь|шнурки|A ; я|иметь|шнурки|A | similarity

MULTIPLE JUDGMENTS:
  Separate with semicolon (;)
  я|видеть|землю|A ; земля|amod|красивый|A

META_TYPES:
  None — ordinary judgment
  generalization — generalizes previous context
  classification — classifies phenomenon
  similarity — connection through shared attribute
  interpretation — interpretation
  reference — direct reference to previous

QUALITY:
  A — affirmative
  N — negative

COMMANDS:
  s — skip
  q — quit
  ? — help
  n — next (save and continue)
""")

def parse_annotation(line):
    """Парсит строку аннотации"""
    if not line.strip():
        return None, None
    
    # Разделяем на суждения и meta_type
    parts = line.split('|')
    
    # Ищем meta_type (последняя часть после последнего |)
    meta_type = None
    judgments_str = line
    
    # Если количество частей не кратно 4 → есть meta_type
    if len(parts) % 4 != 0:
        last_pipe = line.rfind('|')
        meta_type_candidate = line[last_pipe+1:].strip()
        if meta_type_candidate in ['None', 'generalization', 'classification', 'similarity', 'interpretation', 'reference']:
            meta_type = meta_type_candidate if meta_type_candidate != 'None' else None
            judgments_str = line[:last_pipe]
    
    # Парсим суждения
    judgments = []
    for judgment_part in judgments_str.split(';'):
        judgment_part = judgment_part.strip()
        if not judgment_part:
            continue
        
        parts = judgment_part.split('|')
        if len(parts) != 4:
            print(f"  ✗ Invalid format: {judgment_part}")
            return None, None
        
        s, v, o, q = [p.strip() for p in parts]
        if q not in ['A', 'N']:
            print(f"  ✗ Quality must be A or N, got: {q}")
            return None, None
        
        judgments.append((s, v, o, q))
    
    return judgments, meta_type

def annotate_interactive(start_idx=0, limit=50):
    """Интерактивная разметка"""
    
    # Находим пустые entries
    empty_indices = []
    for idx, entry in enumerate(GOLD_EXTENDED):
        sentence, context, judgments, meta_type = entry
        if not judgments and meta_type is None:
            empty_indices.append(idx)
            if len(empty_indices) >= limit:
                break
    
    print(f"\n✓ Found {len(empty_indices)} empty entries")
    print(f"✓ Will annotate first {min(limit, len(empty_indices))}")
    
    annotated_count = 0
    skipped_count = 0
    
    for pos, idx in enumerate(empty_indices[:limit]):
        entry = GOLD_EXTENDED[idx]
        
        print(format_entry(pos, entry))
        
        while True:
            user_input = input("> ").strip()
            
            if user_input == 'q':
                print(f"\n✓ Annotated: {annotated_count}, Skipped: {skipped_count}")
                return annotated_count, skipped_count
            
            if user_input == 's':
                skipped_count += 1
                break
            
            if user_input == '?':
                show_help()
                continue
            
            if not user_input:
                continue
            
            # Парсим ввод
            new_judgments, new_meta_type = parse_annotation(user_input)
            
            if new_judgments is None and user_input != '':
                print("  ✗ Parse error. Type ? for help")
                continue
            
            # Обновляем entry
            sentence, context, _, _ = entry
            GOLD_EXTENDED[idx] = (sentence, context, new_judgments, new_meta_type)
            annotated_count += 1
            print(f"  ✓ Saved: {new_judgments}, meta={new_meta_type}")
            break
    
    print(f"\n✓ Annotated: {annotated_count}, Skipped: {skipped_count}")
    return annotated_count, skipped_count

if __name__ == '__main__':
    print("""
╔════════════════════════════════════════════════════════════════╗
║ GOLD_EXTENDED ANNOTATION TOOL                                  ║
║ Type ? for help                                                ║
╚════════════════════════════════════════════════════════════════╝
""")
    
    annotated, skipped = annotate_interactive(limit=50)
    
    # Сохраняем обратно
    print("\n💾 Saving to gold_extended_davur_key7.py...")
    
    code_lines = [
        "# -*- coding: utf-8 -*-",
        '"""',
        "Расширенный eval set из Davur+Key7 чатов с полным контекстом.",
        "",
        "ФОРМАТ: (sentence, context, judgments, meta_type)",
        '"""',
        "",
        "GOLD_EXTENDED = [",
    ]
    
    for sentence, context, judgments, meta_type in GOLD_EXTENDED:
        code_lines.append(f"    ({repr(sentence)}, {repr(context)}, {repr(judgments)}, {repr(meta_type)}),")
    
    code_lines.append("]")
    
    with open('gold_extended_davur_key7.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(code_lines))
    
    print("✓ Saved!")
