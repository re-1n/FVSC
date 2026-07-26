# Следующая сессия — FVSC guarded semantic context

## Состояние на 2026-07-26

- Активная ветка: `integration/fvsc-core-v1`.
- Ветка опережает `origin/integration/fvsc-core-v1` на **6 коммитов** до handoff-коммита.
- Draft PR: GitHub #2. Ничего не сливать в `main` без отдельного решения.
- Рабочее дерево перед handoff чистое.
- Последняя полная локальная проверка:
  **334 passed, 1 skipped, 11 deselected**.
- Каноническая основа не изменилась:
  `SourceDocument -> EvidenceLedger`. Census, atomic groups, embeddings и compiled
  contexts — производные, заменяемые и source-cited views.

## Что завершено

### 1. Первый deep semantic census заморожен

- Приватный двухсторонний dialogue census полностью проверен обоими участниками.
- Статус: `private-participant-gold-v1`.
- Parent freeze:
  `private_eval/deep_census/dialogue-census-001-freeze-v1.md`.
- Открыты только явно сохранённые неопределённости памяти/конкретики.
- Разрешено локальное тестирование понимания смыслов. Публикация, GitHub, передача
  исходного текста наружу и расширение цели не разрешены.

### 2. Guarded context compiler

Публичный compiler теперь поддерживает:

- детерминированный character cosine baseline;
- character TF-IDF ablation;
- reviewed/candidate retrieval cues, которые не рендерятся как evidence;
- валидируемые external scores для локальных embedding-кандидатов;
- минимальный score как fail-closed control;
- неделимые guards и mandatory corrections;
- отдельные optional related links;
- per-question evidence isolation;
- `require_positive` / `INSUFFICIENT_CONTEXT`;
- atomic reviewed groups с `parent_group_id` и `selectable=false`;
- ограниченный `related_depth`;
- дедупликацию primary/guard/correction units.

Ключевые файлы:

- `src/fvsc/retrieval/context_compiler.py`
- `docs/evaluation/CONTEXT_RANKER_CUES_PROBE.md`
- `docs/evaluation/ATOMIC_GROUP_COMPILATION.md`

### 3. Ranker ablations

Retrieval-only результаты на замороженном диалоге:

| Arm | Macro oracle recall | Решение |
|---|---:|---|
| character cosine, budget 500 | 0.683 | baseline |
| character TF-IDF | 0.733 | не продвигать: небезопасно заполнил Q04 |
| TF-IDF + floor 0.20 | 0.650 | отклонён |
| Qwen3-Embedding 0.6B | 0.533 | отклонён |
| Qwen3-Embedding + task instruction | 0.533 | отклонён |
| blinded candidate cues | 0.733 | не reviewed; не продвигать |
| cosine, budget 700 | 0.757 | только cost ablation |
| owner-reviewed atomic + depth 2, budget 500 | 0.757 | retained view |

Ни TF-IDF, ни embeddings, ни cues не продвинуты. Density matrices по этим ошибкам
по-прежнему не оправданы.

### 4. Локальная embedding-модель

- Установлена в существующее Ollama-хранилище на диске D:
  `qwen3-embedding:0.6b`.
- Локальное Ollama-хранилище: `D:\ollama models`. Если стандартный daemon показывает
  пустой список, запускать отдельный loopback daemon с `OLLAMA_MODELS` на это хранилище;
  не считать модели отсутствующими только по default `ollama list`.
- Digest:
  `ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d`.
- Размер около 639 MB, embedding dimension 1024.
- Добавлен loopback-only `/api/embed` adapter с проверкой batch, dimensions и finite
  values.
- Модель остаётся ablation, не default.

### 5. Owner-reviewed atomic G001

Монолитный безопасный bundle Q04 занимал 671 estimated tokens и не помещался в budget
500. `G001` разложен на пять derived children:

- `G001.A_MECHANISM`
- `G001.B_COMPOSITION`
- `G001.FRAME_RELATION`
- `G001.A_ADOPTION`
- `G001.B_RECEPTION`

Владелец принял все пять формулировок и подтвердил их совместную полноту. Freeze:

- `private_eval/deep_census/atomic-g001-freeze-v1.json`
- `private_eval/deep_census/atomic-g001-derivation-review.md`

Parent census не изменён. `G001` остаётся provenance-parent, но не участвует в ranking.
Q04 теперь компилируется в 479 estimated tokens и сохраняет различие:

- radical level A участницей принят;
- supportive paint metaphor B не принята;
- тогда B переживалась как навязанное неудачное утешение;
- позднее отношение стало нейтральным.

### 6. Generation diagnostics

Итоговый post-dedup atomic v15:

- Run: `.fvsc/dialogue_ablation/18ff4589360fc096`
- raw + locators: **7 accepted, 3 partial, 0 rejected**
- atomic FVSC: **9 accepted, 1 partial, 0 rejected**
- prompt: raw 5,116; atomic FVSC 4,656 (**−9%**)
- это один приватный диалог, одна модель и один seed; общей superiority не заявлять.

После bounded two-hop retrieval Q07 получил `M017` и `M029` в одном 492-token block:

- retrieval recall вырос;
- generation всё равно опустила тактильность;
- Run: `.fvsc/dialogue_ablation/e04069aaa7271eac`.

Следовательно, Q07 теперь классифицирован как **downstream synthesis/coverage failure**,
а не retrieval или storage failure.

## Коммиты незапушенного tranche

- `9bf34e0` — auditable ranker candidates + local embedding adapter.
- `c47ce74` — ranker/budget ablation record.
- `52a3d2e` — atomic reviewed groups.
- `975c10c` — mandatory-unit deduplication.
- `9bf9d89` — bounded typed related traversal.
- `ccc5b52` — owner-reviewed atomic result.

