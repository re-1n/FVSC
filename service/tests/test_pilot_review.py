from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from service import pilot_router, viz_router
from service.pilot_app import app
from service.pilot_review_router import ReviewMark, parse_review_marks


def _review(snapshot: str, *, freedom_useful: bool = True) -> str:
    freedom_positive = "x" if freedom_useful else " "
    freedom_negative = " " if freedom_useful else "x"
    return f"""# FVSC Pilot — Daily Review

Snapshot: `{snapshot}`

## свобода
- [{freedom_positive}] Полезно / точно
- [{freedom_negative}] Неточно / случайно

## доверие
- [ ] Полезно / точно
- [X] Неточно / случайно

## выбор
- [x] Полезно / точно
- [x] Неточно / случайно

## Recently active sources
- [x] Полезно / точно

## Notes
- пользовательский текст
"""


def test_parse_review_marks_extracts_only_unambiguous_concept_ratings() -> None:
    snapshot, marks, ambiguous = parse_review_marks(_review("abc123"))

    assert snapshot == "abc123"
    assert marks == [
        ReviewMark(term="свобода", useful=True, rating=5),
        ReviewMark(term="доверие", useful=False, rating=1),
    ]
    assert ambiguous == ["выбор"]


def test_review_feedback_is_persisted_idempotent_and_revisable(tmp_path: Path) -> None:
    note = tmp_path / "daily.md"
    note.write_text(
        "Свобода включает выбор и ответственность. "
        "Доверие укрепляет отношения.",
        encoding="utf-8",
    )
    viz_router.configure(vault_path=tmp_path)
    pilot_router._runtime = None
    pilot_router._feedback = []
    pilot_router._loaded_vault = None

    with TestClient(app, base_url="http://127.0.0.1") as client:
        rebuild = client.post("/pilot/rebuild")
        assert rebuild.status_code == 200, rebuild.text
        snapshot = rebuild.json()["snapshot_id"]
        text = _review(snapshot[:16])

        first = client.post(
            "/pilot/review-feedback",
            json={
                "text": text,
                "source_path": "_fvsc_review/FVSC Daily Review.md",
            },
        )
        assert first.status_code == 200, first.text
        first_data = first.json()
        assert first_data["submitted_count"] == 2
        assert first_data["ambiguous"] == ["выбор"]
        assert first_data["duplicates"] == []
        assert first_data["revisions"] == []
        assert all(record["snapshot_id"] == snapshot for record in first_data["submitted"])

        second = client.post(
            "/pilot/review-feedback",
            json={"text": text},
        )
        assert second.status_code == 200, second.text
        second_data = second.json()
        assert second_data["submitted_count"] == 0
        assert set(second_data["duplicates"]) == {"свобода", "доверие"}

        summary = client.get("/pilot/feedback/summary")
        assert summary.status_code == 200
        summary_data = summary.json()
        assert summary_data["count"] == 2
        assert summary_data["by_query_type"]["daily_review_concept"]["count"] == 2
        assert summary_data["by_query_type"]["daily_review_concept"]["useful_rate"] == 0.5

        revised = client.post(
            "/pilot/review-feedback",
            json={"text": _review(snapshot[:16], freedom_useful=False)},
        )
        assert revised.status_code == 200, revised.text
        revised_data = revised.json()
        assert revised_data["submitted_count"] == 1
        assert revised_data["revisions"] == ["свобода"]
        assert revised_data["duplicates"] == ["доверие"]
        assert revised_data["feedback_history_count"] == 3
        assert revised_data["feedback_count"] == 2
        assert revised_data["submitted"][0]["supersedes_feedback_id"] is not None

        readiness = client.get("/pilot/readiness")
        assert readiness.status_code == 200
        readiness_feedback = readiness.json()["feedback"]
        assert readiness_feedback["count"] == 2
        assert readiness_feedback["history_count"] == 3
        assert readiness_feedback["useful_rate"] == 0.0

    state_file = tmp_path / ".fvsc" / "pilot-state.json"
    assert state_file.exists()
