# FVSC — Лог изменений и метрики

Данные: тестовый Telegram-диалог, 2000 сообщений, spaCy ru_core_news_md, dim=100, min_components=3, alpha=0.7, K=3.

---

## v0.1 — Плоский экстрактор (baseline)

**Файл:** `live_test.py :: extract_judgments()`
**Метод:** Итерация по токенам → найти VERB → взять nsubj/obj из прямых потомков.

| Метрика | Значение |
|---|---|
| Суждений | 1026 |
| Концептов | 1001 |
| Отрицание | Бинарный флаг на глаголе (не учитывает скоуп) |
| Модальность | Всегда 1.0 (не извлекается) |
| Кванторы | Не обрабатываются |
| Условные | Не связываются |
| "Человек" как субъект | 44 (хаб — всё сливается) |
| "Ты" | Пропускается целиком (в SKIP_PRONOUNS) |

**Проблемы:** "Я не думаю что X" → X записывается как AFFIRM. Модальность игнорируется. "Человек" = свалка. Координация теряет второй элемент.

---

## v0.2 — Рекурсивный экстрактор

**Файл:** `tree_extractor.py :: extract_judgments_recursive()`
**Метод:** Рекурсивный обход дерева зависимостей от корня с передачей `ExtractionContext` (negation, modality, quantifiers, conditionals).

| Метрика | v0.1 | v0.2 | Δ |
|---|---|---|---|
| Суждений | 1026 | 1013 | −13 |
| Отрицание | Плоское | Скоуп по дереву + neg-raising | Корректное |
| Модальность | 1.0 always | Из оболочек (0.3–1.0) | Дифференцированная |
| Кванторы | Нет | ×1.2–1.4 / ×0.5–0.7 | Вес зависит от квантора |
| Условные | Нет | condition_id связывает if→then | Пары связаны |
| Координация | Только первый элемент | Декартово произведение | Полная |

**Добавлено:** `QUASI_GENERIC_NOUNS` + `_is_referential_usage()` — "этот человек" пропускается.

| "Человек" | v0.1 | v0.2 |
|---|---|---|
| Как субъект | 44 | 44 (фильтр по детерминерам: −0, мало с детерминерами) |
| Как объект | 15 | 15 |

---

## v0.3 — Контекстный классификатор

**Файл:** `context_classifier.py` (новый модуль)
**Метод:** Двухуровневая классификация до извлечения:
1. Clause-level: GENERIC / HABITUAL / EPISODIC (аспект, тенс, модальность, тип предиката)
2. NP-level: CONCEPTUAL / SELF / INTERLOCUTOR / GENERIC / REFERENTIAL / QUOTE

| Метрика | v0.2 | v0.3 | Δ |
|---|---|---|---|
| Суждений | 1013 | 877 | −136 (−13.4%) |
| Концептов | ~1001 | ~870 | Менее шумных |
| "Человек" как субъект | 44 | 37 | −7 (референциальные отсеяны) |
| "Ты" как субъект | 0 (skip all) | 66 (INTERLOCUTOR + GENERIC) | Теперь извлекается |
| "Я" как субъект | ~300 | 303 | Стабильно |
| REFERENTIAL отсеяно | — | ~136 | Конкретные референции |
| GENERIC "ты" (weight ×0.7) | — | Включено | Обобщённое "ты" с пониженным весом |

**Новые сигналы:** Аспект (НСВ/СВ), ILP vs SLP предикаты, маркеры хабитуальности, темпоральная конкретность, обобщённо-личное "ты".

**Верификация классификатора (ручная, 8 тестовых предложений):**

| Предложение | Ожидание | Результат | ✓ |
|---|---|---|---|
| "Человек должен быть свободен" | CONCEPTUAL | CONCEPTUAL | ✓ |
| "Этот человек странный" | REFERENTIAL | REFERENTIAL | ✓ |
| "Когда ты видишь закат..." | GENERIC | GENERIC | ✓ |
| "Ты вчера сказал глупость" | INTERLOCUTOR | INTERLOCUTOR | ✓ |
| "Свобода требует ответственности" | CONCEPTUAL | CONCEPTUAL | ✓ |
| "Один человек пришёл" | REFERENTIAL | REFERENTIAL | ✓ |
| "Я люблю свободу" | SELF | SELF | ✓ |
| "Бывает, чувствуешь одиночество" | GENERIC clause | GENERIC clause | ✓ |

---

## v0.5 — Эпистемологические основания + временная динамика

**Файлы:** `density_core.py` (расширен), `FVSC whitepaper.md` (XVII, XVIII)

### F1: Слоистая модель интерпретации (Judgment)
| Поле | Тип | Назначение |
|---|---|---|
| `interpretation_layer` | int (0/1/2) | L0=синтаксис, L1=инференция, L2=LLM |
| `defeasible` | bool | Отменяемое ли суждение |
| `inference_chain` | list[str] | Цепочка обоснования для L1+ |
| `extraction_confidence` | float | Уверенность в корректности извлечения |

Новый метод `Concept.rho_layer(max_layer)` — density matrix только из суждений до указанного слоя.

### F3: Степенной decay + консолидация + архивация (Component, Concept)
| Механизм | Реализация |
|---|---|
| Степенной decay | `w(t) = w₀ · activation_count · (1 + Δt/τ)^{-0.5}` (ACT-R) |
| Архивация | `w < 0.01·max(w)` → `archived=True`, provenance сохранён |
| Консолидация | cosine > 0.85 → `activation_count += 1`, обновление timestamp |
| Восстановление | `Concept.reactivate()` — возврат из архива |

