# -*- coding: utf-8 -*-
"""
Расширенный eval set — 199 предложений из реальных Telegram-чатов.

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
    # AUTO — review needed
    ("У подножия скал в склепе проснулся однажды маленький призрак.",
     [("призрак", "проснуться", "подножие", "A"),
      ("призрак", "проснуться", "склеп", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("если сидеть дома или беззаботно проводить время",
     []),

    # EMPTY — annotate manually if judgment exists
    ("сомневаюсь что год назад ты был таким же",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я видел как занимаются сексом мои родители",
     []),

    # AUTO — review needed
    ("у каждого должен быть свой смысл отдельно",
     [("смысл", "cop:это", "должный", "A")]),

    # AUTO — review needed
    ("чужой человек - олицетворение социума",
     [("человек", "cop:это", "олицетворение", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("ну губы и кожу на пальцах",
     []),

    # EMPTY — annotate manually if judgment exists
    ("все не важно я не смогу ничего рассказать",
     []),

    # EMPTY — annotate manually if judgment exists
    ("стремление вселенной как системы к ней",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и на проезд немного осталось",
     []),

    # EMPTY — annotate manually if judgment exists
    ("кажется тогда я выгорел",
     []),

    # EMPTY — annotate manually if judgment exists
    ("через посредника так сказать",
     []),

    # AUTO — review needed
    ("второй человек с инсультом в этом доме",
     [("человек", "amod", "второй", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("мне очень жаль что тебе пришлось пережить это",
     []),

    # EMPTY — annotate manually if judgment exists
    ("скорее они должны за это извиниться",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и как это тогда выглядело бы",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и раздражают и радуют",
     []),

    # AUTO — review needed
    ("мне сосали пока я играл в бравлик",
     [("я", "играть", "бравлик", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("меня просто заебало быть бедным",
     []),

    # EMPTY — annotate manually if judgment exists
    ("в 7 утра скинули шакальный видос как работать в проге",
     []),

    # EMPTY — annotate manually if judgment exists
    ("общаюсь только в интернете с 2мя, максимум 4мя людьми",
     []),

    # AUTO — review needed
    ("проблема не в месте мне кажется",
     [("проблема", "казаться", "место", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("приятно проходиться потом по ним",
     []),

    # EMPTY — annotate manually if judgment exists
    ("жаль возможность радоваться ему есть не у каждого",
     []),

    # AUTO — review needed
    ("хорошо друг, буду ждать когда в следующий раз у нас будет возможность поговорить, обнял",
     [("возможность", "будет", "раз", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("все происходило постепенно как-то и я чувствовал как знакомлюсь с чем-то новым постепенно и понимаю как это работает",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я бы сказал у меня все происходило очень плавно",
     []),

    # EMPTY — annotate manually if judgment exists
    ("когда проснулся я начал кусать себя",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я сказал иди нахуй со своим компьютером",
     []),

    # AUTO — review needed
    ("кстати я напишу как зайду на сервер",
     [("я", "написать", "сервер", "A")]),

    # AUTO — review needed
    ("я понимаю что языки типа уникальны",
     [("я", "понимать", "уникальный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("и чуть больше мышц",
     []),

    # EMPTY — annotate manually if judgment exists
    ("сегодня я чихнул когда хотел зайти в диалог с самим собой",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ммне нужно идти, извини....",
     []),

    # EMPTY — annotate manually if judgment exists
    ("думаю твой тгк может стать чем-то похожим на тг нулифаера",
     []),

    # EMPTY — annotate manually if judgment exists
    ("если будет возможность я это сделаю",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну люди как-то живут",
     []),

    # EMPTY — annotate manually if judgment exists
    ("бля у тебя есть логика",
     []),

    # EMPTY — annotate manually if judgment exists
    ("но не прям жесть",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и тысячи людей куют метелл",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну хорошо, что она умеет это делать",
     []),

    # EMPTY — annotate manually if judgment exists
    ("о чем я рассказывал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну типа ты такой будь моим батей",
     []),

    # EMPTY — annotate manually if judgment exists
    ("спать было очень неприятно",
     []),

    # AUTO — review needed
    ("я тоже буду рад если так получится",
     [("я", "cop:быть", "рад", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("но кажется что-то приятное",
     []),

    # EMPTY — annotate manually if judgment exists
    ("хотя маленькие не преследуют цели убивать",
     []),

    # EMPTY — annotate manually if judgment exists
    ("одна под другую надевается",
     []),

    # EMPTY — annotate manually if judgment exists
    ("которую ты любишь *",
     []),

    # AUTO — review needed
    ("это всё и есть твои музыкальные предпочтения",
     [("предпочтение", "amod", "музыкальный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("или для удовлетворения потребностей",
     []),

    # EMPTY — annotate manually if judgment exists
    ("делаю зарядку, завтракаю всё такое",
     []),

    # AUTO — review needed
    ("мне кажется или в платонической любви взаимность не всегда необходима",
     [("взаимность", "cop:это", "необходимый", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("помню только что это было что-то доброе и хорошее",
     []),

    # EMPTY — annotate manually if judgment exists
    ("Да и тем более люди с которыми я пытаюсь завести дружбу просто рано или поздно перестают со мной разговаривать",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я ещё спросил \"почему ты так выглядишь?\"",
     []),

    # EMPTY — annotate manually if judgment exists
    ("бухими поедем на полигон",
     []),

    # EMPTY — annotate manually if judgment exists
    ("там есть чел который меня ирл знает",
     []),

    # AUTO — review needed
    ("дневник это часть ментальных внутренностей",
     [("дневник", "cop:это", "часть", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("меня позвали завтра на собеседование",
     []),

    # EMPTY — annotate manually if judgment exists
    ("не можешь придумать чем себя занять?",
     []),

    # AUTO — review needed
    ("брат переведется из школы скорее всего",
     [("школа", "перевестись", "брат", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("в итоге она махнула на меня рукой со словами \"в пизду\"",
     []),

    # EMPTY — annotate manually if judgment exists
    ("по рисункам мало что понятно",
     []),

    # EMPTY — annotate manually if judgment exists
    ("как много я этого хотел",
     []),

    # AUTO — review needed
    ("просто я ПОЛНОСТЬЮ (вроди ...) согласен (уже говорил такое)",
     [("я", "cop:это", "согласный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("не для всех языков есть много библиотек и фреймворков",
     []),

    # EMPTY — annotate manually if judgment exists
    ("в дневнике недавно что-то похожее высирал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("В России он зарегистрирован как лекарство, в других странах (например, США) продается как добавка.",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я бы хотела чтобы ты чувствовала себя лучше",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я взял это и прикрутил нейронку которая сама формирует группы по смыслу слов из названия и описания товаров",
     []),

    # EMPTY — annotate manually if judgment exists
    ("его будет больше думаю когда выйду на работу",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну да хуй с ним просто гештальт",
     []),

    # AUTO — review needed
    ("от этого я не запоминал многое",
     [("я", "запоминать", "многое", "N")]),

    # EMPTY — annotate manually if judgment exists
    ("я когда открыл его для себя охуел",
     []),

    # EMPTY — annotate manually if judgment exists
    ("это было сказано с тем что я расстроен блять нахуй этим фактом",
     []),

    # EMPTY — annotate manually if judgment exists
    ("хочу сделать рисунок который будет формироваться цельным как бы при наложении половины рисунка из цыфры и половина – фотка с бумаги",
     []),

    # EMPTY — annotate manually if judgment exists
    ("у нас просто нет размеченных данных",
     []),

    # EMPTY — annotate manually if judgment exists
    ("уже не актуально то моë высказывание извини",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну я думал об этом и после",
     []),

    # EMPTY — annotate manually if judgment exists
    ("если нужно можешь спрашивать, получать обратную ссвязь, если нужно",
     []),

    # EMPTY — annotate manually if judgment exists
    ("казалось я реально это переживал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("решение для желания упороться",
     []),

    # EMPTY — annotate manually if judgment exists
    ("что ты хочешь сказать и твои методы не до конца понятны",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и кстати то, что ты чувствовала находясь в Украине, похожее у меня было в Питере",
     []),

    # AUTO — review needed
    ("пару минут на коллапсы волновых функций",
     [("функция", "amod", "волновой", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("это просто упрощает очень сильно работу и всё",
     []),

    # AUTO — review needed
    ("ты проделала титанический труд...",
     [("ты", "проделать", "труд", "A")]),

    # AUTO — review needed
    ("но возможно это все были проявления меня",
     [("проявление", "cop:это", "возможный", "A")]),

    # AUTO — review needed
    ("я задаю вопросы и мне говорят типо \"не глючь\" или \"так надо\"",
     [("я", "задавать", "вопрос", "A")]),

    # AUTO — review needed
    ("хочется развития и ветвления опыта",
     [("опыт", "хотеться", "развитие", "A"),
      ("опыт", "хотеться", "ветвление", "A")]),

    # AUTO — review needed
    ("В пространстве 1024 измерений косинусные расстояния сжимаются в узкий диапазон.",
     [("расстояние", "сжиматься", "пространство", "A"),
      ("расстояние", "сжиматься", "диапазон", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("в целом периодами симптомы уходят вообще",
     []),

    # EMPTY — annotate manually if judgment exists
    ("мне это самому нужно в том числе",
     []),

    # EMPTY — annotate manually if judgment exists
    ("своей бы хотел не чувствовать даже физической",
     []),

    # EMPTY — annotate manually if judgment exists
    ("сел тот телефон всё же",
     []),

    # EMPTY — annotate manually if judgment exists
    ("так что это нормально",
     []),

    # AUTO — review needed
    ("я много мужиков видел голыми в армии",
     [("я", "видеть", "армия", "A")]),

    # AUTO — review needed
    ("изучение копрофилии методами осознанных сновидений",
     [("сновидение", "amod", "осознанный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("дело больше в том что для меня значишь ты ..",
     []),

    # AUTO — review needed
    ("я падал в темноту",
     [("я", "падать", "темнота", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("в такой ситуации я ощущал что благополучие моё может быть сформировано после твоего благополучия",
     []),

    # AUTO — review needed
    ("первого типа там маниакальная фаза",
     [("тип", "cop:это", "фаза", "A"),
      ("фаза", "amod", "маниакальный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("ну мне было бы норм и без терапии и без девушек парней думаю",
     []),

    # EMPTY — annotate manually if judgment exists
    ("просто у него ебало такое",
     []),

    # EMPTY — annotate manually if judgment exists
    ("самое приятное из тактильного могу рассказать",
     []),

    # EMPTY — annotate manually if judgment exists
    ("В наших глазах есть три типа колбочек (светочувствительных клеток), каждый из которых отвечает за разные длины световых волн: L-колбочки преимущественно реагируют на красный цвет, S-колбочки — на синий.",
     []),

    # EMPTY — annotate manually if judgment exists
    ("даже пересекались в игре но не факт и смутно помню",
     []),

    # EMPTY — annotate manually if judgment exists
    ("это акты любви с чем-то и кем-то",
     []),

    # EMPTY — annotate manually if judgment exists
    ("нейросети многократно перепроверяют сами себя",
     []),

    # EMPTY — annotate manually if judgment exists
    ("да, я тоже понимаю что люди могут стать такими",
     []),

    # EMPTY — annotate manually if judgment exists
    ("меня будут с интересом слушать но ничего в ответ не последует",
     []),

    # EMPTY — annotate manually if judgment exists
    ("и пытаются наебать на еще больше",
     []),

    # AUTO — review needed
    ("я думал как приятно было бы чтоб люди побыли друг с другом как хобби новое интересное",
     [("человек", "побыть", "хобби", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("оно не берется как таковое",
     []),

    # EMPTY — annotate manually if judgment exists
    ("Усиливают успокаивающий эффект глицина.",
     []),

    # EMPTY — annotate manually if judgment exists
    ("если нужно полежать полежи или дела утрешние",
     []),

    # AUTO — review needed
    ("это о духовных практиках",
     [("практика", "amod", "духовный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("я хотел это услышать",
     []),

    # EMPTY — annotate manually if judgment exists
    ("вот что пусть посмотрят на жизнь иначе это правда",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я восприму нормально даже если прямо сейчас мы замолчим навсегда",
     []),

    # AUTO — review needed
    ("я изначально просто сказал за необходимость фармацевтического подспорья/инструмента/лечения",
     [("я", "сказать", "необходимость", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("прости что мало сказал про историю с человеком",
     []),

    # AUTO — review needed
    ("я услышал это с разных сторон",
     [("я", "услышать", "сторона", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("мне кажется я мог бы быть с тобой",
     []),

    # EMPTY — annotate manually if judgment exists
    ("попробую найти изображения которые бы передали ощущение..",
     []),

    # EMPTY — annotate manually if judgment exists
    ("кожа трескается и сыпется",
     []),

    # AUTO — review needed
    ("я обнуляю все долги и обиды других людей внутри меня прямо сейчас",
     [("я", "обнулять", "долг", "A"),
      ("я", "обнулять", "обида", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("хотел подискутировать на тему травяных антибиотиков",
     []),

    # EMPTY — annotate manually if judgment exists
    ("вылететь в верхние слои там есть много космич мусора",
     []),

    # EMPTY — annotate manually if judgment exists
    ("хочу конвертить чат в векторную бд",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я и другие люди как скляночки с жидкостью разноцветною и когда они взаимодействуют в друг дружкиных жидкостях потихоньку виднееются цвета других людей",
     []),

    # EMPTY — annotate manually if judgment exists
    ("но не до конца мб выразил",
     []),

    # EMPTY — annotate manually if judgment exists
    ("но их я тоже переварил",
     []),

    # EMPTY — annotate manually if judgment exists
    ("сам я кодил очень мало",
     []),

    # EMPTY — annotate manually if judgment exists
    ("а справа стрелки это что",
     []),

    # EMPTY — annotate manually if judgment exists
    ("выбрать никнейм кем именно из участников взаимодействия является сам пользователь",
     []),

    # AUTO — review needed
    ("я из него выкарапкался в реальность и вон че написал",
     [("я", "выкарапкался", "реальность", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("я отдаюсь всем а не беру что-либо от них",
     []),

    # EMPTY — annotate manually if judgment exists
    ("но я понимаю что ты это вынес",
     []),

    # AUTO — review needed
    ("я пью чай с чебрецом, перцем и солью",
     [("я", "пить", "чай", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("все что хотел но еще нужно привести в чувства локальную модель, составить нормальный тех.",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я очень много писал там",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну я думал об этом и после",
     []),

    # AUTO — review needed
    ("настолько что я не уверен что я сам могу бросить человека",
     [("я", "cop:это", "уверенный", "N")]),

    # AUTO — review needed
    ("я снова как бы столкнулся с идеей напрямую вот смотрю",
     [("я", "столкнуться", "идея", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("типо, не секунда, и не минута",
     []),

    # AUTO — review needed
    ("но я отношусь с уважением ко всем с кем контактирую",
     [("я", "относиться", "уважение", "A")]),

    # AUTO — review needed
    ("какое-то время я жил под такие треки",
     [("я", "жить", "время", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("пока не читай этот пост",
     []),

    # AUTO — review needed
    ("я больше смотрю на любознательность",
     [("я", "смотреть", "любознательность", "A")]),

    # AUTO — review needed
    ("вообще в целом неприязнь к людям крайне редко испытываю",
     [("неприязнь", "испытывать", "целое", "A")]),

    # AUTO — review needed
    ("какая это многомерная залупа",
     [("залупа", "amod", "многомерный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("можно готовить и мыть посуду",
     []),

    # AUTO — review needed
    ("но я видел себя никак младенца",
     [("я", "видеть", "младенец", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("у меня было много проектов связано с майном",
     []),

    # EMPTY — annotate manually if judgment exists
    ("остальное меня мало волнует",
     []),

    # AUTO — review needed
    ("каждое слово наполняется смыслом, наносится на карту (сейчас там 1024 измерения как x, y, z но больше гораздо)",
     [("смысл", "наполняться", "слово", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("просто \"что-то\", с чем я себя ассицировал",
     []),

    # AUTO — review needed
    ("Самая сильная часть — асимметрия включения.",
     [("часть", "cop:это", "асимметрия", "A")]),

    # AUTO — review needed
    ("смерть была и без людей",
     [("смерть", "cop:это", "человек", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("да не хочется что-то",
     []),

    # EMPTY — annotate manually if judgment exists
    ("В поиске ваш канал могут находить:",
     []),

    # EMPTY — annotate manually if judgment exists
    ("мб и не стоит",
     []),

    # EMPTY — annotate manually if judgment exists
    ("многие пишут ака \"записки шизика\"",
     []),

    # AUTO — review needed
    ("ну просто там ьейки в пользу моего подхода и я хотел бы от тебя тейков в пользу твоего",
     [("я", "хотеть", "польза", "A")]),

    # AUTO — review needed
    ("ты на практике проверяй",
     [("ты", "проверяй", "практика", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("нет, что они создадут fvsc",
     []),

    # EMPTY — annotate manually if judgment exists
    ("он меня сам нашел и открыл занавес к людям похожим на меня больше чем окружающие",
     []),

    # EMPTY — annotate manually if judgment exists
    ("он сказал что думал что уже меня потерял",
     []),

    # EMPTY — annotate manually if judgment exists
    ("да, такой человек волшебный",
     []),

    # EMPTY — annotate manually if judgment exists
    ("щас я стены долбил",
     []),

    # EMPTY — annotate manually if judgment exists
    ("селекции плохо определена, аналогия с генами слишком свободна.",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну поглядим что и как будет работать",
     []),

    # AUTO — review needed
    ("Нужна дополнительная фильтрация — например, учёт типа",
     [("фильтрация", "cop:это", "нужный", "A"),
      ("тип", "cop:это", "нужный", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("тебе канва может сделать то что надо?",
     []),

    # AUTO — review needed
    ("я говрю в конце \"не неполноценнсть, не недоразвитость\"",
     [("я", "говрю", "конец", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("Довольно пресная штука как будто если бы мы составляли диаграмму вкуса то 60% было бы за престностью и хлебной безвкусностью (как у хлебца/крекера без вкуса) остальное занимает креветко и хзвкус кошачьего корма (наверное что-то конкретное вызывает такую ассоциацию т.",
     []),

    # EMPTY — annotate manually if judgment exists
    ("я помогал ей недавно убираться и с любопытством подошел к новому месту и задачам и она увидела это",
     []),

    # AUTO — review needed
    ("частая проблема с такими людьми",
     [("проблема", "amod", "частый", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("поздно ложусь если занят чемьо",
     []),

    # AUTO — review needed
    ("да, я чуть не стал фембоем какта",
     [("я", "стать", "фембоем", "N")]),

    # EMPTY — annotate manually if judgment exists
    ("а там двое срочников ебут аянами рей",
     []),

    # AUTO — review needed
    ("ушел в отрийание через боль одиночесва",
     [("одиночесва", "уйти", "отрийание", "A"),
      ("одиночесва", "уйти", "боль", "A")]),

    # AUTO — review needed
    ("ну визуально это будет сверхдетальная картинка наверное",
     [("картинка", "amod", "сверхдетальная", "A")]),

    # AUTO — review needed
    ("где меня \"разрывают\" на части люди",
     [("человек", "разрывать", "часть", "A")]),

    # AUTO — review needed
    ("ну люди в целом открывают в себе нечто большее",
     [("человек", "открывать", "целое", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("но мне даже может быть некомфортно от этой музыки",
     []),

    # EMPTY — annotate manually if judgment exists
    ("в том числе поддержка экспорта тг формата",
     []),

    # EMPTY — annotate manually if judgment exists
    ("стал тем кого не понимал",
     []),

    # EMPTY — annotate manually if judgment exists
    ("не могу пока оценить",
     []),

    # EMPTY — annotate manually if judgment exists
    ("могу скинуть промт или примерный код и инструкции",
     []),

    # AUTO — review needed
    ("только то что ты сказал бро)",
     [("ты", "сказать", "бро", "A")]),

    # EMPTY — annotate manually if judgment exists
    ("как определить настроение и характер",
     []),

    # EMPTY — annotate manually if judgment exists
    ("ну ксьати есть такое",
     []),

    # EMPTY — annotate manually if judgment exists
    ("кажется только так вся жидкость в склянке может принять другие цвета целиком ощутить полное слияние",
     []),

    # EMPTY — annotate manually if judgment exists
    ("как бы если что заранее скажу если захочешь принять участие",
     []),

    # EMPTY — annotate manually if judgment exists
    ("У меня тоже нет, поэтому я пошёл в расход вскоре после того, как нашёл и физически принудил его употреблять бупропион, что наконец сняло депрессию",
     []),

    # EMPTY — annotate manually if judgment exists
    ("поле и суммировать то, что уже собирается.",
     []),

]
