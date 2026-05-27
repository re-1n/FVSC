# Следующая сессия — состояние проекта

## Обновлено: 2026-05-28 — SESSION SUMMARY (agnostic core complete)

---

## 🔥 Что сделано за сессию 2026-05-27/28

### 1. Полный переход на агностичный пайплайн
Удалены все spaCy-зависимые модули (10 файлов, ~4000 строк):
`tree_extractor`, `context_classifier`, `live_test`, `interactive_map`,
`visualize_graph`, `antourage_server`, `test_scale`, `test_poc` (старый),
`demo_feedback`, `build_conceptnet_cache`.
Всё сохранено в git до коммита `530bc3d` — восстановимо через `git checkout`.

### 2. Активный стек ядра
- `density_core.py` — матрицы плотности, SemanticSpace, decay, consolidation
- `text_parser_agnostic.py` — текст → semantic_input (regex + co-occurrence)
- `semantic_input.py` + `basis_vectors.py` — явный JSON → ρ
- `thesaurus_prior.py` — bonus-only приор (ConceptNet 95K пар, 0.2s загрузка)
- `feedback.py` — Антураж (FeedbackEngine)
- `text_normalizer.py` + `sentence_segmenter.py` — препроцессинг
- `thesaurus_loader.py` — полные тезаурусы (для будущего)

### 3. Бридж парсер ↔ density_core
`SemanticSpace.load_from_semantic_input(si_dict)` — конвертирует co-occurrence
веса в синтетические Judgments (interpretation_layer=1) и пропускает через
полный пайплайн density_core (decay, consolidation, anomaly, recursive deepen).

### 4. RichJudgment — 6 семантических слоёв
Аддитивно расширен `Judgment` (все новые поля с дефолтами, backward compat):
- **L1 Синтактико-логический** — subject/verb/object/quality/modality/modality_type/negation_scope
- **L2 Фреймовый** — frame_name, semantic_roles, role_intensity (FrameNet/VerbNet)
- **L3 Полисемический** — facet_id, polysemy_degree, sense_vector
- **L4 Телесный** — perceptual_modalities, perceptual_features, emotion_tags
- **L5 Социально-исторический** — context_metadata, historical_variant
- **L6 Рефлексивный** — user_marked_facet, user_confidence (Антураж)

Каналы заполнения L2-L6 ещё не построены — слоты ждут реализации.

### 5. Тесты математических инвариантов: **125/125 PASSED**
`core/test_invariants.py` — 15 групп инвариантов, 125 отдельных проверок:
свойства матрицы (симметрия, PSD), нормировка, асимметрия containment,
границы энтропии, purity, симметрия trace inner product, консолидация,
слои интерпретации, decay, бридж semantic_input, RichJudgment round-trip,
backward compat.
Запуск: `python3 -X utf8 -m core.test_invariants`

### 6. Eval framework — baseline зафиксирован
`core/evaluation.py` — переписан под агностичный пайплайн.
Gold set расширен: полный граф концептов включая глаголы-как-контейнеры
(subj→verb, verb→obj, subj→obj).
**Baseline: Recall=100%, Precision=66%, F1=79%** на 16 предложениях, 46 пар.
24 FP — sibling-пары (силы↔терпения через общий глагол), приемлемый шум.

### 7. Тезаурус-приор (ConceptNet RU)
Bonus-only стратегия: подтверждённые тезаурусом пары усиливаются (×1.2),
неизвестные — не трогаются (penalty убил бы абстрактные пары вроде
свобода→ответственность, которых нет в ConceptNet).
Проверено: `яблоко→фрукт` усилен с 1.0 до 2.0, `яблоко→тоже` остался 1.0.
F1 не изменился под бинарной метрикой — приор меняет ВЕСА, не присутствие.

---

## 📊 Текущие метрики

