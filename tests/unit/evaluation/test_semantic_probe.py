from __future__ import annotations

import json
from pathlib import Path

from fvsc.evaluation.semantic_probe import (
    SemanticFact,
    facts_from_judgments,
    load_semantic_probe,
    run_semantic_capacity_probe,
    score_facts,
)
from fvsc.semantic import Judgment


FIXTURE = Path("data/fixtures/semantic_capacity_probe_v1.json")


def test_judgment_projection_preserves_core_and_explicit_negation() -> None:
    facts = facts_from_judgments(
        [Judgment("child", "go-01", "school", negation_scope=True)]
    )

    assert facts == frozenset(
        {
            SemanticFact("sentence_edge", "go-01", "ARG0", "child"),
            SemanticFact("sentence_edge", "go-01", "ARG1", "school"),
            SemanticFact("attribute", "go-01", "polarity", "-"),
        }
    )


def test_fact_score_counts_false_positive_and_false_negative() -> None:
    first = SemanticFact("sentence_edge", "want-01", "ARG0", "person")
    second = SemanticFact("sentence_edge", "want-01", "ARG1", "go-01")
    extra = SemanticFact("attribute", "want-01", "polarity", "-")

    score = score_facts([first, extra], [first, second])

    assert score.true_positive == 1
    assert score.false_positive == 1
    assert score.false_negative == 1
    assert score.f1 == 0.5


def test_frozen_probe_is_capacity_only_and_umr_retains_document_facts() -> None:
    report = run_semantic_capacity_probe(load_semantic_probe(FIXTURE))

    assert report["capacity_only"] is True
    assert report["promotion_eligible"] is False
    assert report["case_count"] == 4
    assert report["summary"]["umr"]["micro"]["f1"] == 1.0
    assert report["summary"]["judgment_core"]["micro"]["f1"] < 1.0
    assert report["summary"]["judgment_core"]["micro"]["false_negative"] > 0


def test_probe_script_output_is_json_and_matches_library(capsys, monkeypatch) -> None:
    from scripts.semantic_schema_probe import main

    monkeypatch.setattr("sys.argv", ["semantic_schema_probe.py"])
    assert main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output == run_semantic_capacity_probe(load_semantic_probe(FIXTURE))
