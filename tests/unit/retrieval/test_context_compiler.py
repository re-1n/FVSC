from __future__ import annotations

import pytest

from fvsc.retrieval import SemanticContextCompiler, SemanticContextUnit


def _units() -> tuple[SemanticContextUnit, ...]:
    guard = SemanticContextUnit(
        unit_id="N001",
        text="Нельзя утверждать, что метафора совместно принята обоими участниками.",
        kind="guard",
        voice="review",
        polarity="negative",
        owner_decision="confirmed",
        reason="Метафора принадлежит только одному участнику.",
    )
    return (
        SemanticContextUnit(
            unit_id="M001",
            text="Метафора красок была предложена одним участником.",
            voice="speaker-a",
            adoption="speaker-b:not_adopted",
            owner_decision="confirmed",
            guard_ids=("N001",),
            related_ids=("M002",),
        ),
        SemanticContextUnit(
            unit_id="M002",
            text="Финал содержит локальное взаимопонимание.",
            voice="interaction",
            adoption="two-party-confirmed",
            owner_decision="confirmed",
        ),
        guard,
    )


def test_compiler_ranks_surface_match_and_preserves_linked_guard() -> None:
    result = SemanticContextCompiler(_units()).compile(
        "как участники приняли метафору красок?",
        token_budget=500,
        top_k=2,
    )

    assert {item.unit_id for item in result.units} == {"M001", "N001"}
    assert "adoption=speaker-b:not_adopted" in result.rendered
    assert "Нельзя утверждать" in result.rendered
    assert "PROHIBITED_CLAIM — NEVER REPEAT AS FACT" in result.rendered
    assert "REASON_OR_CORRECTION" in result.rendered
    assert result.estimated_tokens <= result.token_budget


def test_compiler_budget_never_splits_meaning_from_required_guard() -> None:
    compiler = SemanticContextCompiler(_units(), token_counter=len)
    one_unit_length = len(compiler.by_id["M001"].render())

    result = compiler.compile(
        "метафора красок",
        token_budget=one_unit_length,
        top_k=2,
    )

    assert result.units == ()
    assert "M001" in result.omitted_ranked_ids


def test_compiler_is_deterministic_and_validates_contracts() -> None:
    compiler = SemanticContextCompiler(_units())
    first = compiler.compile("взаимопонимание в финале", token_budget=500, top_k=2)
    replay = compiler.compile("взаимопонимание в финале", token_budget=500, top_k=2)

    assert first == replay
    with pytest.raises(ValueError, match="query"):
        compiler.compile("", token_budget=10)
    with pytest.raises(ValueError, match="token_budget"):
        compiler.compile("query", token_budget=0)
    with pytest.raises(ValueError, match="missing guards"):
        SemanticContextCompiler(
            (
                SemanticContextUnit(
                    unit_id="M003",
                    text="meaning",
                    guard_ids=("N404",),
                ),
            )
        )
    with pytest.raises(ValueError, match="guard_score_discount"):
        SemanticContextCompiler(_units(), guard_score_discount=0)
    with pytest.raises(ValueError, match="reason/correction"):
        SemanticContextUnit(unit_id="N002", text="forbidden", kind="guard")


def test_typed_expansion_includes_related_unit_and_its_guards() -> None:
    result = SemanticContextCompiler(_units()).compile(
        "метафора красок",
        token_budget=700,
        top_k=2,
        expand_related=True,
    )

    assert {"M001", "M002", "N001"} <= {item.unit_id for item in result.units}


def test_guard_correction_is_mandatory_but_related_unit_is_optional() -> None:
    correction = SemanticContextUnit(
        unit_id="M010",
        text="Подтверждённая положительная формулировка.",
        owner_decision="confirmed",
    )
    optional = SemanticContextUnit(
        unit_id="M011",
        text="Очень длинное необязательное продолжение. " * 30,
    )
    guard = SemanticContextUnit(
        unit_id="N010",
        text="Отвергнутая противоположная формулировка.",
        kind="guard",
        polarity="negative",
        modality="must-not-assert",
        reason="Владелец подтвердил M010.",
        correction_ids=("M010",),
        related_ids=("M011",),
    )

    result = SemanticContextCompiler((guard, correction, optional)).compile(
        "противоположная формулировка",
        token_budget=250,
        top_k=1,
        expand_related=True,
        require_positive=True,
    )

    assert [item.unit_id for item in result.units] == ["N010", "M010"]


def test_require_positive_fails_closed_for_guard_without_correction() -> None:
    guard = SemanticContextUnit(
        unit_id="N020",
        text="Неподдержанное утверждение.",
        kind="guard",
        reason="Источник этого не устанавливает.",
    )

    result = SemanticContextCompiler((guard,)).compile(
        "неподдержанное утверждение",
        token_budget=100,
        require_positive=True,
    )

    assert result.units == ()
    assert result.rendered == ""