| Метрика | Значение |
|---|---|
| Тесты математических инвариантов | 125/125 PASS |
| Recall на gold set | 100% |
| Precision на gold set | 66% |
| F1 | 79% |
| Тезаурус-приор пар | 95279 |
| Зависимостей в requirements | numpy, matplotlib, networkx, wtpsplit (no spaCy) |

---

## 🎯 Открытые направления (приоритет сверху вниз)

### 1. Тест на больших объёмах + фиксы парсера
- Прогнать парсер на `eval_sentences_200.txt` (200 предложений)
- Замерить время, типы ошибок, sibling-FP, разреженность
- По результатам приоритизировать фиксы

### 2. Весовая метрика в eval
- Сейчас eval бинарный (пара есть/нет)
- Добавить top-K по весу — покажет эффект тезаурус-приора
- Цель: precision@10, recall@10, MAP

### 3. L4/L5 операционализация
- L4 (телесный) биологически универсален → baseline grounding между картами
- L5 (социальный) культурно вариативен → источник расхождений в compare_maps
- См. memory: `architecture_l4_l5.md`
- Нужен extractor для perceptual_features (NRC lexicon?) и context_metadata

### 4. Каналы заполнения слоёв 2-6
- Сейчас активно используются L1 и часть L3 (через eigendecomposition)
- L2 — frame extractor (T13)
- L4 — perceptual extractor + NRC emotion lexicon
- L5 — context tagger (chat metadata, source attribution)
- L6 — Антураж/FeedbackEngine (уже есть базовая инфраструктура)

### 5. "Книга = факты в связях слов" (направление)
- `read_book(path)` — книга целиком через парсер, автор в `context_metadata`
- Compare_maps покажет влияние прочитанного на персональную карту
- См. session memory

### 6. Sibling-FP фикс
- Эвристика: блокировать прямые пары через "и"/"или" (силы↔терпения)
- Сохранять их как СИБЛИНГИ через общего родителя (verb)
- Ожидаемый эффект: F1 ~85-90%

---

## 🧠 Архитектурные принципы (зафиксировано в Claude memory)

1. **Два фундаментальных вопроса проекта:**
   - Как работает построение смыслов у людей (механизм)
   - Поможет ли это людям понять себя и друг друга (практика)

2. **Каскад семантики, не backprop:**
   - Скелет (тезаурус) → адаптация (co-occurrence) → шлифовка (feedback)
   - Физика памяти (ACT-R): decay, consolidation, archive
   - НЕ обратное распространение ошибки

3. **Ось L4/L5 — биология vs культура:**
   - L4 универсален → связывает людей при сравнении карт
   - L5 культурно вариативен → источник конфликтов смыслов

---

## 📂 Коммиты сессии (10 коммитов, main + agnostic-core merged)

```
3c4d39e feat: thesaurus prior — bonus-only weak prior
109f09a feat: RichJudgment — 6 semantic layers (additive)
0d1e1d5 test: mathematical invariants for density_core (106 checks)
7d2f9f9 merge agnostic-core: text_parser → density_core bridge
8c6ee8e feat: gold set — full concept graph incl. verbs
dc23cd9 feat: agnostic evaluation (T9) + directed co-occurrence
3698f63 chore: remove spaCy-dependent modules — agnostic core only
6591ddd feat: SemanticSpace.load_from_semantic_input() (bridge)
1c88fd2 feat: T14 temporal concept (synthetic discourse, viz)
6479da5 feat: agnostic input layer (semantic_input, basis_vectors, eval)
```

---

## 🚦 Быстрый старт следующей сессии

```bash
# Проверить здоровье ядра
python3 -X utf8 -m core.test_invariants    # должно быть 125/125

# Проверить baseline
python3 -X utf8 -m core.evaluation         # P=66% R=100% F1=79%

# Структура репо
ls core/  # 21 файл: density_core + agnostic stack + eval + annotate tools
```

Старая `Обновлено: 2026-05-16` сессия описывала переход к v0.7.4 (eval set с контекстом, T14 temporal). Эта сессия завершила агностический переход и зафиксировала математический фундамент тестами.
