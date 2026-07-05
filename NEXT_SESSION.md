# Следующая сессия — состояние проекта

## Обновлено: 2026-07-05 — синхронизация с реальностью (файл отставал на 3 сессии)

---

## 🔥 Что сделано после 2026-06-15 (файл не обновлялся, вот сводка по коммитам)

### 2026-06-16 — Ollama auto-management ✅ ЗАКРЫТ (был priority #1)

Полностью реализован план 1.1–1.4 из прошлой версии этого файла:

- `obsidian-plugin/src/ollama.ts` — autodetect (Win/macOS/Linux) + spawn `ollama serve`
  detached (unref + stdio=ignore), переживает закрытие Obsidian как tray-app.
- `main.ts`: `tryAutoStartOllama()` в параллель с `backend.start()` — к моменту
  открытия view `ollama_up` уже true.
- `view.ts`: inline model picker когда `modelName ∉ models_available`;
  race fix плашки «Чат не подключён» — 3 consecutive misses вместо мгновенного рендера.
- `POST /viz/ollama_pull` SSE (worker-thread + queue.Queue, как build_from_vault);
  `OllamaClient.pull_stream()`.
- `paths.ts`: `macosSystemCandidates()` — закрыт и Mac-эквивалент бага автодетекта Python.
- Custom `OLLAMA_MODELS`: `detectOllamaModelsDir()`, поле Settings «Папка моделей Ollama»
  с autodetect-hint, плашка «Перезапустить Ollama» (taskkill + respawn с env),
  `killAllOllama()` / `restartOllamaWithModelsDir()`.
- Model picker в 3 секции: «Установлено у тебя» / «Рекомендованные» (qwen2.5 7/14/32b,
  llama3.1:8b, gemma2:9b, qwen2.5-coder:14b) / «Своя модель».
- `windowsHide` на всех spawnSync — убраны мигающие cmd-окна.

### 2026-07-02 — restart-invariant core (fix фундаментального бага)

- `stable_hash()` (SHA-256) вместо встроенного `hash()` в `get_term_vector`,
  `_role_transform`, `_relation_transform`. Встроенный hash рандомизирован
  per-process (PYTHONHASHSEED): после рестарта сервиса тот же терм получал
  другой базовый вектор → consolidation переставала срабатывать, compare_maps
  сравнивал несовместимые базисы.
