from __future__ import annotations

import json
from pathlib import Path

from core.natural_language_benchmark import (
    BENCHMARK_VERSION,
    CORPUS_SCHEMA,
    evaluate_corpus,
    html_to_text,
)


def _record(
    *,
    record_id: str,
    thread_id: str,
    record_type: str,
    created_at: float,
    text: str,
) -> dict:
    return {
        "schema": CORPUS_SCHEMA,
        "record_id": record_id,
        "thread_id": thread_id,
        "record_type": record_type,
        "created_at": created_at,
        "text": text,
        "source_url": f"https://example.invalid/questions/{thread_id}/{record_id}",
        "site": "fixture",
        "license": "CC BY-SA 4.0",
        "author_name": f"author-{record_id}",
        "author_url": f"https://example.invalid/users/{record_id}",
        "modified_from_html": True,
        "usage_purpose": "evaluation_only_no_llm_training",
    }


def test_html_cleanup_preserves_quotes_and_removes_code() -> None:
    cleaned = html_to_text(
        "<p>People build trust through dialogue.</p>"
        "<blockquote>Trust requires attention.</blockquote>"
        "<pre><code>print('not prose')</code></pre>"
    )
    assert "People build trust" in cleaned
    assert "[QUOTE]" in cleaned
    assert "Trust requires attention" in cleaned
    assert "print" not in cleaned


def test_public_thread_benchmark_is_grouped_and_deterministic(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    records = []
    for index in range(8):
        thread = str(index + 1)
        created = 1_000.0 + index * 100.0
        records.extend(
            [
                _record(
                    record_id=f"q-{thread}",
                    thread_id=thread,
                    record_type="question",
                    created_at=created,
                    text=(
                        "Planning requires trust and communication. "
                        "Trust supports planning and careful communication. "
                        f"In situation {index}, planning and trust remain important."
                    ),
                ),
                _record(
                    record_id=f"a-{thread}",
                    thread_id=thread,
                    record_type="answer",
                    created_at=created + 10.0,
                    text=(
                        "Clear communication strengthens trust. "
                        "Trust improves planning, while planning guides communication. "
                        f"This answer discusses situation {index} and practical planning."
                    ),
                ),
            ]
        )
    corpus.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in records),
        encoding="utf-8",
    )

    first_output = tmp_path / "report-one.json"
    second_output = tmp_path / "report-two.json"
    first = evaluate_corpus(
        corpus,
        output_path=first_output,
        train_fraction=0.75,
        bootstrap_samples=100,
    )
    second = evaluate_corpus(
        corpus,
        output_path=second_output,
        train_fraction=0.75,
        bootstrap_samples=100,
    )

    assert first["benchmark"] == BENCHMARK_VERSION
    assert first["corpus"]["records"] == 16
    assert first["corpus"]["threads"] == 8
    assert first["corpus"]["attribution_complete_rate"] == 1.0
    assert first["parser_diagnostics"]["parseable_threads"] == 8
    assert first["evaluation"]["train_documents"] == 6
    assert first["evaluation"]["test_documents"] == 2
    assert first["evaluation"]["benchmark"] == "fvsc-chronological-heldout-v1"
    assert first["evaluation"]["verdict"] in {
        "insufficient_data",
        "promising_added_value",
        "not_predictive",
        "no_demonstrated_added_value",
    }
    # Generated timestamps differ, but scientific outputs from the frozen corpus do not.
    assert first["evaluation"] == second["evaluation"]
    assert first["parser_diagnostics"] == second["parser_diagnostics"]
    assert first_output.exists()
    assert second_output.exists()
