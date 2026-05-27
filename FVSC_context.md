FVSC whitepaper (2716 строк) — детальная архитектура:

ЯДРО: значение = содержимое контейнера. Каждое понятие — ρ (density matrix). Граф = view поверх ρ.

МАТЕМАТИКА: ρ(A)=Σwᵢ|vᵢ⟩⟨vᵢ|; contain(A→B)=Tr(ρ_A·ρ_B)/Tr(ρ_A); грани=собств.векторы ρ; S(ρ)=полисемия; recursive: ρₖ₊₁=α·ρ_direct+(1-α)·Σwᵢ·transform(ρₖ(Bᵢ),rᵢ); три уровня изоморфны TreeRNN+PCA+GNN, детерминированы; мера Лёвнера (Bankova/Coecke 2019)

СПЕКТР L0-L3:
- L0: S→V→O синтаксис (93%, defeasible=False)
- L0.5: пресуппозиции/следствия (95-98%, конеч. триггеры)
- L1: импликатуры скаляр./конвенц. (85-90%)
- L1.5: фрейм.активация — незаполн. роли = открытые вопросы (80-85%)
- L2: RST дискурс (65-75%)
- L2.5: метафора через selectional violation (60-70%)
- L3: LLM-Антураж
Judgment: interpretation_layer, inference_chain, defeasible, extraction_confidence

ПРИНЦИПЫ: стенограф а не зеркало (Box); накопление а не обучение; детерминизм; глагол=связка+контейнер; ВСЕ значимые слова — контейнеры; карта отражает восприятие; «лучше потерять связь чем записать неверную»

КОД (core/):
- АГНОСТИК ГОТОВ: basis_vectors (Random Indexing), semantic_input (outer prod+partial trace), text_parser_agnostic (regex+co-occ), тесты
- SPACY LEGACY с критич. L0-L0.5+ логикой: tree_extractor (рекурс. обход, neg-raising, кванторы, мод.оболочки), density_core (Judgment), context_classifier (GENERIC/REFERENTIAL/QUOTE/SELF)
- interactive_map: единств. визуализация (spaCy внутри)

ОШИБКИ MOIX предложений: BGE-m3 как ОСНОВА для |ψ⟩ противоречит ρ (rank-1, импорт отвергнутых векторов); whitepaper НЕ опирается на Леонтьева — фундамент: Wittgenstein, Frege, Kelly, Coecke/Bankova, ACT-R, RST, Grice, Fodor

ЗАДАЧА: переписать как язык-агностик, сохранив архитектуру L0-L3 и мат. ядро