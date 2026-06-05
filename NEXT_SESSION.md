# Следующая сессия — состояние проекта

## Обновлено: 2026-06-06 — SESSION SUMMARY (Антураж MVP-1 + Obsidian-bridge)

---

## 🔥 Что сделано за сессию 2026-06-06

### 1. Obsidian-bridge: vault → концепт-заметки + HTML-карта
Полноценный двусторонний контур с vault'ом. Один command, и vault получает
персональную семантическую карту как нативные заметки + интерактивную HTML.

**Файлы:**
- `core/export_to_vault.py` — рендер SemanticSpace в `.md` с frontmatter
  (term, weight, polysemy, facets, components), wikilinks к содержащим/содержимым.
- `core/vault_sync.py` — единая CLI: walk vault → space → top-N concept notes →
  HTML map в корень vault'а. Perf-логирование на каждой стадии.

**Запуск:** `python -m core.vault_sync --top 100`
**Что в vault'е:** `_fvsc_concepts/` (100 .md), `_fvsc_concepts/_index.md`, `vault_map.html`.

### 2. LLM-слой: Ollama-клиент, REPL чат поверх карты
**Файлы:**
- `core/llm/client.py` — абстракция (`LLMClient`, `ChatMessage`)
- `core/llm/ollama_client.py` — REST-клиент на stdlib (`chat`, `chat_stream`, `ping`, `list_local_models`)
- `core/llm/map_context.py` — system prompt + компактный текстовый дамп карты
  (топ-N концептов с метриками + рёбра) для контекста модели
- `core/semantic_chat.py` — REPL с дисковым кэшем space'а (`_fvsc_cache.pkl` в vault'е),
  командами `/top N`, `/context`, `/reload`, `/quit`

**Запуск:** `python -m core.semantic_chat [--model qwen2.5:14b-instruct-q4_K_M]`

### 3. Антураж MVP-1 — LLM-driven визуализация (главное)
LLM не просто отвечает текстом, а **подсвечивает узлы графа в реальном времени**
синхронно со своим стрим-ответом. Реализован двухпанельный UI: vis-network слева,
чат справа, SSE-канал для highlight-эвентов.

**Файлы:**
- `service/viz_session.py` — стрим-парсер `[[маркеров]]` (state machine,
  устойчив к токенам, разорванным поперёк маркера; протестирован)
- `service/viz_router.py` — `/viz` (HTML), `POST /viz/ask` (SSE),
  `GET /viz/status` (диагностика). Lazy-load vault space из `_fvsc_cache.pkl`.
- `service/viz_template.html` — двухпанельный UI: граф vis-network,
  чат с подсветкой маркеров инлайн, кнопки `[[concept:...]]` кликабельны.
- `service/app.py` — `/` → 307 redirect на `/viz`, подключён viz_router.

**Адресный синтаксис LLM** (LLM учится использовать через system prompt):
```
[[concept:важно]]              — узел
[[edge:A->B]]                  — связь
[[note:path.md]]               — заметка
[[judgment:важно#3]]           — N-е суждение
[[word:тяжело]]                — литеральное слово
```

**Запуск:**
```
python -m uvicorn service.app:app --host 127.0.0.1 --port 8765
# открыть http://127.0.0.1:8765/
```

**End-to-end протестировано:** Ollama `qwen2.5:14b-instruct-q4_K_M` отвечает,
маркеры в проге вытаскиваются парсером, SSE highlight-эвенты долетают, графа
выделяет упомянутые концепты и фокусирует камеру.

### 4. Память: vision'ы антуража
- `memory/antourage_vision.md` — полная архитектурная карта фичи (уровни
  вложенности, синтаксис адресации, ограничения, roadmap MVP-1/2/3).
- `memory/feedback_session_end_ritual.md` — конвенция «что делать в конце сессии».

### 5. Анализ от Haiku был частично разобран
Прогнал критику его scaling-анализа против реального кода. Из 8 предложений:
2 верных мелочи (dim=50 в дефолте, log perf), 1 уже реализовано (linked +
top_by_mass в recursive_deepen), 5 — over-engineering (sparse, Tucker, Redis,
LSH, distributed) для проекта, чьё реальное узкое место — семантическое
качество, а не CPU.

---

## 📊 Метрики 2026-06-06

### Vault pipeline на реальном корпусе (707 файлов, 3.59MB)

| Стадия | Время |
|---|---|
| collect_vault | 0.5с |
| load thesaurus | 0.2с |
| parse → semantic_input | 0.9с |
| materialize | 2.9с |
| recursive_deepen (3 iters) | 17.9с |
| export 100 notes → vault | 31.8с |
| render HTML | 15.0с |
| **TOTAL** | **~69с** |

