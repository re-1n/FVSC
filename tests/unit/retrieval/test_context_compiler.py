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
