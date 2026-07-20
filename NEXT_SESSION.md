# Следующая сессия — FVSC semantic atlas

## Состояние на 2026-07-21

- Активная ветка: `integration/fvsc-core-v1`.
- Draft PR: GitHub #2.
- `main` остаётся замороженной MVP-веткой; без явного решения не сливать.
- Последняя полная локальная проверка: **301 passed, 1 skipped, 11 deselected**.
- Каноническая основа остаётся `SourceDocument -> EvidenceLedger`; семантические
  представления являются заменяемыми, производными и source-cited views.

## Что сделано в завершённой сессии

1. В whitepaper записан языково-агностичный обзор фронтира представлений смысла.
   Вывод: универсального победителя нет; первый широкий schema baseline — UMR, DRS —
   формальный контроль, embeddings — retrieval baseline, density — только для
   размеченной неоднозначности.
2. Добавлены языково-нейтральные `LinguisticFrontendResult` и `SemanticGraphView` с
   точной привязкой к source revision, детерминированными digest и явными потерями.
3. Добавлен loss-aware импорт документированного UMR subset: token blocks, sentence
   graph, alignments и document relations. Импорт не пишет в EvidenceLedger и не делает
   parser guesses каноническими.
4. Добавлен публичный synthetic capacity probe на RU/DE/FR/EN:
   - `judgment_core`: micro-F1 `0.7692307692`, 5 пропущенных и 1 лишняя единица;
   - `umr`: micro-F1 `1.0`, без пропусков;
   - паритет на простом predicate/argument и отрицании;
   - структурная разница на modal conceiver, cross-sentence coreference и time.
5. Результат **не даёт права продвигать UMR**: parser/extraction исключён, gold специально
   содержит представимые UMR-факты, `promotion_eligible=false`.
6. Принято направление следующего эксперимента: не объявлять Gold 001–015 полным
   экзаменом, а строить Evaluation Atlas из вертикальных глубоких census и
   горизонтальных phenomenon/minimal-pair тестов.
7. Добавлены русская инструкция и рабочий шаблон глубокого semantic census.

## Сохранённые коммиты этой линии

- `ec2b0b0` — whitepaper: language-agnostic semantics frontier.
- `e91c9c9` — language-neutral graph contracts.
- `28bb522` — source-grounded UMR subset importer.
- `9cfd988` — frozen semantic capacity probe.

Следующий commit после этого handoff содержит census guide/template и актуализацию
памяти сессии.

## Главный следующий шаг

Создать первый **вертикальный deep semantic census** одного реального смыслонасыщенного
текста.

Пользователю не требуется самостоятельно выполнять полную разметку:

1. скопировать шаблон в `private_eval/deep_census/census-001.md`;
2. вставить текст/locator и при желании первое свободное понимание;
3. Codex выполняет первичную candidate-разметку, anchors, `M/R/G/N/Q`, несколько
   проходов насыщения и карту вопросов для review;
4. пользователь подтверждает только owner-sensitive намерения, авторские термины и
   допустимые/отвергнутые интерпретации;
5. после owner-review замораживается census v1 и вручную сравнивается ёмкость
   Judgment/Evidence, UMR, DRS и ambiguity-only density.

Инструкция:
`docs/evaluation/DEEP_SEMANTIC_CENSUS_GUIDE_RU.md`

Шаблон:
`docs/evaluation/DEEP_SEMANTIC_CENSUS_TEMPLATE_RU.md`

Рекомендуемое приватное рабочее место:
`private_eval/deep_census/census-001.md` — папка уже исключена из публикации общим
правилом `private_eval/*`.

## Правила следующей сессии

- Не превращать candidate-разметку модели в owner-gold автоматически.
- Не требовать от владельца формальных UMR/DRS обозначений; сначала естественно-языковое
  смысловое поле, затем mappings.
- Не смешивать три результата: representational capacity, automatic extraction и
  downstream/query utility.
- Не усреднять всё в один F1: публиковать профиль predicate/argument, scope, modality,
  time, coreference, attribution, ambiguity, abstention и provenance.
- Явно записывать `underdetermined` и запрещённые утверждения; отсутствие ложной
  уверенности является частью качества.
- Новые gold revisions добавлять версиями; старые результаты не переписывать.
- Не публиковать сырой личный текст, actor identities, локальные абсолютные пути или
  generated owner-review journals.

## Быстрые команды

```powershell
$env:PYTHONPATH='src'
python -m pytest -q
python scripts/semantic_schema_probe.py

New-Item -ItemType Directory -Force private_eval/deep_census
Copy-Item docs/evaluation/DEEP_SEMANTIC_CENSUS_TEMPLATE_RU.md `
  private_eval/deep_census/census-001.md
```

## Текущая научная формулировка

FVSC строит не одну универсальную структуру смысла, а provenance-grounded semantic atlas.
Для ограниченного текста и контекста создаётся максимально насыщенное, открытое поле
смысловых единиц. Каждая математическая структура проверяется по тому, какую часть этого
поля она различимо, вычислимо и без ложных утверждений сохраняет.
