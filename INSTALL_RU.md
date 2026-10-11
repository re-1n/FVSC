# Установка FVSC Antourage

FVSC локально синхронизирует Markdown-vault, ищет исходные заметки и может просить
Ollama предложить проверяемую интерпретацию. Ответ модели разбит на claims с цитатами;
он не становится вашей канонической памятью автоматически.

## Что понадобится

- Python 3.10+;
- Obsidian — если нужен плагин;
- Ollama — только для интерпретаций, обычный поиск работает без неё;
- Node.js 18+ — только если вы собираете плагин из исходников.

## 1. Python и зависимости

В корне FVSC:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Отдельный ConceptNet-файл для чистого рабочего пути не нужен. Density/ContainerCore
сохранены как экспериментальные представления, но не являются каноническим хранилищем.

## 2. Ollama (необязательно)

Установите [Ollama](https://ollama.com/download) и один раз скачайте модель:

```bash
ollama pull qwen2.5:14b-instruct-q4_K_M
```

FVSC обращается только к явно локальному адресу Ollama (`127.0.0.1`/`localhost`). Если
Ollama выключена, синхронизация и lexical-поиск продолжают работать.

## 3. Ручная проверка сервиса

Сначала можно создать cache:

```bash
PYTHONPATH=src python -m fvsc.ingest.vault_sync \
  --vault "/путь/к/vault" --exact-judgments
```

Linux/macOS:

```bash
FVSC_VAULT_PATH="/путь/к/vault" \
FVSC_LLM_MODEL="qwen2.5:14b-instruct-q4_K_M" \
python -m uvicorn fvsc.service.app:app --app-dir src \
  --host 127.0.0.1 --port 8765
```

Windows PowerShell:

```powershell
$env:FVSC_VAULT_PATH = "D:\Notes\MyVault"
$env:FVSC_LLM_MODEL = "qwen2.5:14b-instruct-q4_K_M"
python -m uvicorn fvsc.service.app:app --app-dir src --host 127.0.0.1 --port 8765
```

Откройте `http://127.0.0.1:8765/health`. Сервис намеренно привязывается только к
loopback-интерфейсу.

## 4. Сборка и установка Obsidian-плагина

```bash
cd obsidian-plugin
npm install
npm run build
```

Скопируйте в `<vault>/.obsidian/plugins/fvsc-antourage/`:

- `main.js`;
- `manifest.json`;
- `styles.css`.

В Obsidian включите Community plugins → FVSC Antourage. Плагин пытается сам найти
Python и репозиторий. Если не получилось, укажите их в настройках плагина.

## 5. Первый запуск и реальный тест

1. Откройте панель **FVSC Antourage**.
2. Нажмите **Синхронизировать**. Сервис создаст `.fvsc/cache.json` внутри vault.
3. Введите вопрос и сначала нажмите **Найти источники**: проверьте, что открываются
   действительно нужные заметки.
4. Нажмите **Интерпретировать**. Для каждого claim откройте citations.
5. Отдельно нажмите **Принять** или **Отклонить**, затем сохраните оценку.

Это и есть нужный реальный тест архитектуры: не «похоже ли объяснение на умное», а
отражает ли каждый claim вложенный вами смысл и не склеивает ли мысли, которые должны
оставаться раздельными.

## Что сохраняется

- `.fvsc/cache.json` — ledger и производное состояние без сырых тел заметок;
- `.fvsc/interpretations.json` — сгенерированные claims, source revisions/hashes и ваши
  решения; исходные тексты туда не копируются.

Оба файла локальные, создаются атомарно и исключены из сканирования vault.

## Если что-то не работает

### `FVSC: failed`

Проверьте пути Python и FVSC в настройках плагина. После изменения нажмите
**Перезапустить движок**.

### Ollama недоступна

Запустите приложение/daemon Ollama и проверьте:

```bash
ollama list
```

Имя выбранной модели должно совпадать с одной из установленных. Модель можно сменить в
панели или настройках FVSC и перезапустить сервис.

### `source revision changed` или `synchronize first`

Заметка изменилась после построения cache. Нажмите **Синхронизировать**; FVSC не будет
подставлять новый текст под старую citation.

### Синхронизация медленная

Текущий watcher специально использует корректный full-source reconcile, схлопывая
серию правок debounce-таймером. Source-scoped оптимизация запланирована после измерения
реальной задержки; она не должна менять смысл или lifecycle.

### Диагностика

Откройте Obsidian Developer Console (`Ctrl/Cmd+Shift+I`). Сообщения плагина имеют
префиксы `[fvsc-backend]`, `[fvsc-watch]`, `[fvsc-ollama]`.
