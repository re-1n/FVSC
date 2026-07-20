# Deep semantic census — рабочий шаблон

> Скопируйте файл в `private_eval/deep_census/`. Не коммитьте личный исходный текст.
> Для начала достаточно заполнить только раздел 0; остальное может разметить Codex.

## 0. Передача текста

- Census ID: `census-___`
- Название:
- Язык:
- Автор/голос, если известен:
- Локальный source ID или путь:
- Дата/контекст создания, если важны:
- Текст для разметки либо точный locator:

```text
[ВСТАВИТЬ ТЕКСТ ИЛИ LOCATOR]
```

- Моё первое понимание текста (необязательно):
- Особенно важно не потерять (необязательно):
- Что я сам пока не понимаю (необязательно):

## 1. Границы и ревизия

- Source revision / SHA-256:
- Разрешённый контекст: `text_only | local_thread | named_sources | owner_memory`
- Разрешённые дополнительные источники:
- Внешнее мировое знание: `none | common_only | named_knowledge_base`
- Максимальная глубина вывода:
- Разметчик/модель и версия:
- Дата начала:
- Статус: `draft | candidate_complete | owner_reviewed | frozen`

## 2. Первое целостное чтение

- Ядро текста:
- Коммуникативная цель:
- Главная напряжённость/противопоставление:
- Эмоциональный или прагматический эффект:
- Что текст принципиально оставляет открытым:
- Самая опасная ложная интерпретация:

## 3. Source anchors

Создавайте anchor для минимального достаточного фрагмента. Для чувствительного текста
можно оставить только locator и digest без цитаты.

### A001

- Locator: `[source_id#char=start:end | lines | message-id]`
- Короткий фрагмент или digest:
- Голос: `owner | participant | quoted | narrator | lyric | external | unresolved`
- Примечание:

<!-- Дублируйте блоки A002, A003... -->

## 4. Участники, сущности, события и состояния

### E001

- Тип: `person | group | object | concept | event | state | time | place | proposition`
- Нейтральное имя:
- Anchors:
- Референция определена?: `yes | no | partial`
- Возможные кореференты:
- Примечание:

<!-- Дублируйте блоки E002, E003... -->

## 5. Смысловые единицы

### M001

- Нормализованная формулировка:
- Статус: `explicit | entailed | presupposed | defeasible | interpretive | underdetermined | rejected`
- Anchors:
- Участники (`E*`):
- Чей голос/позиция:
- Полярность: `positive | negative | mixed | not_applicable`
- Модальность: `actual | possible | necessary | desired | feared | hypothetical | unknown`
- Время/интервал:
- Условие:
- Зависит от внешнего знания?:
- Уверенность разметчика: `high | medium | low`
- Owner decision: `not_reviewed | confirmed | rejected | open | not_applicable`
- Почему это извлекается из текста:
- Что могло бы опровергнуть это чтение:

<!-- Дублируйте блоки M002, M003... -->

## 6. Отношения между единицами

### R001

- Source: `M___ | E___`
- Relation: `causes | enables | prevents | before | after | overlaps | corefers | part_of | contrasts | contradicts | attributes_to | condition_for | elaborates | symbolizes | other`
- Target: `M___ | E___`
- Anchors:
- Статус: `explicit | entailed | defeasible | interpretive`
- Направление существенно?: `yes | no`
- Owner decision: `not_reviewed | confirmed | rejected | open | not_applicable`
- Примечание:

<!-- Дублируйте блоки R002, R003... -->

## 7. Альтернативные прочтения

### G001

- Вопрос неоднозначности:
- Варианты (`M*`):
- Совместимость: `mutually_exclusive | partially_compatible | all_can_hold`
- Что различает варианты:
- Может ли текст разрешить выбор?: `yes | no | partially`
- Owner decision: `one_selected | several_valid | intentionally_open | not_reviewed`
- Выбранные варианты:
- Комментарий владельца:

## 8. Запрещённые и неподтверждаемые утверждения

### N001

- Утверждение, которое система не должна выдавать как факт:
- Причина: `contradicted | wrong_voice | modality_loss | insufficient_source | over_inference | rejected_reading | other`
- Связанные anchors / `M*`:
- Допустимый ответ системы: `abstain | qualify | offer_alternatives | correct_voice`
- Owner decision: `not_reviewed | confirmed | rejected | not_applicable`

<!-- Дублируйте блоки N002, N003... -->

## 9. Проверочные запросы

### Q001

- Вопрос к представлению:
- Необходимые единицы (`M*`, `R*`, `G*`, `N*`):
- Минимально правильный ответ:
- Обязательная оговорка/воздержание:
- Требуемые citations:
- Недопустимый ответ:

<!-- Дублируйте блоки Q002, Q003... -->

## 10. Контроль покрытия

Отметьте `covered`, `absent`, `open` или `not_applicable`.

| Категория | Статус | IDs / комментарий |
|---|---|---|
| Предикаты и роли | | |
| Отрицание и scope | | |
| Модальность и conceiver | | |
| Условия и контрфактуальность | | |
| Время и порядок событий | | |
| Причинность | | |
| Кореференция | | |
| Голос, цитата и авторство | | |
| Пресуппозиции | | |
| Прагматические выводы | | |
| Метафоры | | |
| Эмоции/оценки | | |
| Альтернативные прочтения | | |
| Неопределённость и abstention | | |
| Owner-specific смысл | | |

## 11. Журнал насыщения

| Раунд | Линза/метод | Новые `M/R/G/N` | Новые категории | Исправлено/отклонено | Заметки |
|---:|---|---:|---:|---:|---|
| 1 | целостное чтение | | | | |
| 2 | буквальная и логическая | | | | |
| 3 | дискурс, время, голоса | | | | |
| 4 | прагматика и метафоры | | | | |
| 5 | owner-review | | | | |

- Остановочный критерий выполнен?:
- Известные непокрытые области:
- Что следует проверить другим разметчиком/моделью:

## 12. Owner-review и заморозка

- Проверены IDs:
- Подтверждены:
- Отклонены:
- Оставлены открытыми:
- Комментарий владельца:
- Версия census:
- Digest замороженного файла:
- Дата решения:

## 13. Карта покрытия архитектурами — заполняется после gold-review

Значения: `native | composed | opaque | collapsed | forced | lost | not_tested`.

| ID | Judgment/Evidence | UMR view | DRS control | Density overlay | Итог/потеря |
|---|---|---|---|---|---|
| M001 | | | | | |
