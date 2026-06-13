# Следующая сессия — состояние проекта

## Обновлено: 2026-06-13 (вечер) — SESSION SUMMARY (MVP onboarding layer)

---

## 🔥 Что сделано за сессию 2026-06-13

Тонкий 4-слойный онбординг сверху ядра — превращает «работает только у Rein» в «новый человек открывает плагин, видит карту через ~2 мин». Ядро не трогали.

### Layer 1 — Backend SSE bootstrap

**`POST /viz/build_from_vault`** (`service/viz_router.py`) — стриминг прогресса первичного билда из vault'а:
- Паттерн `asyncio.to_thread` + `queue.Queue(maxsize=256)` для синхронной `vault_sync.run()` без блокировки event loop. Без этого FastAPI терял бы health-pings от плагина на 95 секунд.
- 9 пар start/end SSE events по `STAGE_WEIGHTS` (collect → prior → parse → provenance → materialize → deepen → export → render → save).
- `_state["space"]` ставится В WORKER'е до `q.put("done")` → `/viz/status` сразу up-to-date, view.reload() не делает лишний pickle.load.
- Защита от двойного старта: `_state["bootstrap_running"]` + `HTTPException(409)`.

**Graceful degradation:**
- `_get_space()` возвращает `(None, None)` при отсутствии cache (не 503). Защищены: `/viz`, `/viz/ask`, `/viz/concepts/.../sources`, `/viz/file_ingest`, `/viz/silent`.
- `/viz/ask` без Ollama → HTTP 200 + SSE `event:error` с русским текстом и hint_url, не 503.
- `/viz/status` расширен полем `bootstrap_running: bool`.

