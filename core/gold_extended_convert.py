# -*- coding: utf-8 -*-
"""
Конвертация gold_extended.py из 2-tuple в 3-tuple формат с meta_type.

Старый формат: (sentence, [judgments])
Новый формат: (sentence, [judgments], meta_type)

meta_type может быть:
  None — обычное суждение
  "generalization" — обобщение предыдущего контекста
  "classification" — классификация явления
  "similarity" — связь через общий атрибут
  "interpretation" — интерпретация
  "reference" — прямая ссылка на предыдущее
"""

import re

# Читаем старый файл
with open('gold_extended.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Находим GOLD_EXTENDED = [ ... ]
match = re.search(r'GOLD_EXTENDED = \[(.*?)\n\]', content, re.DOTALL)
if not match:
    print("ERROR: Could not find GOLD_EXTENDED")
    exit(1)

entries_text = match.group(1)

# Парсим каждый entry
# Формат: (sentence, [judgments]), с комментариями выше
lines = entries_text.split('\n')

new_entries = []
i = 0
while i < len(lines):
    line = lines[i].strip()
    
    # Пропускаем пустые строки и комментарии
    if not line or line.startswith('#'):
        i += 1
        continue
    
    # Ищем начало tuple: (
    if line.startswith('('):
        # Собираем весь tuple (может быть многострочным)
        tuple_lines = [line]
        while not line.rstrip().endswith('),'):
            i += 1
            if i >= len(lines):
                break
            line = lines[i]
            tuple_lines.append(line)
        
        tuple_str = '\n'.join(tuple_lines)
        
        # Конвертируем: (sentence, [judgments]), → (sentence, [judgments], None),
        # Заменяем ), на , None),
        converted = tuple_str.rstrip().rstrip(',')
        if converted.endswith(')'):
            converted = converted[:-1] + ', None),'
        
        new_entries.append(converted)
    
    i += 1

# Собираем новый файл
new_content = content[:match.start(1)]
new_content += '\n    ' + '\n    '.join(new_entries)
new_content += '\n' + content[match.end(1):]

# Пишем новый файл
with open('gold_extended.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"✓ Конвертировано {len(new_entries)} entries")
print("✓ Добавлено meta_type=None для всех")
