# Следующая сессия — состояние проекта

## Обновлено: 2026-04-01 (v0.7.2)

## Что сделано за сессию 2026-04-01

### 1. Аудит кода (полный)
- Проверены все 6450 строк, 18 модулей
- Найдена проблема: смешение масштабов в recursive_deepen (rho_direct trace≠rho_recursive trace) — **не исправлено**, нужно дизайн-решение (нормализовать или нет?)
- Ложные срабатывания отсеяны: trace_inner_product `np.sum(A * B.T)` = `Tr(A·B)` — корректно

### 2. clause_type — эпизодическое↔семантическое (XVIII.5)
- Новое поле `Judgment.clause_type` ("GENERIC"|"HABITUAL"|"EPISODIC"|"UNKNOWN")
- Propagation через все 3 сайта создания Judgment в tree_extractor.py
- EPISODIC суждения стартуют с ×0.7 веса в materialize_judgment
- `Concept.rho_semantic()` — ρ без эпизодических компонентов
- Whitepaper: секция 18.5 с источниками (Tulving 1972, Rubin 2022, Broekaert & Busemeyer 2017, eNeuro 2022)
- Исправлен хрупкий `and/or` идиом → тернарный оператор в copular condition_role

### 3. Расширенный eval set (199 предложений)
- `core/gold_extended.py` — 199 реальных предложений из 3 Telegram-чатов (key7, sqmos, shkshotr)
- `evaluation.py --extended` — запуск с расширенным набором
- **Ожидает ручную разметку** (все `[]` пока)

### 4. Калибровка нормализатора
- `core/normalizer_calibration.py` — фреймворк + runner
- Выявлено: 14 опечаток не ловятся (отрийание, ассицировал, ммне...), 3 сленга нет в словаре (тг, тгк, ирл)
- 9 FAIL, 7 TODO (ждут подтверждения), 17 PASS
- **Ожидает ручную калибровку**

---

## Приоритеты для следующей сессии

### 1. Калибровка нормализатора (ПЕРВЫЙ ШАГ)
- Открыть `core/normalizer_calibration.py`
- Заполнить `None` → правильный текст
- Решить: мат нормализовать? тг→телеграм? бро→брат?
- Добавить KNOWN_MISSPELLINGS и MISSING_SLANG в text_normalizer.py
- Цель: 0 FAIL в `python -X utf8 normalizer_calibration.py`

### 2. Разметка eval set (ПОСЛЕ нормализатора)
- Открыть `core/gold_extended.py`
- Для каждого из 199 предложений вписать ожидаемые S→V→O
- Запуск: `python -X utf8 evaluation.py --extended`
- Цель: baseline F1 на реальных чат-данных

### 3. recursive_deepen масштабы (дизайн-решение)
- rho_direct (trace=масса) vs rho_recursive (trace=avg соседей) → blend некорректен
- Варианты: нормализовать rho_recursive до trace(rho_direct), или оставить как есть
- Нужна дискуссия

### 4. T11: Морфологическое ядро
- pymorphy2 вместо spaCy dep-parser в L0
- Параллельный адаптер (T12) или замещающий?
- Начинать ПОСЛЕ расширения eval set (нужен надёжный baseline для сравнения)

---

## Открытые исследовательские вопросы

| № | Вопрос | Статус |
|---|---|---|
| T1 | PMI / ко-окуренция | Открыто |
| T3 | DisCoCat — тензор глагола | Исследовательский |
| T8 | Тензорное произведение пространств | v2+ |
| T11 | Морфологическое ядро (замена spaCy dep-parse) | **Приоритет** |
| T12 | Универсальная архитектура (pluggable adapters) | Открыто |

---

## Ключевые метрики (v0.7.2)

| Метрика | Значение |
|---|---|
| Evaluation F1 | 75.3% (51 предложение, base) |
| Extended eval set | 199 предложений (не размечены) |
| Convergence | α=0.7→k=6, α=0.8→k=5 |
| Scale test | 1002 текста, 363 суждения, 7117 concepts |
| recursive_deepen | 175s на 7117 concepts |
| Пиковая память | 910 MB |

---

## Как запустить

```bash
# Юнит-тест
cd core && python -X utf8 test_poc.py

# Evaluation (base: 51 предложение)
cd core && python -X utf8 evaluation.py

# Evaluation (extended: 250 предложений)
cd core && python -X utf8 evaluation.py --extended

# Калибровка нормализатора
cd core && python -X utf8 normalizer_calibration.py

# Convergence sweep
cd core && python -X utf8 test_convergence.py

# Scale test
cd core && python -X utf8 test_scale.py "../экспорты чатов/result глубокий (Davurr and Sqmos).json" 2000 Davurr
```
