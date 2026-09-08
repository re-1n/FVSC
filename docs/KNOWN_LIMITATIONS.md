# Известные ограничения реализации

Проверенный код: `08e25c53af401736c5858cb3d883ef659a14d87e`, дата проверки: 2026-09-06. **Все пункты ниже открыты.** В этой редакции изменена документация; исправления кода не заявляются выполненными. Идентификаторы A1–A10 — локальные идентификаторы задач, не номера GitHub issues.

## Реестр и критерии закрытия

| ID | Наблюдение | Затронутый путь | Критерий закрытия |
|---|---|---|---|
| A1 | Консолидация сохраняет первое суждение и множит его вес на число активаций; второй источник и другой вес теряются | `Concept.add_component`, `purge_source`, attribution/retrieval | Сохраняются все независимые свидетельства и их веса; удаление одного источника сохраняет остальные; повторный импорт идемпотентен |
| A2 | `containment` может превышать 1; разница направлений зависит от масс. Текущая `graded_hyponymy` симметрична при единичных следах | `density_core`, query/recursive/UI | Типы ассоциации и включения разделены, метрики названы по контракту; границы и семантическая направленность проверяются отдельно |
| A3 | Overlap одинаковых смешанных состояний меньше 1 | `query_similarity`, `compare_maps` | Сходство отделено от чистоты; совпадение состояний корректно отображается; версии представлений совместимы |
| A4 | Энтропия и собственные направления интерпретируются как полисемия и значения без проверки; T14 предлагает ещё более сильные трактовки | Отчёты, визуализация, LLM-контекст, T14 | Показатели имеют точные названия; семантические/психологические гипотезы оцениваются на независимых данных |
| A5 | Направление токенов заменяет тип отношения; отрицание, цитирование и роли не извлекаются как полноценные структуры. Отношение числа пар к частоте бывает >1 | `text_parser_agnostic`, `load_from_semantic_input` | Есть отдельное наблюдение ассоциации, определённый статистический контракт, контрастивная оценка структурного адаптера |
| A6 | `evaluate()` засчитывает связь в любом направлении с сопоставлением по префиксам; матричная асимметрия не определяет зачёт. Тест интерпретации считает маркеры понятий | `core/evaluation.py`, `service/tests/test_interpretation.py` | Проверяется точное отношение/роль/полярность; качество интерпретаций подтверждается свидетельствами и слепыми оценками |
| A7 | Адаптивный top-k, зависящие от состояний веса и обновление на месте не покрыты общим доказательством сходимости | `recursive_deepen` | Для выбранной схемы доказаны условия либо явно ограничена гарантия; проверены порядок обновления и семантическая польза |
| A8 | Контекст, время записи/события и изменение encoder не образуют полного версионированного контракта | `Judgment`, decay, `get_term_vector`, T14 | Состояние воспроизводимо при фиксированных версиях и времени; история записи отделена от времени действия; encoder пересчитывается или переносится явно |
| A9 | Кандидаты retrieval требуют совпавших понятий; после этого применяется матричное ранжирование | `service/retrieval.py` | Полнота кандидатов измерена отдельно от ranking; оценены парафразы, редкие понятия и отсутствие совпавших токенов |
| A10 | Вспомогательный `BasisVectorGenerator` использует процессозависимый `hash`; `partial_trace` не соответствует порядку `np.kron(A,B)` | `basis_vectors.py`, `semantic_input.py` | Общий стабильный encoder; проверен частичный след при разных размерностях. Активный hash в `SemanticSpace` уже стабилен |

Порядок выполнения: [ROADMAP](ROADMAP.md). Формулы и их вывод: [MATHEMATICAL_CONTRACTS](MATHEMATICAL_CONTRACTS.md).

## Воспроизведение ключевых контрпримеров

В корне checkout проверенного коммита, Python 3.12.13 и NumPy 2.3.5. Примеры фиксируют **наблюдаемое неисправленное поведение**, а не желаемые условия успешного теста.

```python
import numpy as np
from core.density_core import (
    Concept, Judgment, SemanticSpace,
    containment, graded_hyponymy, trace_inner_product,
)
from core.semantic_input import SemanticInputParser
from core.text_parser_agnostic import ParseConfig, text_to_semantic_input

A = np.diag([1., 0.])
B = 2 * A
print(containment(A, B), containment(B, A))
# A2: 2.0, 1.0

A = np.diag([.9, .1])
B = np.diag([.6, .4])
print(graded_hyponymy(A, B), graded_hyponymy(B, A))
# A2: 0.7, 0.7

R = np.eye(50) / 50
print(trace_inner_product(R, R))
# A3: приблизительно 0.02 при одинаковых состояниях

c = Concept('x')
for source, weight in [('a.md', .2), ('b.md', .8)]:
    c.add_component(np.array([1., 0.]), weight, Judgment(
        'x', 'r', 'y', source_text=source, timestamp=1e6))
c._recompute_rho(now=1e6)
print([v.judgment.source_text for v in c.components], np.trace(c.rho))
# A1: ['a.md'], 0.4; сумма исходных весов равна 1.0

s = SemanticSpace(dim=16)
for source in ['a.md', 'b.md']:
    s.materialize_judgment(Judgment(
        'alpha', 'rel', 'beta', source_text=source, timestamp=1e6))
s.purge_source('a.md')
print(s.concepts['alpha'].rho)
# A1: None, хотя b.md не удалён

cfg = ParseConfig(min_freq=1, min_token_len=1, coordination_aware=False)
print(text_to_semantic_input('aa bb bb bb', config=cfg)['aa']['contains']['bb'])
# A5: 3.0; это не вероятность наличия bb
for text in ['Я люблю музыку.', 'Я не люблю музыку.']:
    print(text_to_semantic_input(text, config=cfg)['люблю']['contains']['музыку'])
# A5: 1.0 и 1.0; связь не кодирует полярность суждения

p = SemanticInputParser(dim=2)
A = np.diag([.8, .2])
B = np.diag([.1, .3, .6])
print(p.partial_trace(np.kron(A, B), 3))
# A10: diag(0.62, 0.38), ожидается A=diag(0.8, 0.2)
```

Для вспомогательного hash сравнить вывод в двух отдельных процессах:

```bash
PYTHONHASHSEED=1 python -c "from core.basis_vectors import BasisVectorGenerator; print(BasisVectorGenerator(dim=8).get_vector('alpha'))"
PYTHONHASHSEED=2 python -c "from core.basis_vectors import BasisVectorGenerator; print(BasisVectorGenerator(dim=8).get_vector('alpha'))"
```

Этот пример относится к `BasisVectorGenerator`, а не к уже исправленному `SemanticSpace.get_term_vector()` со стабильным hash.

## Что не установлено этими проверками

Проверки показывают конкретные свойства функций и потери происхождения. Они не измеряют качество всех пользовательских сценариев, частоту ошибок на реальных корпусах или сравнительную эффективность других систем. Полный интерфейс Obsidian и живой ответ Ollama в проверке 2026-09-06 не запускались. Численные результаты evaluator и условия запуска: [TEST_RESULTS](../TEST_RESULTS.md).
