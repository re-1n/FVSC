# Следующая сессия — состояние проекта

## Обновлено: 2026-03-30 (v0.7.1)

## Что сделано за сессию 2026-03-29/30

### Whitepaper: спектр формализуемой интерпретации (XVII.1)

Секция XVII.1 полностью переписана. Вместо 3 грубых слоёв (L0/L1/L2) — 6 уровней формализуемой интерпретации с академическими ссылками для каждого:

- **L0**: Синтаксическая стенография (S→V→O из синтаксиса)
- **L0.5**: Пресуппозиции и логические следствия (Stalnaker, Karttunen, Kiparsky)
- **L1**: Конвенциональные и скалярные импликатуры (Grice, Horn, Levinson, Potts)
- **L1.5**: Фреймовая активация (Fillmore, Baker, Lyashevskaya/Kashkin RuFrameNet)
- **L2**: Дискурсивные связи (Mann & Thompson RST, Asher SDRT, Pisarevskaya русский RST)
- **L2.5**: Детекция метафоры (Lakoff & Johnson, Wilks, Shutova, Steen MIPVU)
- **L3**: Мировое знание и LLM (Sperber & Wilson, Fodor модулярность)

21 новых академических источников в XVI. Обновлены: Принцип, IV, XII, XIV, XV, XVI.

### Код: этапы 1–4

**v0.5.2** — 5 code fixes: C1 (type annotations), C2 (is_verb field), C8 (entropy guard), C10 (дубликаты), C11 (vector reuse).

**v0.5.3** — 3 critical fixes: C3 (timestamp from time.time(), Telegram dates passed), C4 (archived в queryable), C9 ([self] в concepts dict).

**v0.6.0** — Рефакторинг: C5 (shared _collect_and_emit), C7 (core/ = Python-пакет), T2 (extraction_confidence).

**v0.7.0** — Тестирование: T4 (convergence sweep, все alpha сходятся), T9 (evaluation: P=79.5%, R=71.4%, F1=75.3%), T7 (scale test скрипт).

**v0.7.1** — Оптимизация recursive_deepen: candidate-index (judgment-linked + top-200 by mass). 7117 concepts: ∞ → 175s.

### Все C1–C11 закрыты

Все вопросы качества кода из ревью 2026-03-28 решены.

### Архитектурная дискуссия: замена spaCy dep-parse

Обсуждена и формализована концепция **морфологического ядра** (T11):
- spaCy dep-parser = нейросеть в сердце L0. 7-12% ошибок на чатах. Нарушает стенографический принцип фактически.
- Идеальное L0: pymorphy2 (rule-based морфология) + падежная грамматика + словарь валентностей (Апресян) + самодизамбигуация через накопленный контекст (anomaly_score).
- Ноль нейросетей в ядре. Детерминизм. Улучшается с данными без обучения.
- Работает даже на выдуманных словах (пример Щербы).
- Академическое обоснование: Fillmore 1968, Mel'čuk 1974, Apresjan 1995, Zaliznyak 1977.

Обсуждена **универсальная архитектура** (T12):
- Density matrix core уже универсальна (язык-агностична).
- Языкоспецифичен только extraction layer (тонкий pluggable adapter).
- Русский = первый адаптер. Далее — английский, другие.
- В систему можно загружать не только персональную семантику, но и знания из текстов.

---

## Приоритеты для следующей сессии

### 1. T11: Морфологическое ядро (ВЫСОКИЙ)

Реализовать pymorphy2-based extractor как замену spaCy dep-parse в L0:
- pymorphy2 для морфологии (лемма, падеж, аспект, наклонение)
- Падежная грамматика: NOM+V+ACC → S→V→O, NOM+V+GEN → S→V→O (для глаголов с род.п.)
- Словарь валентностей (конечный ресурс, не нейросеть)
- Самодизамбигуация через anomaly_score при морфологической омонимии
- Clause segmentation по пунктуации + союзам
- spaCy → опциональный L1 fallback
- Сравнить с текущим tree_extractor по evaluation set (T9)

### 2. Evaluation: улучшить F1

Текущий F1=75.3%. Паттерны ошибок:
- Лемматизация (люди→человек): нормализовать при сравнении
- Passive inversion: улучшить для краткого причастия
- Непереходные глаголы: расширить fallback на xcomp с pos_=VERB
- Модальный+именной предикат: обработать "должен быть свободен"

### 3. T12: Pluggable language adapter (СРЕДНИЙ)

Абстрагировать extraction layer от density matrix core. Определить интерфейс adapter'а.

### 4. Антураж: архитектура prompt'а

Как дать 7B-модели достаточно контекста без перегрузки.

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

## Ключевые метрики (v0.7.1)

| Метрика | Значение |
|---|---|
| Evaluation F1 | 75.3% (51 предложение) |
| Convergence | α=0.7→k=6, α=0.8→k=5 |
| Scale test | 1002 текста, 363 суждения, 7117 concepts |
| recursive_deepen | 175s на 7117 concepts (было: ∞) |
| Пиковая память | 910 MB |

---

## Файлы проекта

| Файл | Строк | Назначение |
|---|---|---|
| `FVSC whitepaper.md` | ~2600 | Спецификация (I–XVIII + App A) |
| `core/density_core.py` | ~800 | Ядро: density matrices, decay, layers, comparison |
| `core/tree_extractor.py` | ~750 | Рекурсивное извлечение суждений |
| `core/context_classifier.py` | ~430 | Контекстная классификация NP |
| `core/feedback.py` | ~280 | FeedbackEngine: вопросы + ответы |
| `core/antourage_server.py` | ~460 | HTTP-сервер: карта + Ollama + persistence |
| `core/interactive_map.py` | ~830 | Интерактивная HTML-карта |
| `core/live_test.py` | ~430 | Telegram pipeline |
| `core/evaluation.py` | ~300 | T9: evaluation framework (51 gold sentences) |
| `core/test_convergence.py` | ~160 | T4: convergence sweep |
| `core/test_scale.py` | ~200 | T7: масштабное тестирование |
| `core/text_normalizer.py` | ~305 | Нормализация чатового текста |
| `core/thesaurus_loader.py` | ~245 | ConceptNet + RuWordNet |
| `TEST_RESULTS.md` | ~100 | Результаты тестирования |

## Как запустить

```bash
# Юнит-тест
cd core && python -X utf8 test_poc.py

# Evaluation (нужен spaCy)
cd core && python -X utf8 evaluation.py

# Convergence sweep
cd core && python -X utf8 test_convergence.py

# Scale test
cd core && python -X utf8 test_scale.py "../экспорты чатов/result глубокий (Davurr and Sqmos).json" 2000 Davurr

# Демо feedback
cd core && python -X utf8 demo_feedback.py
```
