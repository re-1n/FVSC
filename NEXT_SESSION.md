# Следующая сессия — состояние проекта

## Обновлено: 2026-06-15 (ночь) — SESSION SUMMARY (first honest live UX test)

---

## 🔥 Что сделано за сессию 2026-06-15

Первый честный прогон онбординга «как новый юзер» — бэкап cache + data.json, перезагрузка плагина, проход всей цепочки. Live-тест вскрыл 5 багов, **все запатчены**. Карта Rein'а (1193 концепта) теперь стабильно загружается в UI. Единственное что не сделано — Ollama auto-management (priority #1 следующей сессии).

### Live-тест баги и фиксы

1. **`testPython` формула версии** (`obsidian-plugin/src/paths.ts`):
   - `sys.version_info[0]*10+[1]` → для Py3.13 даёт `43`, проверка `v >= 310` всегда false.
   - **Автодетект Python ни разу за всю историю не мог сработать.** Залив пользователей через INSTALL_RU.md «вписать pythonPath руками» это маскировал.
   - Фикс: `*100+`.

2. **Obsidian не наследует bash PATH** (`paths.ts`):
   - `which python` в bash показывает Python313, в процессе Obsidian'а — нет.
   - Фикс: новая функция `windowsSystemCandidates()` — прямой системный поиск:
     - `%LOCALAPPDATA%\Programs\Python\Python3*\python.exe`
     - `Program Files\Python3*\python.exe` + x86
     - `C:\Windows\py.exe` (launcher)
   - Также: `isLiveFile()` через `statSync` — фильтрует broken symlinks (твой venv создан git-bash'ом в unix-стиле, `venv/bin/python` → broken).

3. **Backend race на double-build** (`service/viz_router.py`):
   - `_state["bootstrap_running"] = True` ставился ВНУТРИ `event_stream()` генератора, ПОСЛЕ возврата StreamingResponse.
   - Два POST'а проходили проверку → два worker'а на cache → cache corruption.
   - Фикс: атомарный claim в эндпоинте до return, release в finally генератора.

4. **`/viz/status` не lazy-load cache** (`viz_router.py`) — главный виновник «карта не работает»:
   - Смотрел `_state["space"]`, не вызывал `_get_space()`.
   - После backend startup → cache на диске → `space_loaded=false`.
   - View рендерил CTA «Построить карту» вместо загрузки существующей карты, и пользователь запускал build_from_vault заново каждый раз.
   - Фикс: lazy-load внутри `viz_status()`.
   - Бонус-фикс view: при `vault_cache_exists && !space_loaded` показывать «Загружаю карту из cache…», не CTA.

5. **View self-dedup race** (`obsidian-plugin/src/view.ts`):
   - Первая dedup-логика (`peers[0] !== ours`) сохраняла первый дубль.
   - Симптом: две полные копии view (toolbar+iframe×2) внутри одного pane.
   - Фикс: симметричная логика — каждый instance detach'ит ВСЕХ других peers.

### Связанные UX-фиксы плагина

- `BootstrapModal.activeInstance` singleton — два клика не открывают две модалки.
- `buildBtn.disabled = true` при клике — UI guard.
- `attachToInflightBuild()` — если backend ответил 409 (билд уже идёт), второй модал переключается в passive polling вместо запуска дубля.
- `scheduleBootstrapCheck` в main.ts — 10 ретраев по 1с на `/viz/status`. Раньше один setTimeout 1000ms давал «через раз».
- `onLayoutReady` detach дублей view из session restore.

---

## 📊 Метрики 2026-06-15

| | До live-теста | После |
|---|---|---|
| Багов критичных для нового юзера | 5 невидимых | 0 |
| Размер main.js | 37.9 KB | 43.6 KB |
| Полей Settings обязательных | 0 (заявлено) | 0 (реально работает) |
| Cache загружается на старте | нет (lazy на /viz, но плагин рендерил CTA до этого) | да (lazy через /viz/status) |
| Защита от double-build | UI-only, обходилась race | UI + backend |
| Тесты ядра (test_invariants) | 125/125 | 125/125 (не трогали) |
| Smoke service (test_smoke.py) | 11/11 | 11/11 (не трогали) |

### Verified end-to-end (live, не мокированно)
- Полный цикл «свежий vault → автодетект → backend start → Bootstrap → build → cache → reload → карта в UI».
- Cache 99 MB load <1с.
- Карта рендерится: 1193 концепта, кластеры видны.
- BootstrapModal с прогрессом по 9 стадиям работает.
- Dedup view: после фикса — одна view в одном pane.

### Не сделано
- **Ollama auto-management** (см. ниже, priority #1).
- Live build_from_vault на полностью **первом** vault'е через UI на чистой машине без Python — не проверено (Python всё ещё ставится вручную).

---

## 🎯 Открытые направления (приоритет сверху вниз)

### 1. 🔥 Ollama auto-management (~3-5ч) — БЛОКЕР MASS-ADOPTION

См. `feedback_ollama_auto.md` в памяти. Rein чётко зафиксировал:
> «подразумевается что это само будет при наличии ollama её запускать типо и выбирать загруженную модель или предлагать выбрать из списка загруженных моделей»

Конкретный план:

**1.1 `obsidian-plugin/src/ollama.ts`** — новый модуль по аналогии с `paths.ts`:
- `detectOllama()`: `where ollama` / `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` / `D:\Ollama\ollama.exe` / macOS `/opt/homebrew/bin/ollama`, `/usr/local/bin/ollama`.
- `ensureOllamaRunning(execPath)`: если 11434 не слушает — `spawn('ollama', ['serve'], { detached: true, stdio: 'ignore' })`. Health-poll каждые 500мс до 10с.
- `listLocalModels()`: уже есть в backend (`/viz/status.models_available`), плагин может использовать через `/viz/status`.

**1.2 Plugin orchestration** (`main.ts`):
- После `backend.start()` up → проверить `/viz/status.ollama_up`.
- Если false → `detectOllama()` → `ensureOllamaRunning()` → refresh status.
- Если up + `settings.modelName` НЕ в `models_available` → открыть inline model-picker (`bootstrap.ts`-like, но без билда).

**1.3 Race fix «Чат не подключён»**:
- Сейчас view рендерит плашку Ollama-hint при `!ollama_up` мгновенно при `onOpen`.
- Должен: ждать ~5-10с после открытия view, и только если за это время backend не сообщил ollama_up — рендерить плашку.
- Реализация: в `view.ts` после первого `/viz/status` если `!ollama_up` — запустить setInterval опрос, рендерить плашку только когда стабильно false 3 подряд.

**1.4 Model picker** (если model не из списка):
- Inline-плашка с radio-кнопками установленных моделей + кнопка «Скачать qwen2.5:14b» если список пуст.
- На клик: записать в settings, перезапустить backend.

### 2. 🔥 Live UX тест: интерпретация через ρ (~30 мин — harness готов)

Harness уже создан в этой сессии:
- `service/tests/test_interpretation.py` — pytest golden с метриками divergence
- `service/tests/interpret_cli.py` — интерактивный CLI
- `service/tests/interpretation_cases.json` — кейс «хлам» + шаблон

Прогнать на твоей карте 3-5 кейсов, посмотреть divergence_score. Если > 0.6 — interpretation lens работает; меньше — диагностика system prompt / top_n.

### 3. macOS-аналог `windowsSystemCandidates` (~1ч)
Иначе при попытке тестового онбординга на Mac будет тот же фейл что был у Python313 на Windows. Добавить:
- `/opt/homebrew/bin/python3`, `/usr/local/bin/python3`, `~/.pyenv/shims/python3`
- `/Applications/Python\ 3.*/IDLE.app` (CPython.org installer)

### 4. PyInstaller bundle (~6-10ч) — перенесено
Заменяет шаги 1, 5 из INSTALL_RU.md.

### 5. Silent_pool в Антураже (~1ч) — перенесено
Endpoint работает, чат не использует.

### 6. CM6 подсветка слов (~2-3ч) — перенесено
### 7. Нативный TS-граф без iframe (~3-4ч) — перенесено

---

## 🚦 Быстрый старт следующей сессии

```bash
# Тесты ядра (без изменений)
python -X utf8 -m core.test_invariants                # 125/125

# Smoke service (требует запущенного backend'а)
python -m uvicorn service.app:app --host 127.0.0.1 --port 8765 &
python -m pytest service/tests/test_smoke.py -v       # 11/11

# Interpretation harness — НОВОЕ в этой сессии
python -m service.tests.interpret_cli                 # interactive
python -m pytest service/tests/test_interpretation.py -v -s   # golden

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
    - Ollama auto-management — такой же блокер как автодетект Python.
    - Любой шаг «открой терминал и запусти X» = failed UX для не-технического взрослого.

---

## Откуда мы пришли (предыдущие сессии)

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