- ⚠️ **Старые .pkl карты построены на нестабильных хешах — их нужно
  пере-ingest'ить из vault'а** (касается живой карты Rein'а!).
- `_orthogonal_matrix()` — lru_cache детерминированного QR: 500 judgments
  @ dim=128: 3.56s → 0.36s (~10x).
- `purge_source()` crash fix (read-only properties → `concept.invalidate()`).
- Новый suite `core/test_restart_invariance.py` — байт-идентичность векторов
  между процессами с разным PYTHONHASHSEED.

### 2026-07-04 — cascade-слои: feedback (live) + skeleton (core-only)

- **FeedbackEngine → сервис** (третий слой каскада, live):
  - `GET  /spaces/{name}/feedback/questions` — калибровочные вопросы из состояния карты
  - `POST /spaces/{name}/feedback/answer` — confirm/reject/promote/... (id одноразовые, 404 на повтор)
  - `GET  /spaces/{name}/feedback/stats` — прогресс ревью
  - Контрактные тесты `core/test_feedback.py` (138 строк): противоречия AFFIRM/NEGATIVE,
    confirm/reject/rebuild ρ, dedup вопросов, defeasible promotion в L0, reactivation.
- **Skeleton layer** (первый слой каскада, `core/skeleton.py`) — **ТОЛЬКО core, в сервис НЕ подключён**:
  - `SkeletonIndex.from_conceptnet()` — 132,838 judgments индексируются за ~1.4с один раз,
    per-ingest seeding ~0.01с (раньше `load_for_terms()` перечитывал весь JSON на каждый вызов).
  - `seed_skeleton(space, index, terms)`: сидирует ТОЛЬКО термы уже присутствующие
    в space (стенографический принцип), идемпотентен, `max_per_term` против
    RelatedTo-хабов, modality 0.3 — личные высказывания доминируют.
  - Коммит-месседж прямо говорит: «Service wiring comes in the next commit» — этого коммита ещё нет.

---

## 🎯 Открытые направления (приоритет сверху вниз)

### 1. 🔥 Skeleton layer → service wiring (~1-2ч) — начатое незаконченное

`core/skeleton.py` готов и оттестирован, но ничего в `service/` его не вызывает.
План:
- Singleton `SkeletonIndex` в service (lazy, один load на процесс).
- Вызов `seed_skeleton()` в ingest-пути (после добавления personal judgments,
  на новые термы) — и в `build_from_vault`, и в live watcher / инкрементальном ingest.
- Настройка/флаг чтобы можно было выключить (и путь к conceptnet_ru.json конфигурируемый).
- Smoke-тест через TestClient: ingest → термы обросли skeleton-компонентами.

### 2. ⚠️ Re-ingest живой карты после stable_hash (~30 мин + время билда)

Карта Rein'а (1193 концепта, cache 99 MB) построена до 0bbb147 — на нестабильных
хешах. Формально работает, но consolidation/compare с новыми данными некорректны.
Прогнать build_from_vault заново, убедиться что cache пересоздан.

### 3. Live UX тест: интерпретация через ρ (~30 мин — harness готов)

- `service/tests/test_interpretation.py`, `interpret_cli.py`, `interpretation_cases.json`.
- Прогнать на свежей (пере-ingest'нутой!) карте 3-5 кейсов, смотреть divergence_score.
  > 0.6 — interpretation lens работает; меньше — диагностика system prompt / top_n.
- Требует скачанной модели (теперь ставится через model picker в UI).

### 4. Feedback UI в плагине (~2-3ч)

Endpoints третьего слоя live, но плагин их не использует. Минимум: панель/модал
«Калибровка» — вопросы из `/feedback/questions`, кнопки confirm/reject/skip,
прогресс из `/feedback/stats`.

### 5. PyInstaller bundle (~6-10ч) — перенесено
Заменяет шаги 1, 5 из INSTALL_RU.md.

### 6. Silent_pool в Антураже (~1ч) — перенесено
Endpoint работает, чат не использует.

### 7. CM6 подсветка слов (~2-3ч) — перенесено
### 8. Нативный TS-граф без iframe (~3-4ч) — перенесено

---

## 🚦 Быстрый старт следующей сессии

```bash
# Тесты ядра
python -X utf8 -m core.test_invariants                # 125/125
python -m pytest core/test_restart_invariance.py -v   # НОВОЕ 07-02
python -m pytest core/test_feedback.py -v             # НОВОЕ 07-04
python -m pytest core/test_skeleton.py -v             # НОВОЕ 07-04

# Smoke service (требует запущенного backend'а)
python -m uvicorn service.app:app --host 127.0.0.1 --port 8765 &
python -m pytest service/tests/test_smoke.py -v       # 11/11

# Interpretation harness
python -m service.tests.interpret_cli                 # interactive
python -m pytest service/tests/test_interpretation.py -v -s   # golden (skip без модели)

# Плагин: пересборка после правок TS
cd obsidian-plugin && npm run build
DEST="C:/Users/daur1/Desktop/экзокортекс для fvsc map/Rein/.obsidian/plugins/fvsc-antourage"
cp -f main.js styles.css manifest.json "$DEST/"
```

---

## 🧠 Архитектурные принципы (обновлено)

К предыдущим (1-9):

10. **Live-тест ловит то, что unit-тесты пропускают** (2026-06-15):
    - 125/125 invariants + 11/11 smoke были зелёные, но автодетект Python никогда не работал, cache никогда не lazy-load'ился через /viz/status, race в bootstrap всегда был.
    - **Перед заявлением «MVP готов»** — обязательно прогонять полный live-цикл: бэкап cache+settings → reload плагина → дойти до карты + чата + интерпретации.

11. **Если что-то «через раз» в UX — это race**, не магия. Искать таймауты/последовательности фронт↔бэк.

12. **Lazy-load в HTTP API смотрит на disk, не только на in-memory state** (2026-06-15):
    - `/viz/status` обязан триггерить `_get_space()` если есть cache на диске.
    - Иначе клиент видит «space_loaded=false» при наличии данных и принимает неправильные решения.

13. **Mass-adoption — не «когда-нибудь»** (2026-06-15):
    - Ollama auto-management — такой же блокер как автодетект Python. ✅ Закрыт 06-16.
    - Любой шаг «открой терминал и запусти X» = failed UX для не-технического взрослого.

14. **Никогда не использовать встроенный `hash()` для персистентных данных** (2026-07-02):
    - PYTHONHASHSEED рандомизирует его per-process → «работает в сессии, ломается после рестарта».
    - Только `stable_hash()` (SHA-256). Старые артефакты на нестабильных хешах — пере-ingest.

15. **Слой каскада не существует, пока сервис его не вызывает** (2026-07-04):
    - ThesaurusLoader умел конвертировать edges с 05-31, но никто его не звал.
    - FeedbackEngine лежал в core без единого импорта.
    - Чек: `grep -r "ИмяКласса" service/` — если пусто, слоя в продукте нет.

16. **NEXT_SESSION.md обновлять в конце КАЖДОЙ сессии с коммитами** (2026-07-05):
    - Файл отставал на 3 сессии; «priority #1 Ollama» был закрыт 3 недели назад.

---

## Откуда мы пришли (предыдущие сессии)

### 2026-06-15 (ночь) — первый честный live UX тест
5 корневых багов найдено и запатчено: формула версии Python в testPython
(`*10` → `*100`), Obsidian не наследует bash PATH (`windowsSystemCandidates()`),
backend race на double-build (атомарный claim), `/viz/status` без lazy-load cache
(главный виновник «карта не работает»), view self-dedup race. Карта Rein'а
(1193 концепта) стабильно грузится. Создан interpretation harness.

### 2026-06-13 (вечер) — MVP onboarding layer
4-слойный онбординг сверху ядра: SSE build_from_vault, autodetect, BootstrapModal, INSTALL_RU. См. memory `mvp_onboarding_2026_06_13.md`.

### 2026-06-06 (вечер) — Provenance + plugin + live watcher
TS plugin с auto-spawn uvicorn. Per-file provenance. silent_pool (51K). Live watcher с debounce 1.5с. cytoscape.

### 2026-06-06 (утро) — антураж MVP-1
Антураж в браузере через `/viz`. SSE chat с маркерами `[[concept:X]]`.

### 2026-06-05 — Sibling-FP fix
Coordination-aware parser; F1 79.3% → 80.7%.

### 2026-06-04 — FVSC Core Service
FastAPI обёртка, 11 endpoints, quantum retrieval через Tr(ρ_query·ρ_chunk).

### 2026-05-31 — Empirical pivot
Тезаурус покрывает 80% узлов, 1.2% рёбер. Bonus-only стратегия закреплена.
