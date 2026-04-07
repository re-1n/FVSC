# -*- coding: utf-8 -*-
"""
Расширенный eval set — 210 нормализованных предложений из Telegram-чатов.

PRE-ANNOTATED: auto-extracted judgments для ручной проверки.
Статус: # AUTO = автоматически извлечено, требует ревью
        # EMPTY = автоэкстракция пуста, разметить вручную если есть суждение
        # CONFIRMED = проверено человеком

Глаголы в инфинитиве (лемме): "требует" → "требовать".
Копулы: "X — это Y" → verb="cop:это".
Прилагательные: "важная свобода" → verb="amod".
Quality: A=утвердительное, N=отрицательное.
"""

GOLD_EXTENDED = [
    # --- [shkshotr] ---

    # EMPTY — annotate manually if judgment exists
    ("что-то типа сонного паралича",
     []),

    # EMPTY — annotate manually if judgment exists
    ("поспал 3 часа примерно",
     []),

    # EMPTY — annotate manually if judgment exists
    ("не помню чем закончилось",
     []),

    # AUTO — review needed
    ("2 галлона конской спермы",
     [("сперма", "amod", "конский", "A")]),

    # AUTO — review needed
    ("кажется у женщин примерно такая же позиция",
     [("позиция", "казаться", "женщина", "A")]),

    # AUTO — review needed
    ("я вернулся в реальность.",
     [("я", "вернуться", "реальность", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("бывало я был нейтрален",
     []),

    # EMPTY — annotate manually if judgment exists
    ("химию и матан смешал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("думаю что тяжелые последние годы жизни были у него",
     []),

    # AUTO — review needed
    ("ты уже всех знакомых научил",
     [("ты", "научить", "знакомых", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("не буду заëбывать с тем что она не развивается",
     []),

    # EMPTY — annotate manually if judgment exists
    ("кто не может жить сам пусть его косит естественный отбор",
     []),

    # EMPTY — annotate manually if judgment exists
    ("так и есть, скорее всего..",
     []),

    # EMPTY — annotate manually if judgment exists
    ("это из-за бесполезности процесса",
     []),

    # EMPTY — annotate manually if judgment exists
    ("от людей вокруг зависит",
     []),

    # AUTO — review needed
    ("очень сильно чувствуется когда какие-то мышцы побыли в напряжении какое-то время",
     [("мышца", "побыть", "напряжение", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("там чурки мир захватили",
     []),

    # EMPTY — annotate manually if judgment exists
    ("во мне нет мотивации и у меня нет цели",
     []),

    # EMPTY — annotate manually if judgment exists
    ("твой путь единственный верный для тебя",
     []),

    # EMPTY — annotate manually if judgment exists
    ("каждый день начинается в относительной дереализации и некой пластмассовости",
     []),

    # EMPTY — annotate manually if judgment exists
    ("Она всегда очень завораживала маленького призрака в ее свете он чувствовал себя спокойнее.",
     []),

    # AUTO — review needed
    ("лина со своим новым парнем у меня на глазах занимались.",
     [("лина", "заниматься", "глаз", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("но успокоившись уснул и снова попал в петлю",
     []),

    # EMPTY — annotate manually if judgment exists
    ("мне он кажется \"моим\"",
     []),

    # EMPTY — annotate manually if judgment exists
    ("мне льстит что кто-то считает меня обречённым",
     []),

    # EMPTY — annotate manually if judgment exists
    ("Всё ещё на той же комнате",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ей нужно было просто выйти к дороге через ролчаса",
     []),

    # EMPTY — annotate manually if judgment exists
    ("сколько тебе ещё носить их",
     []),

    # EMPTY — annotate manually if judgment exists
    ("если не секрет конечно..",
     []),

    # EMPTY — annotate manually if judgment exists
    ("помог 18ти летнему мальчику",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну и что делать",
     []),

    # AUTO — review needed
    ("я знаю какие цели она преследует",
     [("я", "знать", "цель", "A")]),

    # AUTO — review needed
    ("в будущем будут воспринимать тебя таким как ты есть",
     [("ты", "воспринимать", "будущее", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("было дело сегодня да..",
     []),

    # AUTO — review needed
    ("- Яичный белок - 2шт.",
     [("белок", "amod", "яичный", "A")]),

    # AUTO — review needed
    ("от чего-то я ощущаю тяжесть",
     [("я", "ощущать", "тяжесть", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("но он тебе таких инсайдов может насыпать",
     []),

    # AUTO — review needed
    ("почему в дошике приправа отдельно типа..",
     [("приправа", "cop:это", "дошике", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("в армию зато не надо",
     []),

    # AUTO — review needed
    ("дрочатся там люди с других стран",
     [("человек", "дрочатся", "страна", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("но если ты не можешь сдерживать это не слабость",
     []),

    # EMPTY — annotate manually if judgment exists
    ("в общем-то когда люди с срк не нервничают обычно им гораздо легче",
     []),

    # EMPTY — annotate manually if judgment exists
    ("может им и платят больше",
     []),

    # EMPTY — annotate manually if judgment exists
    ("кирилл работает и копит на свадьбу",
     []),

    # EMPTY — annotate manually if judgment exists
    ("когда по видеосвязи говорил вроде",
     []),

    # EMPTY — annotate manually if judgment exists
    ("вот это ты себя удовлетворяешь",
     []),

    # EMPTY — annotate manually if judgment exists
    ("он поехал на работу а я вот вернулся домой",
     []),

    # EMPTY — annotate manually if judgment exists
    ("да нормально в принципе",
     []),

    # EMPTY — annotate manually if judgment exists
    ("только и повеситься если еще и одинок",
     []),

    # EMPTY — annotate manually if judgment exists
    ("все средство уже смылось, осталась только вода",
     []),

    # EMPTY — annotate manually if judgment exists
    ("а если представлю как это делаю",
     []),

    # EMPTY — annotate manually if judgment exists
    ("на то куда там сперма полетит",
     []),

    # EMPTY — annotate manually if judgment exists
    ("Человек с часами и таймером в минуту.",
     []),

    # EMPTY — annotate manually if judgment exists
    ("тебе просто переодеться нужно",
     []),

    # AUTO — review needed
    ("создание тематических разделов по желанию пользователей",
     [("раздел", "amod", "тематический", "A")]),

    # AUTO — review needed
    ("Я тут упарываюсь в абстрактные штуки и свои внутренние ощущения и реакцию на реальный мир",
     [("я", "упарываюсь", "штука", "A"),
      ("я", "упарываюсь", "реакция", "A"),
      ("я", "упарываюсь", "мир", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("Из-за того что помогал андрею трек писать",
     []),

    # EMPTY — annotate manually if judgment exists
    ("типа можно жить спокойно без этого",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ты был фаталистичен так что да",
     []),

    # EMPTY — annotate manually if judgment exists
    ("день как обычно рутина",
     []),

    # EMPTY — annotate manually if judgment exists
    ("могу с ней поговорить о чем угодно",
     []),

    # EMPTY — annotate manually if judgment exists
    ("что учишь таки немецкий",
     []),

    # EMPTY — annotate manually if judgment exists
    ("еду встречать лизу с работы",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и это несомненно повлияло на меня",
     []),

    # AUTO — review needed
    ("моя первая любовь тоже была больна",
     [("любовь", "cop:быть", "больной", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("интересно ну обработай чем-то",
     []),

    # AUTO — review needed
    ("я уверен в том что ты способен со всем этим рассправиться",
     [("я", "cop:это", "уверенный", "A")]),

    # AUTO — review needed
    ("и как я заполнял документы на призыв",
     [("я", "заполнять", "документ", "A"),
      ("я", "заполнять", "призыв", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("ну ты не знаешь что такое",
     []),

    # AUTO — review needed
    ("прикольный, властный человек со своей опг",
     [("человек", "amod", "прикольный", "A")]),

    # --- [sqmos] ---

    # EMPTY — annotate manually if judgment exists
    ("типа уют? для меня?",
     []),

    # EMPTY — annotate manually if judgment exists
    ("может быть и такое что я никогда не скажу то чего ты не понимаешь или не поймёшь",
     []),

    # AUTO — review needed
    ("не было едкости и разбитости утром что очень редко бывало в принципе",
     [("едкость", "быть", "принцип", "N"),
      ("разбитость", "быть", "принцип", "N")]),

    # EMPTY — annotate manually if judgment exists
    ("но видео арабов с казнями и издевательствами",
     []),

    # AUTO — review needed
    ("что за страшный человек",
     [("человек", "amod", "страшный", "A")]),

    # AUTO — review needed
    ("кинетический импульс большого взрыва как архипричина соткал реальность и разгосится волнами событий и причинно-следственных в бесконечность",
     [("импульс", "соткал", "реальность", "A"),
      ("импульс", "соткал", "бесконечность", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("немного в ударе сегодня",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и я рождаю вселенную",
     []),

    # EMPTY — annotate manually if judgment exists
    ("к вечеру мы ВОЗМОЖНО сможем в дс на пример сегодня",
     []),

    # EMPTY — annotate manually if judgment exists
    ("вокруг меня еще попадаются частные домики но их становится меньше и плотность высоток растет",
     []),

    # EMPTY — annotate manually if judgment exists
    ("более математичные, механические / более чувственные",
     []),

    # EMPTY — annotate manually if judgment exists
    ("можно скрин того что я там писал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("это как раз и хотел узнать",
     []),

    # EMPTY — annotate manually if judgment exists
    ("допустим этот если взять он тяжёлый но качественный будет и скорее всего не прогадаем",
     []),

    # EMPTY — annotate manually if judgment exists
    ("на самом деле у меня внешность немного необычная пушто есть чурки в корнях",
     []),

    # AUTO — review needed
    ("ещё и из-за гиперэмтии наверное часто надуманной (кажется)",
     [("гиперэмтии", "cop:это", "надуманный", "A")]),

    # AUTO — review needed
    ("в некоторые моменты буду пропадать но обязательно возвращаться когда будет возможность",
     [("возможность", "пропадать", "момент", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("я был немного занят.",
     []),

    # AUTO — review needed
    ("людей с которыми я общаюсь на диагноз наберется",
     [("я", "общаться", "человек", "A"),
      ("я", "общаться", "диагноз", "A")]),

    # AUTO — review needed
    ("- Общие расходы на жизнь: €800–1200/мес (жильё + еда + транспорт + страховка + карманные).",
     [("расход", "amod", "общий", "A")]),

    # AUTO — review needed
    ("человек переоценивает своё значение во вселенной кажется будто",
     [("человек", "переоценивать", "значение", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("он синергируют до одного существа на нейронном уровне",
     []),

    # EMPTY — annotate manually if judgment exists
    ("потом я увидел что волосы у меня теперь мило лежат и я похож на девочку👉👈",
     []),

    # AUTO — review needed
    ("я бы и тоже пошел в майн но нужно готовить",
     [("я", "пойти", "майн", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("и если они хотят",
     []),

    # AUTO — review needed
    ("я осуждаю его в некотором но может это даст больше понимания если нужно то можешь читать, задавать вопросы",
     [("я", "осуждать", "вопрос", "A")]),

    # AUTO — review needed
    ("ты на пример выкатила лонгрид той девочке которую пыталась уберечь от типа из подвала",
     [("ты", "выкатить", "пример", "A"),
      ("ты", "выкатить", "лонгрид", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("все нормально еще не понятно",
     []),

    # EMPTY — annotate manually if judgment exists
    ("такое пока не было возможно и я не смогу сказать прямо",
     []),

    # EMPTY — annotate manually if judgment exists
    ("сводя все к тому что из себя представляет моя жизнь",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ебать как ты туда поступила вще",
     []),

    # AUTO — review needed
    ("но я должен делать платформу",
     [("я", "cop:это", "должный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("и многое зависит от меня и это еще больше ебет",
     []),

    # EMPTY — annotate manually if judgment exists
    ("просто это уже так ловко и быстро происходит",
     []),

    # EMPTY — annotate manually if judgment exists
    ("но не который должен что-то кому-то",
     []),

    # EMPTY — annotate manually if judgment exists
    ("Больше нет нигде объектов —",
     []),

    # EMPTY — annotate manually if judgment exists
    ("но и просьба в моменты когда это было бы уместно",
     []),

    # EMPTY — annotate manually if judgment exists
    ("просто ему лонгриды не заходят",
     []),

    # EMPTY — annotate manually if judgment exists
    ("а что если вводить вещество которое будет триггерить ощущение м",
     []),

    # EMPTY — annotate manually if judgment exists
    ("защиты мне иногда не хватает",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и не дойдёт думаю",
     []),

    # AUTO — review needed
    ("- Если на базу подается ток, транзистор открывается, и ток течёт от коллектора к эмиттеру.",
     [("база", "подаваться", "ток", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("это как бы без проблем личное навеерное все дела",
     []),

    # EMPTY — annotate manually if judgment exists
    ("Это касается бакалавриата и последовательной магистратуры (consecutive Master's) в большинстве публичных университетов.",
     []),

    # AUTO — review needed
    ("думая за меня ты компеллируешь мною сказанное в выводы и логику это очень большая работа и мне стыдно даже както, что это я-то должен делать а ты совсем не обязана.",
     [("ты", "компеллируешь", "работа", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("Но это вдохновляет на embodied AI, где ИИ с роботизированным \"телом\" может приблизиться к человеческому grounded опыту, решая проблемы вроде отсутствия эмпатии.",
     []),

    # AUTO — review needed
    ("потому что я дал ему душу",
     [("я", "дать", "душа", "A")]),

    # AUTO — review needed
    ("и тебе большое спасибо за все чем делишься, правда",
     [("спасибо", "amod", "большой", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("ведь раньше в среде к которой он адаптировался его так научили / это работало",
     []),

    # AUTO — review needed
    ("- Студенческие общежития (Studentenwerk) — самые дешёвые (€250–450/мес, включая коммуналку), но очередь большая (подавай сразу после acceptance).",
     [("общежитие", "cop:это", "дешёвый", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("из него можно собрать любой инструмент",
     []),

    # EMPTY — annotate manually if judgment exists
    ("неважно что под этим подразумевать",
     []),

    # EMPTY — annotate manually if judgment exists
    ("эти моменты цепляли меня до неприятного жжения в груди, до горечи",
     []),

    # AUTO — review needed
    ("просто было уверенное ощущение",
     [("ощущение", "amod", "уверенный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("ну вот я просто сглупил думаю",
     []),

    # AUTO — review needed
    ("я кхккх аа можново мизинчиковое или..",
     [("я", "cop:это", "кхккх", "A")]),

    # AUTO — review needed
    ("я написал это сообщения",
     [("я", "написать", "сообщение", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("может быть ведь так что деньги на сигареты нужнее",
     []),

    # AUTO — review needed
    ("капкан для людей который зубы ломает да",
     [("капкан", "ломать", "зуб", "A")]),

    # AUTO — review needed
    ("очень кривой недоделанный монтаж моментов из армии..",
     [("монтаж", "amod", "кривой", "A"),
      ("монтаж", "amod", "недоделанный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("у меня много мест где лежат деньги",
     []),

    # EMPTY — annotate manually if judgment exists
    ("по сути ракету бы по-хорошему",
     []),

    # EMPTY — annotate manually if judgment exists
    ("Полностью бесплатное + стипендия на жизнь (чтобы покрыть расходы)",
     []),

    # AUTO — review needed
    ("ой да латна не души так себя",
     [("душа", "cop:это", "латный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("только больше хочется сказать превед",
     []),

    # EMPTY — annotate manually if judgment exists
    ("тут суть в том что",
     []),

    # EMPTY — annotate manually if judgment exists
    ("кажется слушал когда-то но не услышал (про трек)",
     []),

    # EMPTY — annotate manually if judgment exists
    ("типа сидеть чтобы сказать",
     []),

    # EMPTY — annotate manually if judgment exists
    ("терялся в высокой траве",
     []),

    # EMPTY — annotate manually if judgment exists
    ("можно и миром назвать",
     []),

    # --- [key7] ---

    # EMPTY — annotate manually if judgment exists
    ("а ты где живешь если не секрет",
     []),

    # EMPTY — annotate manually if judgment exists
    ("для ненависти к себе",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и работают они не очень",
     []),

    # AUTO — review needed
    ("я скинул сон в дополнение к тейку про нырок в пустоту и выстраивание концепции где даже над пропастью гештальтов и триггеров ты можешь быть в порядке",
     [("я", "скинуть", "сон", "A"),
      ("я", "скинуть", "дополнение", "A"),
      ("я", "скинуть", "порядок", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("как обычно утром было хуже",
     []),

    # EMPTY — annotate manually if judgment exists
    ("кошачей мяты не почувствовал",
     []),

    # AUTO — review needed
    ("инопланетное топливо и тд",
     [("топливо", "amod", "инопланетный", "A")]),

    # AUTO — review needed
    ("у меня была беда с зубами в детстве",
     [("беда", "быть", "детство", "A")]),

    # AUTO — review needed
    ("а не специальное столкновение",
     [("столкновение", "amod", "специальный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("даже если захочешь сделать что-то в значительной степени отличное от моего",
     []),

    # EMPTY — annotate manually if judgment exists
    ("Это началось еще в детстве когда поедая п-песок на детской площадке я впервые зараз-зился [стронгило‌идес-с-с стерк-к-кора‌лис]",
     []),

    # EMPTY — annotate manually if judgment exists
    ("могу ли я посмотреть мир глазами другого человека",
     []),

    # EMPTY — annotate manually if judgment exists
    ("это все я хотел пихнуть в платформу",
     []),

    # EMPTY — annotate manually if judgment exists
    ("думаю чут чут текстуры если придать и каскадик сделать то будет нормально волчара",
     []),

    # EMPTY — annotate manually if judgment exists
    ("моя идея вообще началась",
     []),

    # AUTO — review needed
    ("где же я писал блин",
     [("я", "писать", "блин", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("у меня было много проектов связано с майном",
     []),

    # EMPTY — annotate manually if judgment exists
    ("это реально трудно объяснить",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я понимаю как это странно звучит",
     []),

    # AUTO — review needed
    ("я не адреналиновый человек",
     [("я", "cop:это", "человек", "A"),
      ("человек", "amod", "адреналиновый", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("так что если копать то сюда",
     []),

    # AUTO — review needed
    ("но ночь ушла только на просмотр информации и изучение",
     [("ночь", "уйти", "просмотр", "A"),
      ("ночь", "уйти", "изучение", "A")]),

    # AUTO — review needed
    ("я в целом так и подумал и испугался что принял вас за одного человека",
     [("я", "подумать", "целое", "A")]),

    # AUTO — review needed
    ("но чуть с другим определением",
     [("определение", "amod", "другим", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("но у нас абсолют а не как у человека",
     []),

    # EMPTY — annotate manually if judgment exists
    ("или непонимарие того что делать в принципе",
     []),

    # EMPTY — annotate manually if judgment exists
    ("вспоминая весь опыт сновидений и иных \"измененных\" состояний, ощущаю след, оставленный ими внутри меня.",
     []),

    # EMPTY — annotate manually if judgment exists
    ("плюс не хотел принимать поспешных решений но он сказал что я недостаточно нейропластичный потому что не могу стать геем или вроде того",
     []),

    # EMPTY — annotate manually if judgment exists
    ("просто что-то можешь узнать у нейронок",
     []),

    # EMPTY — annotate manually if judgment exists
    ("то есть ты слишком сконцентрирован на нашем взаимодействии?",
     []),

    # EMPTY — annotate manually if judgment exists
    ("кстати это эгоистично так-то",
     []),

    # EMPTY — annotate manually if judgment exists
    ("Дай мне изучить все",
     []),

    # EMPTY — annotate manually if judgment exists
    ("да, пожалуй одна из самых больших моих болей это невозможность переживать различный опыт особенно опыт взаимодействия с людьми",
     []),

    # EMPTY — annotate manually if judgment exists
    ("если прикрутить нейрочипы вовремя",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и не стесняются быть мерзкими или обнажающими чтолибо",
     []),

    # EMPTY — annotate manually if judgment exists
    ("это было ужасно больно",
     []),

    # AUTO — review needed
    ("Это понятие подчеркивает автономность, свободу выбора и каузальность (причинно-следственную связь) между действиями и их результатами.",
     [("понятие", "подчёркивать", "автономность", "A"),
      ("понятие", "подчёркивать", "свобода", "A"),
      ("понятие", "подчёркивать", "каузальность", "A")]),

    # AUTO — review needed
    ("ключевыми изобретениями: (1) фрактальный IFS-механизм для понятий, (2) персонализированная qualia-геометрия, (3) мост между IIT/QRI и",
     [("ifs", "cop:это", "изобретениями", "A"),
      ("механизм", "cop:это", "изобретениями", "A"),
      ("изобретениями", "amod", "ключевой", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("Сравнение карт как основа для диалога.",
     []),

    # AUTO — review needed
    ("я только что разделал курицу голыми руками",
     [("я", "разделать", "курица", "A"),
      ("я", "разделать", "рука", "A")]),

    # AUTO — review needed
    ("только то что ты сказал бро)",
     [("ты", "сказать", "бро", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("Но риск в том, чтобы поверить, что метафора глубже, чем она есть.",
     []),

    # AUTO — review needed
    ("но я думал об исключительности",
     [("я", "думать", "исключительность", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("я просто не совсем мыслю такими мерками",
     []),

    # EMPTY — annotate manually if judgment exists
    ("он меня пытался склеить",
     []),

    # EMPTY — annotate manually if judgment exists
    ("но если это возможно",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну типа время уделяю кому-то",
     []),

    # EMPTY — annotate manually if judgment exists
    ("сам я кодил очень мало",
     []),

    # AUTO — review needed
    ("я жил похожим образом",
     [("я", "жить", "образ", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("ну они озабочены этим в каком-то смысле",
     []),

    # EMPTY — annotate manually if judgment exists
    ("вот это меня прям поломало",
     []),

    # EMPTY — annotate manually if judgment exists
    ("типа ебать я тупой",
     []),

    # AUTO — review needed
    ("требуй постановления диагноза, тебя чтобы класть в пнд должны были что-то поставить",
     [("требуй", "cop:были", "должный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("чуть по чуть впрыскиваются",
     []),

    # AUTO — review needed
    ("забавно что я произнëс слово \"распад\" и другой человек сказал что именно это слово было в его голове при описании",
     [("я", "произнëс", "слово", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("сходить с ума порой свобода",
     []),

    # AUTO — review needed
    ("Что \"любовь содержит свободу\" не означает \"свобода содержит любовь\" — и что эта асимметрия И ЕСТЬ отпечаток восприятия.",
     [("любовь", "содержать", "свобода", "N")]),

    # AUTO — review needed
    ("я не лежал в пнд по диагнозу",
     [("я", "лежать", "пнд", "N"),
      ("я", "лежать", "диагноз", "N")]),

    # AUTO — review needed
    ("Да можно но не обязательно это я просто чтобы на фоне что-то делали вдвоём и параллельно разговаривали можно отвлекаться на объяснение чего-то или схемы и обратно в Майн",
     [("я", "делать", "фон", "A"),
      ("я", "делать", "вдвоём", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("семантических маперов нет особо",
     []),

    # EMPTY — annotate manually if judgment exists
    ("просто поговорить надо нормально",
     []),

    # EMPTY — annotate manually if judgment exists
    ("Это не значит, что идея плохая.",
     []),

    # EMPTY — annotate manually if judgment exists
    ("что бы ни было",
     []),

    # EMPTY — annotate manually if judgment exists
    ("да, но в тех условиях я бы и не стал",
     []),

    # AUTO — review needed
    ("У этих трёх вариантов разные требования к качеству и разные типы ошибок.",
     [("требование", "cop:это", "вариант", "A"),
      ("тип", "cop:это", "вариант", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("как минимум один из них",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ты говорил что тëтя болеет вроде",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я не от тебя устал или типа того просто когда много пишу или гворю устаю в какой-то момент сам от себя",
     []),

    # EMPTY — annotate manually if judgment exists
    ("значит ты можешь себе это представить и внутри тебя есть пространство где подобный опыт может разворачиваться",
     []),

    # AUTO — review needed
    ("атомарный уровень фрактольного графа на основании которого происходит анализ",
     [("граф", "amod", "фрактольного", "A"),
      ("анализ", "происходить", "основание", "A"),
      ("уровень", "amod", "атомарный", "A")]),

]