Новые поля Component: `activation_count`, `archived`.

### T6: Сравнение карт двух пользователей
Новый метод `SemanticSpace.compare_maps(space_a, space_b)`:
- Для каждого общего понятия: `Tr(ρ_A^norm · ρ_B^norm)`
- Возвращает: divergent (расхождения), aligned (совпадения), global_similarity

### Whitepaper
- Раздел XVII: Эпистемологические основания (17.1–17.3)
- Раздел XVIII: Временная динамика (18.1–18.5)
- 21 новых академических источников
- Обновлён "Принцип", раздел XII (Антураж), XV (открытые вопросы)

### F2: Персональный прогрев (grounding)
`get_term_vector()` трёхуровневый: PCA (>50 компонентов) → spaCy → хеш. `_personal_basis()` через SVD.

### T5: Relation-dependent transform
`_relation_transform(ρ, relation)`: R_r·ρ·R_r†. `_dominant_relation(A,B)` находит глагол связи.

### T10: Интерактивный канал обратной связи
Новый `core/feedback.py`: FeedbackEngine генерирует вопросы (anomaly, contradiction, defeasible, archive, contrast, milestone), обрабатывает ответы (confirm/reject/promote/contextualize).

### Антураж — живой LLM-диалог
Новый `core/antourage_server.py`: HTTP-сервер localhost:8731. Ollama qwen2.5:7b. FeedbackEngine → контекст → LLM → естественная речь. Персистентность в `data/sessions/*.jsonl`. Извлечение суждений из ответов пользователя → L0.

Новые поля Judgment: `confirmation_status`, `context_tags`.

---

## v0.5.2 — Code fixes + Interpretation Spectrum (2026-03-29)

- **Whitepaper XVII.1**: 3 слоя → 6 уровней формализуемой интерпретации (L0–L3). 21 новый академический источник.
- C1: Type annotations `rho` → `Optional[np.ndarray]`
- C2: `_is_verb` monkey-patch → поле `is_verb: bool` в Concept
- C8: Guard в `von_neumann_entropy`
- C10: Удалены дубликаты в text_normalizer
- C11: Переиспользование векторов в materialize_judgment

---

## v0.5.3 — Critical timestamp fix (2026-03-29)

- **C3**: `Judgment.timestamp` = `time.time()` вместо 0.0. Timestamps из Telegram передаются в extractor. Decay теперь работает корректно.
- C4: `_queryable_concepts` считает только active компоненты
- C9: `[self]` в concepts dict, участвует в query/comparison/recursive_deepen

---

## v0.6.0 — Package + Clause refactor + extraction_confidence (2026-03-29)

- **C7**: `core/` = Python-пакет (`__init__.py`). Все imports с try/except (relative + bare fallback).
- **C5**: `_extract_clause_arguments` → shared `_collect_and_emit()`. Conditional clauses теперь получают passive inversion, discourse pointer filtering, GENERIC modality reduction.
- **T2**: `extraction_confidence` заполняется из сигналов парсинга: OOV, dep=dep, длина предложения, глубина вложенности.

---

## v0.7.0 — Testing: convergence, evaluation, scale (2026-03-29)

- **T4**: Convergence sweep α=[0.5..0.9], k=1..10. Все alpha сходятся. α=0.7→k=6, α=0.8→k=5. Рост массы <1%.
- **T9**: Gold standard: 51 предложение, 49 суждений. P=79.5%, R=71.4%, F1=75.3%.
- **T7**: Scale test: 1002 текста, 363 суждения, 489 терминов, 7117 concepts (с тезаурусом).

---

## v0.7.1 — recursive_deepen optimization (2026-03-29/30)

- **Bottleneck fix**: recursive_deepen зависал на 2600+ concepts. Candidate-index: judgment-linked + top-200 by mass. 7117 concepts: ∞ → 175s.
- Personal-only targets: тезаурусные понятия не deepened, только sources.

---

## Архитектура пайплайна (текущая)

```
текст
  → text_normalizer (чатовый сленг, повторы)
  → spaCy (токенизация, морфология, дерево зависимостей)
  → context_classifier (clause type + NP ref status)
  → tree_extractor (рекурсивный обход дерева + ExtractionContext)
  → density_core (материализация в ρ, decay, consolidation, recursive deepening)
  → feedback (FeedbackEngine: генерация вопросов, обработка ответов)
  → interactive_map + antourage_server (визуализация + LLM-диалог)
```

---

## Файлы проекта

| Файл | Строк | Назначение |
|---|---|---|
| `FVSC whitepaper.md` | ~2300 | Спецификация (I–XVIII + Приложение A) |
| `core/density_core.py` | ~700 | Ядро: density matrices, decay, layers, comparison |
| `core/feedback.py` | ~280 | FeedbackEngine: вопросы + ответы |
| `core/antourage_server.py` | ~450 | HTTP-сервер: карта + Ollama + persistence |
| `core/context_classifier.py` | ~420 | Контекстная классификация NP |
| `core/tree_extractor.py` | ~700 | Рекурсивное извлечение суждений |
| `core/interactive_map.py` | ~820 | Интерактивная HTML-карта + Антураж-панель |
| `core/live_test.py` | ~420 | Telegram pipeline |
| `core/visualize_graph.py` | ~200 | Статичный PNG-граф (networkx) |
| `core/test_poc.py` | ~190 | Юнит-тест на ручных суждениях |
