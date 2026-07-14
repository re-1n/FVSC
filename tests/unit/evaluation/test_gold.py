from __future__ import annotations

import json

import pytest

from fvsc.evaluation import (
    EvidenceRef,
    GoldCase,
    GoldLink,
    GoldSet,
    RankedSources,
    evaluate_rankings,
    load_gold_set,
)


def _gold() -> GoldSet:
    return GoldSet(
        schema_version=1,
        cases=(
            GoldCase(
                case_id="gold-001",
                title="Open metaphor",
                question="Какую роль играет образ?",
                decision="accepted",
                evidence=(
                    EvidenceRef("Diary:2", "message-2", "primary"),
                    EvidenceRef("Diary:1", "message-1", "context"),
                    EvidenceRef("Diary:3", "message-3", "support"),
                    EvidenceRef("Diary:9", "message-9", "negative"),
                ),
                links=(
                    GoldLink("Diary:1", "Diary:2", "context"),
                    GoldLink("Diary:2", "Diary:9", "separate"),
                ),
                owner_interpretation="Meaning remains free text.",
            ),
            GoldCase(
                case_id="gold-012",
                title="Rejected composite",
                question="Should these notes be merged?",
                decision="excluded",
                evidence=(),
                rejected_interpretations=("One composite meaning",),
            ),
        ),
    )


def test_gold_round_trip_keeps_free_meaning_and_negative_links(tmp_path) -> None:
    gold = _gold()
    path = tmp_path / "gold.json"
    path.write_text(json.dumps(gold.to_dict(), ensure_ascii=False), encoding="utf-8")

    restored = load_gold_set(path)

    assert restored == gold
    assert restored.cases[0].owner_interpretation == "Meaning remains free text."
    assert restored.cases[0].links[1].decision == "separate"


def test_rank_evaluation_scores_sources_context_negatives_and_abstention() -> None:
    result = evaluate_rankings(
        _gold(),
        [
            RankedSources(
                case_id="gold-001",
                source_ids=("message-9", "message-2", "message-3", "message-1"),
            ),
            RankedSources(case_id="gold-012", abstained=True),
        ],
        top_k=3,
    )

    first = result.cases[0]
    assert first.reciprocal_rank == pytest.approx(0.5)
    assert first.recall_at_k == pytest.approx(1.0)
    assert first.context_recall_at_k == pytest.approx(0.0)
    assert first.negative_hits_at_k == 1
    assert result.abstention_accuracy == pytest.approx(1.0)
    assert result.negative_hits_at_k == 1


def test_schema_rejects_duplicate_refs_unknown_links_and_invalid_rankings() -> None:
    with pytest.raises(ValueError, match="duplicate evidence"):
        GoldCase(
            case_id="x",
            title="x",
            question="x",
            decision="open",
            evidence=(EvidenceRef("A", None), EvidenceRef("A", None)),
        )
    with pytest.raises(ValueError, match="unknown evidence"):
        GoldCase(
            case_id="x",
            title="x",
            question="x",
            decision="open",
            evidence=(EvidenceRef("A", None),),
            links=(GoldLink("A", "B", "linked"),),
        )
    with pytest.raises(ValueError, match="abstained"):
        RankedSources(case_id="x", source_ids=("a",), abstained=True)