Узкое место экспорта — `query_contains/contained_in` (O(N) перебор × 100 концептов).
Лёгкая цель для оптимизации (eigendecomp cache в Concept) — отложено.

---

## 🎯 Открытые направления (приоритет сверху вниз)

### 1. 🔥 АНТУРАЖ MVP-2 + MVP-3 (новый высший приоритет)
Из `antourage_vision.md`:
- **MVP-2 (~1.5ч):** dblclick на узле → drill-down в Components/суждения концепта,
  side-view с заметками-источниками (через грубый сканер vault'а: substring match).
- **MVP-3 (~1.5ч):** подсветка `[[note:...]]` и `[[word:...]]` маркеров на drill-down уровне,
  клик по `[[note:...]]` → `obsidian://open?vault=Rein&file=...`.

### 2. Интеграция в Obsidian как вкладка
Три тира из обсуждения:
- **Тир 1 (15 мин):** iframe через Custom Frames plugin, URL `http://localhost:8765/viz`.
- **Тир 2 (+1ч):** автостарт uvicorn через Shell Commands plugin при загрузке Obsidian.
- **Тир 3 (6-10ч):** настоящий нативный плагин на TypeScript с доступом к vault API
  (LLM получает реальный текст заметок, не только метаданные).

### 3. Точный provenance в Judgment (для MVP-3 правильно)
Переписать `vault_ingest.py` так, чтобы парсить файлы по одному и класть имя
файла в `Judgment.source_text`. Сейчас всё помечено `[vault]` — provenance потерян.
Альтернатива (грубый сканер для MVP-2) уже описана.

### 4. Уровень 0 — кластеры/темы (отложено)
Нужен algorithm choice: k-means на rho_deep_norm vs Louvain/Leiden community
detection на графе. Отдельная сессия.

### 5. Прочие открытые направления (с прошлых сессий)

- **Sibling-FP fix** — есть локальные изменения с 2026-06-05 (F1 79.3%→80.7%
  по memory; коммитятся в этой же сессии).
- **Eval-200 diagnostic** — есть локальные результаты (`eval_200_results*.json`,
  `eval_200_diagnostic.py`); коммитятся в этой же сессии.
- **Compare-режим карт** — `SemanticSpace.compare_maps` есть, но в UI не выведен.
- **Анализ карты в отрыве от текста** — community detection, centrality.
- **L4/L5 операционализация.**

---

## 🚦 Быстрый старт следующей сессии

```bash
# 1) Поднять сервис
python -m uvicorn service.app:app --host 127.0.0.1 --port 8765

# 2) Открыть Антураж в браузере
# http://127.0.0.1:8765/

# 3) Если кэш vault'а устарел — пересобрать
python -m core.vault_sync --top 100
# (создаст также _fvsc_cache.pkl для быстрого старта чата)

# 4) Терминальный чат (без UI) — для отладки промпта
python -m core.semantic_chat --model qwen2.5:14b-instruct-q4_K_M

# 5) Проверки ядра
python -X utf8 -m core.test_invariants                 # 125/125
python -m pytest service/tests/test_smoke.py -v         # 11/11
```

---

## Обновлено: 2026-06-04 — SESSION SUMMARY (FVSC Core Service + квантовый retrieval)

---

## 🔥 Что сделано за сессию 2026-06-04

### 1. FVSC Core Service — FastAPI обёртка
Ядро FVSC теперь standalone HTTP-сервис. Multi-tenancy через именованные
пространства, lazy-load persistence через pickle, авто-save после N ingest-ов.

**Файлы:** `service/` — 10 файлов, ~850 строк
- `app.py` — FastAPI, lifespan с загрузкой ThesaurusPrior, 11 endpoints
- `store.py` — SpaceBundle (пространство + чанки + meta), SpaceStore (CRUD + persistence)
- `ingest.py` — chunking → text_to_semantic_input → load_from_semantic_input
- `retrieval.py` — квантовый retrieval через Tr(ρ_query · ρ_chunk)
- `models.py` — Pydantic v2 схемы
- `format_adapter.py` — mistune AST → структурированные чанки из Markdown

**Endpoints:**
`POST /spaces`, `GET /spaces`, `GET /spaces/{name}`, `DELETE /spaces/{name}`,
`POST /spaces/{name}/save`, `POST /spaces/{name}/deepen`,
`POST /spaces/{name}/ingest` body: {text, source_id, format},
`GET /spaces/{name}/concepts/{term}/contains|contained-in|facets|polysemy|report`,
`GET /spaces/{name}/similarity?a=X&b=Y`,
`POST /spaces/{name}/retrieve` body: {query, top_k},
`GET /compare?a=X&b=Y`

**Запуск:** `uvicorn service.app:app --host 127.0.0.1 --port 8765`
**Тесты:** 11/11 `python -m pytest service/tests/test_smoke.py -v`

### 2. Квантовый retrieval — Tr(ρ_query · ρ_chunk)
Настоящий quantum semantic similarity вместо weighted component matching.
Запрос парсится в ρ_query из basis vectors. Каждый чанк получает свой ρ_chunk
(восстановленный из компонентов с source_text == chunk_id). Score = Tr(ρ_q · ρ_c).

Результат на whitepaper (740 чанков, 3902 концепта): 46-314мс/запрос,
scores 0.01-0.15 (genuine quantum overlap). Находит содержание ПО ТЕМЕ,
а не по вхождению слов.

### 3. Markdown format adapter (mistune AST)
Вместо regex-based strip_markdown — парсинг Markdown в AST через mistune:
- Таблицы → "колонка: значение" (сохраняется column relationship)
- Заголовки → prepend к последующим параграфам (контекст раздела)
- Списки → "родитель: дочерний; дочерний" (сохраняется вложенность)
- Code blocks/HTML → исключены

Сравнение на whitepaper: +32% концептов vs plain text (3902 vs 2960),
ноль табличного мусора в retrieval (plain давал 2/6 запросов с pipe-синтаксисом).

### 4. Whitepaper — добавлены quantum cognition references
- Garg & Ramakrishnan 2019 (EMNLP) — density matrix word embeddings
- Busemeyer & Bruza 2012 (Cambridge UP) — фундаментальная книга quantum cognition

### 5. BGE удалён из проекта
Упоминание BGE-m3 удалено из `text_parser_agnostic.py` docstring.
BGE никогда не использовался в коде — был только задокументирован
как запрещённый паттерн. Основание: BGE-вектор коллапсирует ρ
в rank-1 pure state, теряя asymmetric containment.

### 6. Обсуждены архитектурные направления
- Матрицы плотности как основа для ИИ — гибридный подход разумнее чистого quantum
- FVSC изначально — инструмент когнитивного выравнивания, не AGI-компонент
- Самоприменение: FVSC retrieval для поиска по собственной документации
- Obsidian-плагин как следующий шаг (JS frontend → FastAPI backend)

---

## 🔥 Что сделано за сессию 2026-05-31

### 1. Pipeline ingest для внешних источников
Реализован bridge от Telegram-экспортов и Obsidian-структур к FVSC. Источник
автоконвертируется в MD-файлы с YAML-frontmatter, несущим `register`,
`source`, `social_group` для будущего L5 `context_metadata` — впервые слой 5
заполняется не вручную, а из источника.

**Скрипт:** `core/exocortex_ingest.py`
- JSON-экспорт → структурированные MD-файлы по периодам
- Опциональный флаг `--fvsc` строит SemanticSpace per источник
- Чистка: URL, @mentions, длинные хеши, code blocks, Latin-only токены,
  standalone digits (годы из заголовков)
- Регистры L5: diary, dream, ideas, project, dialogue, creative, reference, и т.д.

### 2. Диагностика на представительном тестовом корпусе
**Скрипт:** `core/diary_diagnostic.py`

Эмпирически подтверждены три предсказания density-matrix архитектуры на
реальном корпусе (не на синтетических предложениях):

| Свойство | Подтверждение |
|---|---|
| Асимметрия containment | Δ ~ 0.9-0.95 на множестве пар при B→A ≈ 0 — впервые не на synthetic gold set |
| Полисемия как энтропия | Концепты с 4-5 фасетами выявляются автоматически через `query_polysemy(t)` |
| L6-кандидаты определяются количественно | По порогу von Neumann H, не по словарю |
| Sibling-FP виден как класс ошибок | Случайные co-occurrence дают высокий Δ — подтверждение проблемы #6 |

**Особое наблюдение:** высокочастотные аффективные маркеры показывают 4-5
фасетов — операциональное обнаружение полисемии аффективных слов без
априорной разметки. Этот класс лексики является полноценным полисемичным
концептом в персональной семантике, не шумом.

### 3. Визуализация (vis-network HTML)
**Скрипт:** `core/visualize_space.py`

Интерактивная карта: узлы размером по частоте, цветом по полисемии (синий→красный),
направленные рёбра по асимметрии содержания, side-panel с метриками,
click-to-navigate. Карты сохраняются вне репозитория (см. .gitignore).

### 4. Полный прогон vault + тезаурус-приор
**Скрипт:** `core/vault_ingest.py`

- 606 .md файлов (3.5M символов), 1200 концептов, 3127 направленных пар
- ConceptNet RU bonus-only приор (bonus=1.5, 95K пар)

**ГЛАВНЫЙ КОЛИЧЕСТВЕННЫЙ РЕЗУЛЬТАТ — узлы vs рёбра:**

| Что покрывает ConceptNet | Процент |
|---|---|
| Top-15 концептов (узлы) | **80%** (12/15) |
| Связи (рёбра) | **1.2%** (38/3127) |

Это эмпирический ответ на главный вопрос проекта: **тезаурус покрывает словарный запас, но не персональные связи**. Корпус даёт ~99% рёбер. Гипотеза "тезаурус даёт скелет, корпус — мясо" получила численное доказательство 80% vs 1.2%.

Top концепты vault — социально-аффективная ось с poly 1.4-2.3, самые
полисемичные имеют 5 фасетов. ~20% top концептов отсутствуют в ConceptNet —
это разговорные формы и аффективные маркеры, by design не покрытые KB.

---

## 📊 Данные тестов (2026-05-31)

### Метрики корпусов (анонимизированы)

| Корпус | Объём | Концепты | Полисем. лидер |
|---|---|---|---|
| Diary-register, ~3500 сообщений | ~ | 800 (top800/797) | 5 фасетов |
| Vault, 606 файлов | 3.5M симв. | 1200 (top1200/1193) | 5 фасетов (poly=2.275) |

### Метрики ядра (без изменений с 2026-05-28)

| Метрика | Значение |
|---|---|
| Тесты математических инвариантов | 125/125 PASS |
| Recall на gold set | 100% |
| Precision на gold set | 66% |
| F1 | 79% |
| Тезаурус-приор пар | 95279 |

### Бенчмарки vault pipeline

- Сбор vault (606 файлов): **2.2с**
- Загрузка ConceptNet: **0.2с**
- text_to_semantic_input (3.5M символов, 1200 концептов): **0.8с**
- materialize_judgment всех концептов: **2.8с**
- recursive_deepen(3, 0.7): **18.8с**
- HTML рендер: <1с
- **Итого end-to-end: ~25 секунд** для полного vault с приором

---

## 🎯 Открытые направления (приоритет сверху вниз)

### 1. 🔥 ДОРАБОТАТЬ ВИЗУАЛИЗАЦИЮ (новый высший приоритет)
Текущая `visualize_space.py` — рабочий MVP, но требует углубления:
- Динамические фильтры (порог рёбер, top-N, фильтр по полисемии)
- Раскрытие концепта вглубь (drill-down через `query_facets` — показывать собственные грани как мини-граф)
- Времeнной слайдер (если корпус датирован — фильтр по периоду; видеть эволюцию)
- Compare-режим: две карты бок-о-бок с подсветкой пересечений и расхождений
- Поиск концепта по подстроке
- Экспорт подграфа (фокус-узел + neighborhood) как отдельный JSON для дальнейшего анализа
- Визуализация фасетов: круговая диаграмма внутри узла? eigenvalue-веса?
- L4/L5 цветовая разметка (когда заполнятся каналы)

### 2. 🔥 АНАЛИЗ КАРТЫ В ОТРЫВЕ ОТ ИСХОДНЫХ ТЕКСТОВ (новый)
Что можно извлечь о корпусе, имея ТОЛЬКО ρ-граф, без доступа к оригиналу?
- Профильные доминанты: что является центром (degree, betweenness, eigenvector centrality)
- Эмоциональные оси: какие концепты тянут карту в свою сторону по физике
- Тематические кластеры через community detection (Louvain, Leiden)
- Самые "одинокие" концепты — те, что в персональной семантике, но без сильных связей
- Кандидаты на "ключевые понятия" — высокая центральность + высокая полисемия
- Можно ли восстановить регистр/тематику корпуса только по карте?
- Это методологический тест: что говорит ρ-граф о структуре, если читать его как картину, а не как индекс?

### 3. 🔥 ПРИКРУТИТЬ АНТУРАЖА ДЛЯ АНАЛИЗА КАРТЫ (новый)
Сейчас `feedback.py` (FeedbackEngine) есть, но не связан с готовой картой.
- Антураж читает ρ-граф и выбирает интервенции по триггерам:
  - `polysemy_degree > θ` → "у тебя X в N разных смыслах, разделить?"
  - `anomaly_score > θ` → "это новое употребление, развернуть?"
  - `centrality > θ` → "это узел с большим влиянием — что для тебя X?"
- Сессия диалога: Антураж задаёт вопросы из карты, ответы обновляют ρ через `materialize_judgment` с `user_confidence`
- Интеграция с visualize: подсветка узлов-кандидатов, кнопка "спросить Антуража"
- Триггеры по состоянию ρ, не ELIZA-словарь

### 4. Тест на 200 предложениях + фиксы парсера
- `eval_sentences_200.txt` (200 предложений) — было #1 ранее
- Замерить время, типы ошибок, sibling-FP, разреженность
- Теперь с тезаурусом — измерить эффект приора при bonus=1.2 vs 1.5

### 5. Compare maps между источниками
- `SemanticSpace.compare_maps()` на двух регистрах
- Где смыслы пересекаются (общая семантика), где расходятся (контекстная дифференциация)
- Это часть #2 и тест #3 — Антураж может работать на дифференциальной карте

### 6. Sibling-FP фикс
- Эвристика: блокировать прямые пары через "и"/"или", сохранять как СИБЛИНГИ через verb-родителя
- Сейчас виден количественно через diagnostic
- Ожидаемый эффект: F1 ~85-90%

### 7. Весовая метрика в eval
- Сейчас eval бинарный (пара есть/нет)
- top-K по весу, precision@10, recall@10, MAP

### 8. L4/L5 операционализация (предыдущий приоритет)
- L4 (телесный) биологически универсален → baseline grounding между картами
- L5 (социальный) — уже извлекается из метаданных источников, встраивается в `RichJudgment.context_metadata`

### 9. Каналы заполнения слоёв 2-6
- L2 — frame extractor (T13)
- L4 — perceptual extractor + NRC emotion lexicon
- L5 — context tagger (расширить на vault)
- L6 — Антураж (см. #3)

### 10. "Книга = факты в связях слов"
- `read_book(path)` — книга целиком через парсер, автор в `context_metadata`
- Compare_maps покажет влияние прочитанного на персональную карту

---

## 🧠 Архитектурные принципы

1. **Два фундаментальных вопроса проекта:**
   - Как работает построение смыслов у людей (механизм)
   - Поможет ли это людям понять себя и друг друга (практика)

2. **Каскад семантики, не backprop:**
   - Скелет (тезаурус) → адаптация (co-occurrence) → шлифовка (feedback)
   - Физика памяти (ACT-R): decay, consolidation, archive

3. **Ось L4/L5 — биология vs культура:**
   - L4 универсален → связывает людей при сравнении карт
   - L5 культурно вариативен → источник конфликтов смыслов

4. **Тезаурус валидирует, корпус извлекает (новое, 2026-05-31):**
   - Эмпирически: 80% узлов покрыты ConceptNet, только 1.2% рёбер
   - Стратегия bonus-only остаётся правильной — penalty убил бы 98.8% реальных связей
   - Любое "обогащение через тезаурус" уничтожит персональную семантику

---

## 📂 Коммиты сессии 2026-06-04

```
f4e397f feat: quantum retrieval — Tr(ρ_query · ρ_chunk) instead of keyword matching
c391f88 feat: Markdown format adapter — AST-level structural extraction
1cf30d1 feat: FVSC Core Service — FastAPI wrapper for the semantic engine
7187062 chore: remove BGE reference from text_parser_agnostic docstring
c0495f6 docs: add missing quantum cognition refs to whitepaper XVI
d23c6c9 (pushed 18 accumulated commits from 2026-05-27/31)
```

## 🚦 Быстрый старт следующей сессии

```bash
# Запустить сервис (python 3.12+, venv с fastapi/uvicorn/mistune)
uvicorn service.app:app --host 127.0.0.1 --port 8765

# Проверить здоровье (должно быть 11/11)
python -m pytest service/tests/test_smoke.py -v

# Self-retrieval test — ингест whitepaper и поиск по нему
python service/selftest.py

# Сравнение форматов MD vs plain
python service/compare_formats.py

# Проверить здоровье ядра (должно быть 125/125)
python -X utf8 -m core.test_invariants

# Полный прогон vault → карта (~25 секунд) — пути локальные, не в репо
python -X utf8 -m core.vault_ingest
```

---

## Откуда мы пришли (предыдущая сессия)

Старая `Обновлено: 2026-05-28` — завершён агностический переход (удалён spaCy, ~4000 строк), бридж text_parser → density_core, RichJudgment 6 слоёв, тезаурус-приор bonus-only, 125/125 PASSED, baseline F1=79%. Эта сессия (2026-05-31) проверила всё это на реальном корпусе в 600+ файлов и численно ответила на главный вопрос «достаточно ли тезауруса».
