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

    # AUTO — review needed
    ("есть что-то дальше, я уверен",
     [("я", "cop:это", "уверенный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("и обернуло это в то что я должен был это понять сам",
     []),

    # EMPTY — annotate manually if judgment exists
    ("на прощание она обняла меня",
     []),

    # AUTO — review needed
    ("но я бы назвал это мысленными экспериментами",
     [("я", "назвать", "эксперимент", "A"),
      ("эксперимент", "amod", "мысленный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("и чувство как будто я вчера бухал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я почти ни с кем в сети",
     []),

    # AUTO — review needed
    ("я просто пропустил строчку",
     [("я", "пропустить", "строчка", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("и я тебя принимаю",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ты говорил что тебе было скучно",
     []),

    # EMPTY — annotate manually if judgment exists
    ("возле склада и внутри убирать ся",
     []),

    # EMPTY — annotate manually if judgment exists
    ("если зима то елок на фон хот",
     []),

    # AUTO — review needed
    ("я имею ввиду что ты не в соло страдаешь",
     [("ты", "страдать", "соло", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("а я проснулся и подумал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("есть один который многих может шокировать",
     []),

    # EMPTY — annotate manually if judgment exists
    ("были оказывается не объективны",
     []),

    # EMPTY — annotate manually if judgment exists
    ("просто такие вещи объяснить довольно трудно",
     []),

    # EMPTY — annotate manually if judgment exists
    ("есть причины на это",
     []),

    # EMPTY — annotate manually if judgment exists
    ("потому что это чревато",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и я чувствую себя чуточку счастливее",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я досмотрел гуррен лаган",
     []),

    # AUTO — review needed
    ("Внимание должна привлекать она",
     [("внимание", "cop:это", "должный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("но я не слышал чтобы так кто-то делал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну в плане они летают и может быть какие-то из них просачиваются сквозь атмосферу",
     []),

    # EMPTY — annotate manually if judgment exists
    ("впервые за долгое время поиграл в майн",
     []),

    # EMPTY — annotate manually if judgment exists
    ("у нее как и у меня были разные шнурки на кросах",
     []),

    # AUTO — review needed
    ("\"работа не волк в лес не убежит\"",
     [("работа", "убежать", "лес", "N")]),

    # EMPTY — annotate manually if judgment exists
    ("мне кстати тоже это нравится",
     []),

    # EMPTY — annotate manually if judgment exists
    ("об этом я написал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("а я недавно подумал что если сосредоточиться и вдуматься",
     []),

    # EMPTY — annotate manually if judgment exists
    ("там люди гуляли как днём",
     []),

    # AUTO — review needed
    ("то есть вы из рф повезете банки?.",
     [("ты", "повезти", "банк", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("лиза попросила налить воды",
     []),

    # EMPTY — annotate manually if judgment exists
    ("проходил через это не раз",
     []),

    # AUTO — review needed
    ("ну он больной человек что поделать",
     [("человек", "amod", "больной", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("не переживай ты всему научишься",
     []),

    # EMPTY — annotate manually if judgment exists
    ("как у людей которые в принципе общаются",
     []),

    # EMPTY — annotate manually if judgment exists
    ("Пришло время, разлуке - месть",
     []),

    # AUTO — review needed
    ("лиза говорит похоже на \"пираты черной лагуны\"",
     [("лагуна", "amod", "чёрный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("я не был возбужден особо",
     []),

    # AUTO — review needed
    ("К сожалению для тебя ценные люди обычно предпочитают эксклюзивность",
     [("человек", "предпочитать", "сожаление", "A"),
      ("человек", "предпочитать", "эксклюзивность", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("получается жизнь налаживается у тебя?",
     []),

    # EMPTY — annotate manually if judgment exists
    ("где ты их достал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и алана теперь нужно чем-то занимать, как-то проводить с ним время и заниматься его воспитанием потому что у него проблемы с агрессией и злостью",
     []),

    # AUTO — review needed
    ("у тебя милый голос там на кружке",
     [("голос", "amod", "милый", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("ну типа, визуально, ок, материально, ну никак",
     []),

    # EMPTY — annotate manually if judgment exists
    ("типа я тоже аморал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("а больше никому это не надо из окружения",
     []),

    # EMPTY — annotate manually if judgment exists
    ("но потом ассоциативно как-то линии сливались в единый логотип",
     []),

    # EMPTY — annotate manually if judgment exists
    ("сказал что вчитаюсь как-то",
     []),

    # EMPTY — annotate manually if judgment exists
    ("вчера второй день подряд засыпал с плохим, почти ужасным настроением",
     []),

    # EMPTY — annotate manually if judgment exists
    ("она не сможет их до конца понять",
     []),

    # AUTO — review needed
    ("рассуждения на тему[[ вопрос цифрового патента]]:",
     [("патент", "amod", "цифровой", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("От релокантов требуют вернуться в Россию.",
     []),

    # EMPTY — annotate manually if judgment exists
    ("как и со всем в жизни",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я стараюсь очень осторожно действовать",
     []),

    # EMPTY — annotate manually if judgment exists
    ("верность исходит не из себя самой а из нежелания делать больно",
     []),

    # EMPTY — annotate manually if judgment exists
    ("выплаты переплатили а я виноват",
     []),

    # EMPTY — annotate manually if judgment exists
    ("поработать над идеей какой нибудь",
     []),

    # EMPTY — annotate manually if judgment exists
    ("потом я с ней общался только когда ей было плохо",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и мне бывает стыдно из-за этого",
     []),

    # EMPTY — annotate manually if judgment exists
    ("бля мск это очень близко было",
     []),

    # EMPTY — annotate manually if judgment exists
    ("мне все так говорят",
     []),

    # EMPTY — annotate manually if judgment exists
    ("больше времени проводи хоть с кем-то",
     []),

    # AUTO — review needed
    ("Возможность создания персональных пространств закрытых для переговоров нескольких людей знающих друг друга в реальной жизни",
     [("пространство", "amod", "персональный", "A"),
      ("жизнь", "amod", "реальный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("мы даже не виделись ни разу",
     []),

    # EMPTY — annotate manually if judgment exists
    ("начали весело выкрикивать \"а вы что с нами ехали всё это время\" и тоже махали руками",
     []),

    # EMPTY — annotate manually if judgment exists
    ("очень красиво было там.",
     []),

    # EMPTY — annotate manually if judgment exists
    ("мне снилось много всего но я запомнил только один сон",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну время хоть хорошо провели",
     []),

    # EMPTY — annotate manually if judgment exists
    ("САШКА САШКА ТАК НЕ ХОДЯТ",
     []),

    # --- [sqmos] ---

    # AUTO — review needed
    ("играли с ним в игру где большой босс слизень был",
     [("босс", "играть", "игра", "A")]),

    # AUTO — review needed
    ("иначе бы я не научился тому что можно обозвать социальные игры",
     [("я", "научиться", "игра", "N")]),

    # AUTO — review needed
    ("это была простая логическая ошибка",
     [("ошибка", "amod", "простой", "A"),
      ("ошибка", "amod", "логический", "A")]),

    # AUTO — review needed
    ("док рассыпал зубочистки и они хором тут же произнесли \"сорок\"",
     [("док", "рассыпать", "зубочистка", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("Мы с милёнком у метро",
     []),

    # AUTO — review needed
    ("И этот, характерный для часиков, металлический щелчок, с которым под крышкой скрываются цифры, словно отсекал очередную минуту из жизни человечества.",
     [("цифра", "скрываться", "крышка", "A"),
      ("щелчок", "amod", "металлический", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("не пью таблетки кстати",
     []),

    # EMPTY — annotate manually if judgment exists
    ("советую попить что-то вроде родиолы хотябы если будет возможность",
     []),

    # EMPTY — annotate manually if judgment exists
    ("если что я периодически пытаюсь прощупать твой пульс у себя в голове",
     []),

    # AUTO — review needed
    ("00:19 перестраивается я в курсе",
     [("я", "перестраиваться", "курс", "A")]),

    # AUTO — review needed
    ("до 0:28 человек прям живой",
     [("человек", "amod", "живой", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("мы не говорили об этом обстоятельно",
     []),

    # AUTO — review needed
    ("только у меня все зубы высыпались мне в руки",
     [("зуб", "высыпаться", "рука", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("я планировал оставить табличку с адресом сайта (хотел купить домен leghoster.space или вроде того.) на твоей территории в майнкрафте, в месте куда ты заходишь априори будто более готовая к взаимодействию поскольку там есть люди или могут быть",
     []),

    # EMPTY — annotate manually if judgment exists
    ("\"есть два крайних выхода либо мы расстаемся либо вы с ней перестанете общаться\"",
     []),

    # EMPTY — annotate manually if judgment exists
    ("что если у меня будет возможность я это самое",
     []),

    # EMPTY — annotate manually if judgment exists
    ("хотя ты вроде сама на это указывала что как бы косвенно или прямо и было причиной одного из долгих молчаний",
     []),

    # EMPTY — annotate manually if judgment exists
    ("четам надо для волос",
     []),

    # EMPTY — annotate manually if judgment exists
    ("кстати нашел пару артефактов из старых снов",
     []),

    # EMPTY — annotate manually if judgment exists
    ("оно не только объяснит но и изменит, даже совершенствует",
     []),

    # EMPTY — annotate manually if judgment exists
    ("о запятые и точки не споткнешься точно",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и в нём было 10 прямоугольных коробочков по 1кг ррасфасованных",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ой кстати сегодня я был счастив кажется",
     []),

    # AUTO — review needed
    ("Апостиль на аттестат обязателен для подачи.",
     [("апостиль", "cop:это", "обязательный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("но опаснее в никотине способы его употребления",
     []),

    # AUTO — review needed
    ("если я ментально продолжаю человеку давать поддержку и тд но включаю в жизнь другого человека то как бы вродь ничего",
     [("я", "продолжать", "человек", "N")]),

    # AUTO — review needed
    ("просто проблема что он с людьми не общался толком",
     [("проблема", "общаться", "человек", "N")]),

    # EMPTY — annotate manually if judgment exists
    ("скажи пожалуйста что тебя беспокоит..",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я не писал потому что не знал чëтких границ пропадания",
     []),

    # EMPTY — annotate manually if judgment exists
    ("типа сидеть чтобы сказать",
     []),

    # AUTO — review needed
    ("Предметы, достигшие 100-летнего возраста, обретают душу.",
     [("предмет", "обретать", "душа", "A")]),

    # AUTO — review needed
    ("и по факту поймешь это все скорее всего только ты",
     [("ты", "поймешь", "факт", "A")]),

    # AUTO — review needed
    ("да, я примерно так и воспринимал сон",
     [("я", "воспринимать", "сон", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("вообще чип от маска в мозг встраивается",
     []),

    # EMPTY — annotate manually if judgment exists
    ("тут не нужно особо то уходить в субъективное для каждого",
     []),

    # EMPTY — annotate manually if judgment exists
    ("не гонюсь за 100% эффективностью просто оставляю двери и логические краны приоткрытыми",
     []),

    # AUTO — review needed
    ("вздыхаю и грудь наполняет чувство доброты и расплываюсь в улыбке",
     [("вздыхаю", "наполнять", "чувство", "A"),
      ("грудь", "наполнять", "чувство", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("ограничивающее от свободы мертальной это как телефон для человека который любит играть в него и не хочет стать большим и пересечь вселённую пешком",
     []),

    # EMPTY — annotate manually if judgment exists
    ("комплементи как не лыбица",
     []),

    # AUTO — review needed
    ("когда я ем еду которую сам же приготовил порой она кажется совсем уж безвкусной",
     [("я", "ем", "еда", "A")]),

    # AUTO — review needed
    ("просто часто мне кажется что я понимаю запах людей как хищник со стороны и свой в т.ч.",
     [("я", "понимать", "запах", "A"),
      ("я", "понимать", "хищник", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("и стало как есть.",
     []),

    # EMPTY — annotate manually if judgment exists
    ("думаю совсем малая часть из того что можно было бы сказать",
     []),

    # AUTO — review needed
    ("если о модели то это определенный спектр чувств и инструменты для оптимизации взаимодействия людей",
     [("спектр", "amod", "определённый", "A")]),

    # AUTO — review needed
    ("на каждо предмете порой вместо текстуры скука",
     [("скука", "cop:это", "предмет", "A")]),

    # AUTO — review needed
    ("выглядит так будто ты думаешь что я просто всё придумал у себя в голове и хожу страдаю",
     [("я", "придумать", "голова", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("как жаль что ресурс исчерпаем",
     []),

    # EMPTY — annotate manually if judgment exists
    ("Могут быть опасными, но также покровительствуют детям и любят огурцы .",
     []),

    # EMPTY — annotate manually if judgment exists
    ("поплавило пока игрался с этим шаром",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну просто кажется будто ты сама есть всё",
     []),

    # EMPTY — annotate manually if judgment exists
    ("настолько что он уже перестает крутиться и раскидывать его",
     []),

    # AUTO — review needed
    ("я просто пытаюсь быть искренним потому что люди способны быть целыми мирами",
     [("я", "пытаться", "искренний", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("нужно договорить в канал",
     []),

    # AUTO — review needed
    ("но ты очень сильная",
     [("ты", "cop:это", "сильный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("он бы сказал как работать с тем что следует из причин",
     []),

    # AUTO — review needed
    ("вообще нужно развить систему интрпретации и сжатия субъективного опыта",
     [("опыт", "amod", "субъективный", "A")]),

    # AUTO — review needed
    ("я видел много людей",
     [("я", "видеть", "человек", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("во мне же есть всё кроме меня",
     []),

    # AUTO — review needed
    ("у человека не отсутствует свобода воли",
     [("свобода", "отсутствовать", "человек", "N")]),

    # EMPTY — annotate manually if judgment exists
    ("из последнего мне казалось что ты будешь вместе с Крисом типа в отношениях смысле",
     []),

    # EMPTY — annotate manually if judgment exists
    ("начал изучать квантовую физику, иногда курить хотя обещал себе не делать этого",
     []),

    # EMPTY — annotate manually if judgment exists
    ("как видишь там всего одна заметка",
     []),

    # EMPTY — annotate manually if judgment exists
    ("иногда я не фиксировал что плохо",
     []),

    # AUTO — review needed
    ("я выходил из ванной",
     [("я", "выходить", "ванная", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("задаю очень неудобные вопросы иногда напрямую и даже в шуточной форме чтобы подумал человек",
     []),

    # EMPTY — annotate manually if judgment exists
    ("в том что сказал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("что-то хочу сказать ..",
     []),

    # AUTO — review needed
    ("на деле это показываются адаптации психики в разных средах в которых они формировались, учились, выживали",
     [("дело", "показываться", "адаптация", "A")]),

    # AUTO — review needed
    ("я если что про звуки металла, деревьев",
     [("я", "cop:это", "дерево", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("человек плакал, плохо было ему",
     []),

    # --- [key7] ---

    # EMPTY — annotate manually if judgment exists
    ("из нее много чего может вытекать",
     []),

    # AUTO — review needed
    ("Я поплакал(а) и стало лучше.",
     [("я", "стать", "хороший", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("ну я буду симуляцию запускать",
     []),

    # AUTO — review needed
    ("что-то что \"нормальные\" люди называют неслушабельным",
     [("человек", "называть", "неслушабельным", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("«мои онтологические щупальца прямо-таки дрожат от восторга», сказал [Ч]",
     []),

    # AUTO — review needed
    ("я имел ввиду люди",
     [("я", "иметь", "человек", "A")]),

    # AUTO — review needed
    ("- \"Свобода, которую даёт любовь\" — относительные предложения",
     [("свобода", "cop:это", "предложение", "A"),
      ("предложение", "amod", "относительный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("когда мне плохо я напоминаю себе как работает на физ.",
     []),

    # AUTO — review needed
    ("так трудно отказывать людям что я бездействовал когда рядом был человек который хотел контакта",
     [("я", "бездействовать", "человек", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("будь жизнь субъективно комфортна все равно бы хотелось умереть?",
     []),

    # EMPTY — annotate manually if judgment exists
    ("кажется ты много играл в пк",
     []),

    # EMPTY — annotate manually if judgment exists
    ("но я не могу перестать иметь тело",
     []),

    # EMPTY — annotate manually if judgment exists
    ("Исследования показывают, что кастрация может продлить жизнь мужчинам, в среднем на несколько лет, из-за снижения уровня тестостерона, замедляющего старение и влияющего на иммунную систему.",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну тут он уже есть",
     []),

    # EMPTY — annotate manually if judgment exists
    ("только больше непонимания контекстов",
     []),

    # AUTO — review needed
    ("дак ты как будешь генерить теги",
     [("ты", "генерить", "теги", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("но знаешь для людей герой тот кто служит сверхличностным целям",
     []),

    # AUTO — review needed
    ("Я бы поиграл по приколу в хоррор мод",
     [("я", "поиграть", "прикол", "A"),
      ("я", "поиграть", "хоррор", "A"),
      ("я", "поиграть", "мода", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("6 критических пробелов — что не существует и что придётся изобретать",
     []),

    # EMPTY — annotate manually if judgment exists
    ("часто ощущал себя архитипической сущностью которая строит вселенные из пустоты, целые миры",
     []),

    # EMPTY — annotate manually if judgment exists
    ("но чем больше принимаешь вещей с которыми ничего не можешь поделать тем свободнее становишься",
     []),

    # EMPTY — annotate manually if judgment exists
    ("если о внешности то как минимум худой и ношу крест",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну если мы будем детерминировать твою жизнь то не только твоя",
     []),

    # EMPTY — annotate manually if judgment exists
    ("кошачей мяты не почувствовал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("пытаюсь работать на себя)",
     []),

    # EMPTY — annotate manually if judgment exists
    ("говорила об этом прям",
     []),

    # EMPTY — annotate manually if judgment exists
    ("выбрать никнейм кем именно из участников взаимодействия является сам пользователь",
     []),

    # AUTO — review needed
    ("и я видел землю",
     [("я", "видеть", "земля", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("но не обязательно сразу",
     []),

    # EMPTY — annotate manually if judgment exists
    ("потому что частотность употребления говорит сама за себя",
     []),

    # EMPTY — annotate manually if judgment exists
    ("так что если копать то сюда",
     []),

    # EMPTY — annotate manually if judgment exists
    ("для тех у кого нет локал ллм",
     []),

    # EMPTY — annotate manually if judgment exists
    ("написал в тот период",
     []),

    # EMPTY — annotate manually if judgment exists
    ("пхпх ну можно и их)",
     []),

    # EMPTY — annotate manually if judgment exists
    ("кстати у меня есть коллекция окаменелостей",
     []),

    # EMPTY — annotate manually if judgment exists
    ("изолированно это сделать пожалуй трудно",
     []),

    # AUTO — review needed
    ("но когда закончу кухню свободного времени должно быть гораздо больше",
     [("кухня", "cop:это", "должный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("а ты скрафтишь такую абстракцию ктторая будет пизже",
     []),

    # AUTO — review needed
    ("там были голые люди",
     [("человек", "amod", "голый", "A")]),

    # AUTO — review needed
    ("Красный шум слышен с берега от отдалённых объектов, находящихся в океане.",
     [("шум", "cop:это", "слышный", "A")]),

    # AUTO — review needed
    ("самое близкое это knowledge graph на рекурсивной модели нейросети",
     [("модель", "amod", "рекурсивный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("это бывший эмеральда как раз",
     []),

    # EMPTY — annotate manually if judgment exists
    ("но я ему открыться не могу",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и уже в третий раз написала",
     []),

    # EMPTY — annotate manually if judgment exists
    ("если им простым языком и контекстуально объяснить",
     []),

    # EMPTY — annotate manually if judgment exists
    ("могу предположить что когда я только родился и был слепым",
     []),

    # AUTO — review needed
    ("в природе есть взаимодействие оргаризмов",
     [("взаимодействие", "быть", "природа", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("то есть попытки были но там всë не то оказывалось, слишком плоско",
     []),

    # EMPTY — annotate manually if judgment exists
    ("могу ли я посмотреть мир глазами другого человека",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну типа время уделяю кому-то",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я с некоторыми взаимодействовал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("думал что будешь более м отрешенным от реальности может быть",
     []),

    # AUTO — review needed
    ("Шум, спектр которого имеет преимущественно нулевую энергию за исключением нескольких пиков[5]",
     [("спектр", "иметь", "энергия", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("он целый год мучался от кашмаров",
     []),

    # EMPTY — annotate manually if judgment exists
    ("он кстати хорош но я сожалею что у меня не получилось прожить этот опыт при прослушивании",
     []),

    # AUTO — review needed
    ("меня в репо зовет человек их прошлых отношений",
     [("человек", "звать", "репо", "A"),
      ("отношение", "звать", "репо", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("вчера плакал кстати спустя долгое время",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и понял что это мне нп по карману как минимум",
     []),

    # AUTO — review needed
    ("\"свобода\" набирало массу в 2024 году, а потом затухло — это ценно для самопознания.",
     [("свобода", "набирало", "масса", "A"),
      ("свобода", "набирало", "год", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("но и те с трудом заставляют себя не плакать",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я хочу вообще свою эко-деревню построить",
     []),

    # EMPTY — annotate manually if judgment exists
    ("плюс не хотел принимать поспешных решений но он сказал что я недостаточно нейропластичный потому что не могу стать геем или вроде того",
     []),

    # AUTO — review needed
    ("Первые 50 текстов будут давать шум, а не карту.",
     [("текст", "давать", "шум", "A"),
      ("текст", "давать", "карта", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("если думать то он точно пропадет",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я может быть с ним смогу",
     []),

    # EMPTY — annotate manually if judgment exists
    ("да, согласен, очень важное делают ребята",
     []),

    # EMPTY — annotate manually if judgment exists
    ("у каждого уже есть",
     []),

    # EMPTY — annotate manually if judgment exists
    ("это не расширение границ понимания реальности а скорее прикольный эксперимент с восприятием",
     []),

    # AUTO — review needed
    ("я даже сам какое-то время сомневался что я не шизофренический бред несу",
     [("бред", "amod", "шизофренический", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("как говорила моя мама",
     []),

]
