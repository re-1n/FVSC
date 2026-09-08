# FVSC Antourage — Obsidian plugin

Frontend для FVSC Antourage. Запускает локальный FastAPI-бэкенд (Python) и встраивает
визуализацию семантической карты + чат с LLM прямо во вкладку Obsidian.

## Зависимости

- Python 3.10+ с зависимостями из [requirements.txt](../requirements.txt); этот порог проверяет автодетект плагина.
- Node.js и npm для сборки из исходников.
- Для чата — локальный Ollama с выбранной моделью (тег по умолчанию `qwen2.5:14b-instruct-q4_K_M`). Для карты Ollama не обязательна.
- Карту можно построить при первом запуске через «Построить карту»; предварительный ручной cache не обязателен.

Подробная [инструкция установки](../INSTALL_RU.md). Загрузка зависимостей и моделей требует интернета. [Ограничения ядра](../docs/KNOWN_LIMITATIONS.md) относятся и к отображаемой карте.

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

- Команда **«Open Antourage»** (или иконка в ribbon) → открывает вкладку с графом + чатом.
- Спросить в чате что-нибудь про vault → LLM стримит ответ, концепты подсвечиваются на карте.

## Что дальше

Текущие приоритеты: [следующая сессия](../NEXT_SESSION.md) и [план развития](../docs/ROADMAP.md). Готовность установки проверяется отдельно на чистом окружении; зелёные тесты ядра не заменяют проверку пути нового пользователя.
