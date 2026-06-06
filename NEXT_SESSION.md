# Следующая сессия — состояние проекта

## Обновлено: 2026-06-06 (вечер) — SESSION SUMMARY (Plugin + Provenance + Live watcher)

---

## 🔥 Что сделано за сессию 2026-06-06 (продолжение)

### 1. 🔥 Obsidian-плагин (этап 1 из roadmap'а) — landed
TypeScript-плагин с автозапуском Python-бэкенда. Папка `obsidian-plugin/`:

**Файлы плагина:**
- `manifest.json`, `package.json`, `tsconfig.json`, `esbuild.config.mjs`, `install-to-vault.cmd`
- `src/main.ts` — Plugin lifecycle, status bar (●/цвет), команды, ribbon icon
- `src/backend.ts` — `BackendController`: child_process spawn uvicorn,
  health-poll `/viz/status`, обработчик `ENOENT` с понятным сообщением
- `src/settings.ts` — pythonPath, fvscRepoPath, port, modelName, autoStart
- `src/view.ts` — `AntourageView` ItemView с iframe на `/viz` + toolbar
  («Перезагрузить карту», «Открыть Obsidian-граф» — split с native graph view)
- `src/vault_watcher.ts` — live watcher (см. ниже)

**Backend изменения:**
- `service/app.py` lifespan читает `FVSC_VAULT_PATH` / `FVSC_LLM_MODEL` из env
- CORS middleware: `allow_origins=["*"]` (origin `app://obsidian.md` был блокирован)

**Установка:**
```
cd obsidian-plugin
npm install
npm run build
install-to-vault.cmd   # копирует main.js + manifest.json + styles.css в <vault>/.obsidian/plugins/fvsc-antourage/
```
В Settings → Community plugins → toggle FVSC Antourage on. Указать pythonPath и fvscRepoPath.

### 2. 🔥 Provenance pipeline (главная архитектурная фича)
Раньше всё помечалось `source_text="[vault]"`. Теперь каждый Judgment знает
из какого .md файла он пришёл.

**Файлы:**
- `core/provenance.py` — `build_provenance_and_silent(si, files_by_path, cfg)`:
  второй per-file pass через `extract_concepts_and_cooccurrence`, выдаёт
  `(ProvenanceMap, SilentPool)`.
- `density_core.SemanticSpace.load_from_semantic_input` принимает optional
  `provenance` — N Judgment'ов на концепт с `modality * fraction`.
  **Критичный нюанс:** `intensity` НЕ делится (только modality). Иначе ρ
  размывается по разным векторам и query_contains возвращает мизер. Этот
  баг был обнаружен и исправлен в этой же сессии.
- `core/vault_sync.py` использует новый flow + auto-saves `_fvsc_cache.pkl`
  (раньше кэш писал `semantic_chat` — не очевидно для нового пользователя).
- Endpoint `GET /viz/concepts/{term}/sources` — топ-N .md с весами.
- Endpoint `GET /viz/silent?query=...&min_freq=1&max_freq=4` — поиск в silent_pool.
- UI: dblclick на узле графа или на `[[concept:...]]` в чате →
  панель «откуда пришёл смысл» с `obsidian://open?vault=...&file=...` ссылками.

### 3. 🔥 Silent_pool (новый структурный слой)
Концепты с freq < min_freq (5) теперь не отбрасываются — сохраняются
параллельной структурой `SemanticSpace.silent_pool = {token: {freq, sources: {path: count}}}`.