def test_reviewed_retrieval_cues_bridge_paraphrase_without_becoming_evidence() -> None:
    desired_response = SemanticContextUnit(
        unit_id="M030",
        text="Сначала показать отношение и понимание, не предлагая немедленного решения.",
        voice="participant",
        owner_decision="confirmed",
        retrieval_cues=("какого способа ответа хотела участница",),
    )
    surface_distractor = SemanticContextUnit(
        unit_id="M031",
        text="Участница хотела самостоятельно найти способ завершить ответ.",
        voice="participant",
        owner_decision="candidate",
    )
    compiler = SemanticContextCompiler((desired_response, surface_distractor))

    baseline = compiler.compile(
        "Какого способа ответа хотела участница?",
        token_budget=200,
        top_k=1,
    )
    cued = compiler.compile(
        "Какого способа ответа хотела участница?",
        token_budget=200,
        top_k=1,
        use_retrieval_cues=True,
    )

    assert [item.unit_id for item in baseline.units] == ["M031"]
    assert [item.unit_id for item in cued.units] == ["M030"]
    assert baseline.ranking_method == "unicode-char-ngram-v1"
    assert cued.ranking_method == "unicode-char-ngram-with-reviewed-cues-v1"
    assert "какого способа ответа" not in cued.rendered.casefold()


@pytest.mark.parametrize(
    "retrieval_cues, message",
    [
        (("",), "non-empty and trimmed"),
        ((" cue",), "non-empty and trimmed"),
        (("duplicate", "duplicate"), "unique"),
    ],
)
def test_retrieval_cues_are_validated(
    retrieval_cues: tuple[str, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        SemanticContextUnit(
            unit_id="M040",
            text="meaning",
            retrieval_cues=retrieval_cues,
        )


def test_tfidf_downweights_corpus_common_distractor_without_changing_budget() -> None:
    target = SemanticContextUnit(
        unit_id="TARGET",
        text="The palette metaphor describes adoption.",
    )
    distractor = SemanticContextUnit(
        unit_id="DISTRACTOR",
        text=(
            "How does the participant relate to this account? "
            "The participant relationship is described here."
        ),
    )
    common = tuple(
        SemanticContextUnit(
            unit_id=f"COMMON{index:02d}",
            text=f"The participant describes a relationship and account number {index}.",
        )
        for index in range(10)
    )
    compiler = SemanticContextCompiler((target, distractor, *common))
    query = "How does the participant relate to the palette metaphor?"

    cosine = compiler.compile(
        query,
        token_budget=200,
        top_k=1,
        ranking_method="char_cosine",
    )
    tfidf = compiler.compile(
        query,
        token_budget=200,
        top_k=1,
        ranking_method="char_tfidf",
    )

    assert [item.unit_id for item in cosine.units] == ["DISTRACTOR"]
    assert [item.unit_id for item in tfidf.units] == ["TARGET"]
    assert tfidf.estimated_tokens <= tfidf.token_budget == cosine.token_budget
    assert tfidf.ranking_method == "unicode-char-tfidf-v1"


def test_compiler_rejects_unknown_ranking_method() -> None:
    with pytest.raises(ValueError, match="ranking_method"):
        SemanticContextCompiler(_units()).compile(
            "query",
            token_budget=100,
            ranking_method="unknown",  # type: ignore[arg-type]
        )


def test_external_scores_are_auditable_and_preserve_compiler_contract() -> None:
    result = SemanticContextCompiler(_units()).compile(
        "semantic query",
        token_budget=500,
        top_k=1,
        ranking_method="external",
        external_scores={"M001": 0.9, "M002": 0.2, "N001": 0.1},
    )

    assert {item.unit_id for item in result.units} == {"M001", "N001"}
    assert result.ranking_method == "external-scores-v1"


def test_external_scores_fail_closed_on_incomplete_or_invalid_input() -> None:
    compiler = SemanticContextCompiler(_units())
    with pytest.raises(ValueError, match="requires external_scores"):
        compiler.compile(
            "query",
            token_budget=100,
            ranking_method="external",
        )
    with pytest.raises(ValueError, match="exactly every"):
        compiler.compile(
            "query",
            token_budget=100,
            ranking_method="external",
            external_scores={"M001": 0.5},
        )
    with pytest.raises(ValueError, match=r"finite and in \[0, 1\]"):
        compiler.compile(
            "query",
            token_budget=100,
            ranking_method="external",
            external_scores={"M001": 1.1, "M002": 0.2, "N001": 0.1},
        )
    with pytest.raises(ValueError, match="only with external"):
        compiler.compile(
            "query",
            token_budget=100,
            external_scores={"M001": 0.5, "M002": 0.2, "N001": 0.1},
        )


def test_minimum_score_fails_closed_and_records_weak_candidates() -> None:
    compiler = SemanticContextCompiler(
        (
            SemanticContextUnit(
                unit_id="M050",
                text="The participant discussed an unrelated practical decision.",
            ),
        )
    )

    result = compiler.compile(
        "What did the palette metaphor mean?",
        token_budget=100,
        top_k=1,
        minimum_score=0.2,
        require_positive=True,
    )

    assert result.units == ()
    assert result.rendered == ""
    assert result.below_threshold_ranked_ids == ("M050",)
    assert result.omitted_ranked_ids == ()


@pytest.mark.parametrize("minimum_score", [-0.01, 1.01, float("inf"), True])
def test_minimum_score_is_validated(minimum_score: object) -> None:
    with pytest.raises(ValueError, match="minimum_score"):
        SemanticContextCompiler(_units()).compile(
            "query",
            token_budget=100,
            minimum_score=minimum_score,  # type: ignore[arg-type]
        )