Следующий коммит после них — этот handoff/status checkpoint.

## Главный следующий шаг

Обновление 2026-07-26: публичный synthetic coverage gate выполнен и **не пройден**.
Baseline и coverage получили macro required-facet recall 1.000; citation correctness
снизилась с 1.000 до 0.933; обе arms ошибочно выбрали zinc coating в abstention-case.
Минимальный coverage contract отклонён. Приватный Q07 не повторять. Следующий шаг —
на публичных данных локализовать abstention/answer-claim consistency failure и только
затем preregister новую synthesis operation.

Второе обновление 2026-07-26: public claim-first consistency gate **пройден** на восьми
synthetic cases. Required recall сохранился 1.000, abstention accuracy вырос с 0.625
до 1.000, prohibited violations снизились с 2 до 0. Разрешён ровно один диагностический
повтор приватного Q07 с frozen claim-first operation. Результат сохранить независимо
от исхода; prompt по приватному ответу не менять.

Приватный Q07 diagnostic выполнен один раз. Результат **partial**: обе нужные units
были процитированы, тактильность восстановлена, но явное различие «сначала понимание,
не переходить сразу к решению» снова сокращено и вторая часть опущена. Разрешённый
повтор израсходован. Q07 больше не запускать и prompt по нему не настраивать.
Следующая задача — публичный горизонтальный phenomenon atlas для compositional
multi-facet coverage.

Coverage atlas v1 выполнен. Baseline macro required recall = 0.958, claim-first =
0.583. Claim-first безопасен по unsupported/prohibited, но ошибочно воздержался в
5/12 положительных cases, поэтому как global default отклонён. Hard/easy gaps для
temporal contrast, conditional scope и distributed rationale равны; выбирать один
post hoc нельзя. Нужен versioned public atlas extension, v1 не изменять.

Atlas v2 extension выполнен: baseline recall 1.000, claim-first 0.667. Temporal hard
paraphrases прошли, conditional и distributed-rationale hard paraphrases дали по два
over-abstention failure; tie сохранился, отдельный phenomenon не выбран. Следующий
candidate — public held-out requirement-to-claim coverage map, который отделяет
question decomposition, relation support и deterministic rendering.

Held-out end-to-end requirement coverage gate не пройден: recall 0.500, 6 schema
errors, 7 status errors. Правильные claims часто были потеряны fail-closed из-за
несогласованной индексной linkage-карты. Следующий controlled ablation: frozen
question plan на входе и ровно один supported/unsupported cited slot на requirement.
Это тест synthesis capacity, не автоматического planner.

Frozen-plan slot ablation выполнен: после безопасной normalization только exact
proposition-free unsupported sentinel получены recall 1.000, abstention 1.000,
citations 1.000, unsupported/prohibited 0. Strict schema errors были 4, tolerant 0.
Это локализует bottleneck в automatic question planning/linkage. Следующий этап —
отдельный public planner-only evaluation против frozen question-only plans; только
после него возможен новый held-out end-to-end gate.

Не продолжать настройку ranker на этом диалоге.

Следующая зарегистрированная задача — **coverage-aware synthesis**:

1. создать публичные synthetic fixtures, где один вопрос требует 2–3 независимых,
   source-cited facets;
2. сравнить обычный one-shot answer с минимальным coverage contract;
3. coverage contract не должен превращать каждый selected unit в обязательное
   утверждение: guards, alternatives и optional/caveated facets различаются;
4. измерять facet recall, unsupported facet rate, citation correctness, abstention,
   prompt/output tokens и latency;
5. только после synthetic gate повторить приватный Q07;
6. не менять Gold и не подбирать prompt по одному приватному ответу.

После решения synthesis/coverage перейти к **горизонтальному phenomenon atlas** на
публичных или синтетических minimal pairs. Только затем выбирать следующую
математическую view по доминирующему классу ошибок.

## Когда возвращаться к математическим структурам

- Graph/typed edges уже оправданы для guards, corrections, parent groups и related
  traversal.
- UMR/DRS — проверять на scope, modality, coreference и time, не на общий retrieval.
- Embeddings — оставить ablation; 0.6B кандидат проиграл lexical floor.
- Density — только для размеченных сосуществующих интерпретаций и contextual mixture,
  с classical/diagonal ablation. Текущие Q04/Q07 не являются таким доказательством.
- Tensor/transform/temporal views — только после отдельной registered operation.

## Жёсткие границы

- Не публиковать dialogue source, participant identities, review journals, raw model
  outputs, blind maps или локальные абсолютные пути.
- Не превращать model candidate cues в owner-reviewed cues.
- Не переписывать parent Gold результатами derived view.
- Не считать retrieval recall downstream-quality metric.
- Не скрывать отрицательные TF-IDF/embedding/cue результаты.
- Не продвигать atomic view как универсальное представление смысла.
- Не push/merge без явного решения пользователя; `main` остаётся замороженной.

## Быстрые команды

```powershell
$env:PYTHONPATH='src'
python -m pytest -q
git status --short --branch
git log -8 --oneline
ollama list
```

Приватные диагностические скрипты и артефакты находятся в ignored:

- `private_eval/deep_census/`
- `.fvsc/dialogue_ranker_audit/`
- `.fvsc/dialogue_ablation/`

## Текущая научная формулировка

FVSC — provenance-grounded semantic atlas, а не одна универсальная геометрия. Текущий
результат показывает, что reviewed atomic structure может одновременно сохранить
owner-sensitive границы, исправить context starvation и уменьшить prompt относительно
raw. Но даже наличие нужных facets в контексте не гарантирует их сохранения
генеративной моделью; retrieval, representation и synthesis должны оцениваться
раздельно.