- Threshold: freq ≥ 1, без лимита (Rein's choice).
- НЕ участвует в `query_contains` / `compare_maps` / retrieval.
- Назначение: рефлексия «у тебя есть это понятие, но ты говорил о нём один раз —
  окружающие не могут знать что это важно». На vault'е Rein'а: **51,365 silent
  токенов, 29,024 произнесены однажды.**
- `/viz/silent` endpoint для browsing.
- UI fallback: dblclick на термин не из графа → ищет в silent → badge «🔇 silent · N×».

### 4. 🔥 Live vault watcher (этап 2 из roadmap'а) — landed
Карта живёт. Изменил заметку → через ~1.5с backend обновил ρ.

**Файлы:**
- `core/density_core.py`:
  - `SemanticSpace.purge_source(path)` — архивирует все компоненты с этим
    source_text, сбрасывает ρ, чистит silent_pool.
  - `SemanticSpace.ingest_one_file(path, si_local, silent_local)` — инкрементальный add.
- `service/viz_router.py`:
  - `POST /viz/file_ingest` (create/modify/delete/rename), auto-saves cache каждые 5 ingest'ов.
  - `POST /viz/save_cache` для force-save (используется плагином на unload).
- `obsidian-plugin/src/vault_watcher.ts`:
  - Hooks на `vault.on('modify'|'create'|'delete'|'rename')`.
  - Debounce 1.5с per path.
  - Исключает `_fvsc_concepts/`, `.obsidian/`, `.trash/`, файлы > 5MB.
- Status bar: `● FVSC: up  ↻…/папка/file.md` во время активности.

**Trade-off:** инкрементальный ingest НЕ пересчитывает global provenance fractions.
Через сотни изменений возможен лёгкий drift. Решение: периодический
`python -m core.vault_sync` для восстановления точности.

### 5. Граф — Obsidian-style эстетика (этап 4 частично)
vis-network → cytoscape.js + cose layout.

**Файлы:**
- `service/viz_template.html` — переписан полностью под cytoscape.
- `core/visualize_space.py` — `build_graph_data` параметризован:
  - `include_neighbours=3`: добавляет satellite-узлы (специфические соседи top-N).
  - `neighbour_min_score=0.45`, `edge_threshold=0.35`, `max_edges_per_node=10`.
  - Эффект: 100 top + 68 satellites = 168 nodes, 264 edges (раньше 100 nodes / 10 edges).

**UX:**
- Hover-focus: соседи яркие, остальное тускнеет (0.12 opacity).
- Дебаунс камеры 350мс — больше нет ping-pong когда LLM пишет несколько `[[concept:X]]` подряд.
- Клик на `[[note:путь.md]]` в чате → `obsidian://open` (требует `__VAULT_NAME__` placeholder).
- Иконка 📄 для note-маркеров, hint «(клик — открыть в Obsidian)».
- Двойной клик на `[[concept:X]]` в чате → sources panel.

---

## 📊 Метрики 2026-06-06 (вечер)

### Vault pipeline на реальном корпусе (707 файлов, 3.59MB)

| Стадия | Время |
|---|---|
| collect_vault | 0.5с |
| load thesaurus | 0.2с |
| parse → semantic_input | 1.0с |
| **provenance + silent** (новое) | **1.0с** |
| materialize (после intensity-fix) | 36.3с |
| recursive_deepen (3 iters) | 8.3с |
| export 100 notes → vault | 32.0с |
| render HTML | 15.3с |
| save_cache (новое) | 0.2с |
| **TOTAL** | **94.7с** |

### Качество карты

| | До provenance | После |
|---|---|---|
| Концепты с реальной атрибуцией | 0/1200 | 1200/1200 |
| silent_pool | 0 | 51,365 tokens (29,024 hapax) |
| Cache size | ~70 MB | 93.9 MB |
| Graph density (top=100) | 10 edges | 100 top + 68 sat = 168 nodes, 264 edges |
| Тесты ядра | 125/125 | 125/125 |
| Smoke service | 11/11 | 11/11 |

---

## 🎯 Открытые направления (приоритет сверху вниз)

### 1. 🔥 Этап 6 (новый) — Silent_pool в Антураже (~1ч)
Сейчас silent_pool существует и endpoint работает, но **антураж его не использует**
в ответах. Нужно:
- В `service/viz_session.py` — system prompt: добавить блок «known silent concepts»
  (индекс топ-N silent с freq=2-4).
- На пользовательский вопрос с термином из silent — LLM формирует особый ответ:
  «у тебя есть это понятие но ты говорил о нём редко».
- Это закрывает сценарий «почему окружающие не уважают моё личное пространство»
  который был использован как мотивация для silent_pool.

### 2. 🔥 Этап 3 — CM6 подсветка слов в заметках (~2-3ч)
Новый адресный маркер `[[locate:путь.md#"конкретная фраза"]]`.
- Плагин слушает SSE напрямую (через EventSource в TS), не через iframe.
- На событие `locate`: `workspace.openFile(file)`, найти позицию, добавить
  `Decoration.mark` через CM6 на найденный диапазон, `editor.scrollIntoView`.
- Подсветка временная (через CSS-класс), файл не модифицируется.
- Требует Antourage system prompt'а: «когда говоришь о месте в заметке,
  используй [[locate:путь#"первые слова фразы"]]».

### 3. Этап 1.5 — автодетекция путей в Settings (~45 мин)
Mass-adoption критерий. Убрать обязательные поля где возможно:
- FVSC repo path: плагин знает свой `__dirname`, ищет `service/app.py` в
  соседних директориях / `~/FVSC` / `Documents/FVSC`.
- Python interpreter: попробовать `../venv/Scripts/python.exe`, `python.exe` в PATH.
- Vault path вообще убрать — он известен через `app.vault.adapter.getBasePath()`.
- Поля показывать только если автодетекция не сработала.

### 4. Этап 4 (полный) — нативный TS-граф без iframe (~3-4ч)
cytoscape прямо в плагине. Compound nodes для drill-down. Прямой EventSource
для SSE (без iframe-bridge). Это делает антураж по-настоящему интегрированным
с Obsidian (можно из графа открывать заметки одним кликом без `obsidian://`).

### 5. Этап 5 — PyInstaller bundle (~6-10ч)
**Архитектурно критичен** для mass adoption (см. `memory/feedback_mass_adoption.md`).
Python больше не нужен. Один .exe в директории плагина. Цель: установил
плагин → сразу работает.

### 6. Точный edge provenance per-file (отложено)
Сейчас edge fallback = self(A) когда co-occurrence cross-file. Можно сделать
sentence-granularity (`файл.md:para3`) — точнее, но шумнее в drill-down.

---

## 🚦 Быстрый старт следующей сессии

```bash
# Проверки ядра
python -X utf8 -m core.test_invariants                 # 125/125

# Smoke service (нужен запущенный uvicorn — поднимет плагин в Obsidian)
python -m pytest service/tests/test_smoke.py -v         # 11/11

# Full rebuild vault (если drift накопился)
python -X utf8 -m core.vault_sync --vault "C:\\Users\\daur1\\Desktop\\экзокортекс для fvsc map\\Rein" --top 100

# Backend без плагина (для отладки бэкенда)
python -m uvicorn service.app:app --host 127.0.0.1 --port 8765

# Плагин: пересборка после правок TS
cd obsidian-plugin && npm run build && install-to-vault.cmd

# UI правки в viz_template.html — НЕ требуют пересборки плагина, только тоггл backend'а
```

---

## 🧠 Архитектурные принципы (обновлено)

К предыдущим:

5. **Provenance = первая практическая фича FVSC** (2026-06-06):
   - До этого FVSC был «зеркало смысла», сейчас «зеркало откуда смысл».
   - Каждое изменение пайплайна должно сохранять source_text в Judgment.
   - Любая правка `load_from_semantic_input` — следить за инвариантом
     `intensity` НЕ делится между source-файлами.

6. **Stenography includes silent** (2026-06-06):
   - Низкочастотные токены не отбрасываются, идут в `silent_pool`.
   - Это словарь «гул мыслей» — НЕ участвует в density-matrix, но доступен
     для рефлексии и Антураж'а.
   - Threshold freq≥1: максимальная честность, шум фильтруется на уровне UX.

7. **Living map > snapshot** (2026-06-06):
   - Live vault watcher через debounce. Карта обновляется на правки.
   - Trade-off: drift возможен — периодический full rebuild компенсирует.

---

## Откуда мы пришли (предыдущие сессии)

### 2026-06-06 (утро) — антураж MVP-1
Антураж работал через /viz HTML в браузере. vis-network граф. SSE chat.
Маркеры `[[concept:X]]` и `[[edge:A->B]]` подсвечивали узлы. Vault_sync
писал `.md`-ноты + HTML карту в vault, но кэш приходилось строить через
запуск semantic_chat. Не было плагина, не было provenance, не было
silent_pool, не было live watcher'а. Всё это landed в этой сессии.

### 2026-06-05 — Sibling-FP fix
Coordination-aware parser; F1 79.3% → 80.7%, sibling_fp_rate 2.5% → 0.66%.
См. memory.

### 2026-06-04 — FVSC Core Service
FastAPI обёртка, 11 endpoints, quantum retrieval через Tr(ρ_query·ρ_chunk),
Markdown format adapter (mistune AST). См. git log.

### 2026-05-31 — Empirical pivot
Тезаурус покрывает 80% узлов, 1.2% рёбер. Bonus-only стратегия закреплена.
См. memory.
