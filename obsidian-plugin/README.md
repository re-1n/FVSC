# FVSC Antourage — Obsidian plugin

Frontend для FVSC Antourage. Запускает локальный FastAPI-бэкенд (Python) и встраивает
визуализацию семантической карты + чат с LLM прямо во вкладку Obsidian.

## Зависимости

- Python 3.11+ с FVSC репо (см. `requirements.txt` в корне).
- Локальный Ollama с моделью, указанной в настройках (по умолчанию `qwen2.5:14b-instruct-q4_K_M`).
- Один раз построенный `_fvsc_cache.pkl` в корне vault'а:
  ```bash
  python -m core.vault_sync --top 100
  ```

## Сборка плагина

```bash
cd obsidian-plugin
npm install
npm run build      # → main.js
```

## Установка в vault

В директории `<vault>/.obsidian/plugins/` создать папку `fvsc-antourage/` и положить туда:

- `manifest.json`
- `main.js` (после сборки)
- `styles.css`

Включить плагин в Settings → Community plugins.

## Настройка

Settings → FVSC Antourage:

- **Python interpreter** — путь к `python.exe` в venv FVSC.
- **FVSC repo path** — путь к корню репозитория FVSC (cwd для uvicorn).
- **Port** — порт uvicorn, по умолчанию 8765.
- **LLM model** — Ollama-тег модели.
- **Auto-start backend** — поднимать ли FastAPI при загрузке плагина.

После настройки нажать «Restart backend» (или перезагрузить плагин).
Статус виден в status bar внизу: `● FVSC: up` зелёный = всё ок.

## Использование

- Команда **«Open Antourage»** (или иконка в ribbon, или ribbon) → открывает вкладку с графом + чатом.
- Спросить в чате что-нибудь про vault → LLM стримит ответ, концепты подсвечиваются на карте.

## Что дальше

См. `NEXT_SESSION.md` в корне репо: live vault-watch (этап 2), подсветка слов
в заметках через CodeMirror (этап 3), нативный рекурсивный граф (этап 4),
PyInstaller bundle для mass-adoption (этап 5).
