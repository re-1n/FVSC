# -*- coding: utf-8 -*-
"""
Генератор шаблона для разметки.
Создаёт файл с пустыми предложениями для ручного редактирования.
"""

from gold_extended import GOLD_EXTENDED

# Находим пустые
empty_entries = []
for idx, (sentence, judgments, meta_type) in enumerate(GOLD_EXTENDED):
    if not judgments and meta_type is None:
        empty_entries.append((idx, sentence))

print(f"Найдено пустых: {len(empty_entries)}")

# Генерируем шаблон
template = """# ШАБЛОН ДЛЯ РАЗМЕТКИ
# Формат: sentence | S|V|O|Q ; S|V|O|Q | meta_type
# 
# Примеры:
#   и обернуло это в то что я должен был это понять сам | я|понять|это|A | interpretation
#   у неё были шнурки разные как и у меня | она|иметь|шнурки|A ; я|иметь|шнурки|A | similarity
#
# Meta types: None, generalization, classification, similarity, interpretation, reference
# Quality: A (утвердительное), N (отрицательное)
#
# Пропусти строку если нет суждения (оставь пусто после |)

"""

for idx, sentence in empty_entries[:20]:  # Первые 20
    template += f"# [{idx}] {sentence}\n"
    template += f"|\n\n"

with open('annotation_template.txt', 'w', encoding='utf-8') as f:
    f.write(template)

print(f"✓ Создан annotation_template.txt с первыми 20 пустыми предложениями")