**`core/vault_sync.py`:**
- Опциональный параметр `progress_callback: Callable[[str, float, str], None]`.
- `STAGE_WEIGHTS` константа с весами на основе перфа 95с.
- `_emit()` хелпер — callback errors не ломают pipeline.
- CLI режим (без callback'а) работает как раньше.

### Layer 2 — Plugin: автодетекция путей

**Новый `obsidian-plugin/src/paths.ts`:**
- `getPluginAbsDir(app, manifest.dir)` — через `FileSystemAdapter.getFullPath`.
- `detectPython(pluginAbsDir, repoCandidate)` — 4 кандидата с testPython (3.10+). Учитывает Windows venv-в-bin (git-bash layout).
- `detectRepo(pluginAbsDir)` — 7 кандидатов: bundle, env, neighbouring, ~/FVSC, ~/Desktop/FVSC, ~/Documents/FVSC.
- `autoFillSettings(plugin)` — пишет в settings только что нашло; не перезаписывает заполненное.

**`settings.ts`** — переписан целиком:
- Все labels/desc на русский, без слов «venv», «uvicorn», «FastAPI».
- Под каждым из двух путей — async-блок `.fvsc-autodetect-hint`: либо «Найдено: PATH [Использовать]», либо «Не найдено автоматически — укажи путь вручную».

### Layer 3 — Plugin: bootstrap UX + graceful

**Новый `obsidian-plugin/src/bootstrap.ts`:**
- `BootstrapModal extends Modal`. Шаг 1: confirm «У тебя ещё нет карты. ~2 мин. [Построить] [Отмена]». Шаг 2: прогресс-бар + текст стадии, AbortController для cancel.
- SSE reading через `fetch().body.getReader()` + TextDecoder, ручной split по `\n\n`.
- `BootstrapModal.maybeShow(plugin, backend, onDone)` — статический метод, проверяет `/viz/status` и показывает модалку только если нет кэша + не идёт другой build.
- Pause/resume vault watcher на время билда (insurance — EXCLUDE_PREFIXES уже исключает _fvsc_concepts).

**`view.ts`** переписан:
- Конструктор расширен `getPlugin: () => FvscPlugin` и `getBackend: () => BackendController` (вместо хака `(app as any).plugins`).
- `onOpen` сначала `await fetch('/viz/status')`, потом:
  - `!status` → CTA «Движок карты не отвечает».
  - `!space_loaded` → CTA «Построить карту» (открывает BootstrapModal). iframe НЕ создаётся.
  - `!ollama_up` → оранжевая плашка `.fvsc-ollama-hint` над iframe.
- `reload()` теперь ререндерит весь view, не просто свопает iframe src.

**`backend.ts`** — RU error messages + `onConfigError?: () => void` callback в BackendOptions. ENOENT обработчик и failure path дёргают его → плагин открывает свои Settings.

**`vault_watcher.ts`** — public `pause()` и `resume()`. Флаг `paused` фильтруется в `schedule()`. Логи в DevTools console.

**`main.ts`** — orchestration:
- `await autoFillSettings(this)` ДО создания BackendController.
- BackendController получает `onConfigError: () => this.openOwnSettings()`.
- AntourageView получает getPlugin/getBackend.
- `watcher` теперь public field (для BootstrapModal).
- После `backend.start()` если up — setTimeout 1с → `BootstrapModal.maybeShow`.
- `openOwnSettings()` через полу-приватный `(this.app as any).setting.openTabById(this.manifest.id)`, fallback к Notice.

**`styles.css`** — добавлены `.fvsc-modal-buttons`, `.fvsc-progress-wrap/-bar/-stage`, `.fvsc-autodetect-hint`, `.fvsc-empty-cta`, `.fvsc-ollama-hint`. Используют Obsidian CSS-переменные.

### Layer 4 — Docs

- **`INSTALL_RU.md`** — 7-шаговая инструкция без техтерминов. ConceptNet шаг 4 (обязательный по решению пользователя).
- **`README.md`** — `> 🇷🇺 Установка на русском: [INSTALL_RU.md](./INSTALL_RU.md)` в самом верху.

---

## 📊 Метрики 2026-06-13

| | До | После |
|---|---|---|
| Тесты ядра (test_invariants) | 125/125 | 125/125 |
| Smoke service (test_smoke.py) | 11/11 | 11/11 |
| Эндпоинты /viz | 7 | 8 (+build_from_vault) |
| Файлов в obsidian-plugin/src | 5 | 7 (+paths.ts, +bootstrap.ts) |
| Размер бандла main.js | ~18 KB | 37.9 KB |
| Обязательные поля Settings для нового user'а | 2 | 0 (автодетект всегда пробует) |
| Ответы на нерабочие условия | 503 + красная ошибка | HTTP 200 + русский SSE error |

### Verified end-to-end

- `/viz/status` отдаёт новое поле `bootstrap_running` ✓
- `/viz/ask` без Ollama: HTTP 200 + русский SSE error ✓
- `npm run build` без ошибок TS ✓
- 11/11 smoke ✓ (требуют запущенного backend'а)
- 125/125 invariants ✓

### Не проверено в этой сессии

- Live build_from_vault на чистом vault'е через Obsidian UI (требует ~2-3 минуты UI-теста; первая задача следующей сессии).
- Автодетекция repo + python на чистой машине без `data.json`.

---

## 🎯 Открытые направления (приоритет сверху вниз)

### 1. 🔥 Live UI smoke (~20 мин)
Перезагрузить Obsidian, удалить `<vault>/.obsidian/plugins/fvsc-antourage/data.json` и `<vault>/_fvsc_cache.pkl`. Проверить:
- Settings заполнены автоматически.
- Status-bar становится зелёным.
- BootstrapModal всплывает через 3с.
- Прогресс-бар двигается, view рендерится после done.

### 2. 🔥 Silent_pool в Антураже (~1ч) — перенесено из 2026-06-06 roadmap
Silent_pool существует и endpoint работает, но Антураж не использует его в ответах. Нужно: блок «known silent concepts» в system prompt'е (`service/viz_session.py`), особый ответ на silent-термин.

### 3. CM6 подсветка слов в заметках (~2-3ч) — перенесено
Маркер `[[locate:путь.md#"конкретная фраза"]]`, плагин слушает SSE напрямую, `Decoration.mark` через CM6.

### 4. Нативный TS-граф без iframe (~3-4ч) — перенесено
cytoscape прямо в плагине, compound nodes для drill-down, прямой EventSource для SSE.

### 5. PyInstaller bundle (~6-10ч) — перенесено
Заменяет шаги 1, 5 из INSTALL_RU.md. `detectPython` уже первым кандидатом проверяет `<plugin>/python/python.exe` — bundle подцепится автоматически.

---

## 🚦 Быстрый старт следующей сессии

```bash
# Тесты ядра
python -X utf8 -m core.test_invariants                # 125/125

# Smoke service (требует запущенного backend'а)
python -m uvicorn service.app:app --host 127.0.0.1 --port 8765 &
python -m pytest service/tests/test_smoke.py -v       # 11/11

# Verification 6.2 (без Ollama)
curl -sN -X POST http://127.0.0.1:8765/viz/ask \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hi"}],"stub":false}'
# ожидание: event:error + event:done, HTTP 200

# Плагин: пересборка после правок TS
cd obsidian-plugin && npm run build && install-to-vault.cmd

# Live build через UI: см. Open направление 1
```

---

## 🧠 Архитектурные принципы (обновлено)

К предыдущим:

8. **MVP-граница = «новый человек видит свою карту без чтения документации»** (2026-06-13):
   - Любой шаг setup'а с техтерминами (venv, uvicorn) — failed UX (см. memory `feedback_mass_adoption.md`).
   - Любая ошибка должна вести к понятному действию пользователя, не к 503.
   - Bootstrap-флоу должен запускаться автоматически при отсутствии данных, без чтения CLI-документации.

9. **Долгие синхронные pipeline'ы в FastAPI = thread + queue** (2026-06-13):
   - Не блокируем event loop никогда. Worker в `asyncio.to_thread`, прогресс через `queue.Queue`.
   - asyncio.Queue не подходит — не thread-safe.
   - Backpressure через `put(timeout=1)` без зависания worker'а.

---

## Откуда мы пришли (предыдущие сессии)

### 2026-06-06 (вечер) — Provenance + plugin + live watcher
TypeScript-плагин с auto-spawn uvicorn. Per-file provenance (каждый Judgment знает .md-источник). silent_pool (51K токенов). Live vault watcher с debounce 1.5с. cytoscape.js граф вместо vis-network. См. memory.

### 2026-06-06 (утро) — антураж MVP-1
Антураж в браузере через `/viz`. SSE chat с маркерами `[[concept:X]]` синхронно с подсветкой узлов.

### 2026-06-05 — Sibling-FP fix
Coordination-aware parser; F1 79.3% → 80.7%, sibling_fp_rate 2.5% → 0.66%. См. memory.

### 2026-06-04 — FVSC Core Service
FastAPI обёртка, 11 endpoints, quantum retrieval через Tr(ρ_query·ρ_chunk), Markdown format adapter.

### 2026-05-31 — Empirical pivot
Тезаурус покрывает 80% узлов, 1.2% рёбер. Bonus-only стратегия закреплена. См. memory.
