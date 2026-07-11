from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from service import pilot_router, viz_router
from service.pilot_app import app


def _reset_pilot(vault: Path) -> None:
    viz_router.configure(vault_path=vault)
    pilot_router._runtime = None
    pilot_router._feedback = []
    pilot_router._loaded_vault = None


def test_pilot_rebuild_live_update_trace_feedback_and_reload(tmp_path: Path) -> None:
    (tmp_path / "daily").mkdir()
    first = tmp_path / "daily" / "one.md"
    second = tmp_path / "daily" / "two.md"
    first.write_text(
        "# Мысль\n\nСвобода включает выбор и ответственность. "
        "Ответственность требует дисциплины.",
        encoding="utf-8",
    )
    second.write_text(
        "Доверие укрепляет отношения. Свобода требует честности.",
        encoding="utf-8",
    )
    (tmp_path / "_fvsc_concepts").mkdir()
    (tmp_path / "_fvsc_concepts" / "generated.md").write_text(
        "Этот файл не должен попадать в pilot.", encoding="utf-8"
    )

    _reset_pilot(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        rebuild = client.post("/pilot/rebuild")
        assert rebuild.status_code == 200, rebuild.text
        rebuilt = rebuild.json()
        assert rebuilt["files_seen"] == 2
        assert rebuilt["files_indexed"] >= 1
        assert rebuilt["active_event_count"] > 0
        assert rebuilt["concept_count"] > 0

        status = client.get("/pilot/status")
        assert status.status_code == 200
        assert status.json()["state_exists"] is True
        initial_snapshot = status.json()["snapshot_id"]

        concept = client.get("/pilot/concepts/свобода")
        assert concept.status_code == 200, concept.text
        concept_data = concept.json()
        assert concept_data["sources"]
        assert concept_data["related"]

        target = concept_data["related"][0]["term"]
        trace = client.post(
            "/pilot/trace",
            json={"source": "свобода", "target": target},
        )
        assert trace.status_code == 200, trace.text
        trace_data = trace.json()
        assert trace_data["query_id"]
        assert 0.0 <= trace_data["shape_overlap"] <= 1.0

        updated_text = (
            "Свобода включает выбор и ответственность. "
            "Свобода поддерживает творчество."
        )
        update = client.post(
            "/pilot/file_ingest",
            json={
                "path": "daily/one.md",
                "action": "modify",
                "text": updated_text,
                "observed_at": 10.0,
            },
        )
        assert update.status_code == 200, update.text
        assert update.json()["snapshot_id"] != initial_snapshot
        assert update.json()["updates"][0]["retracted_events"] > 0

        feedback = client.post(
            "/pilot/feedback",
            json={
                "query_id": trace_data["query_id"],
                "query_type": "trace",
                "rating": 4,
                "useful": True,
                "notes": "Связь выглядит правдоподобно.",
                "snapshot_id": trace_data["snapshot_id"],
            },
        )
        assert feedback.status_code == 201, feedback.text
        summary = client.get("/pilot/feedback/summary")
        assert summary.status_code == 200
        assert summary.json()["count"] == 1
        assert summary.json()["useful_rate"] == 1.0

        review = client.get("/pilot/daily-review?limit=5")
        assert review.status_code == 200, review.text
        assert review.json()["concepts"]

        evaluation = client.post(
            "/pilot/evaluate",
            json={
                "train_fraction": 0.5,
                "bootstrap_samples": 100,
                "max_files": 100,
            },
        )
        assert evaluation.status_code == 200, evaluation.text
        evaluation_data = evaluation.json()
        assert evaluation_data["benchmark"] == "fvsc-chronological-heldout-v1"
        assert evaluation_data["train_documents"] == 1
        assert evaluation_data["test_documents"] == 1
        assert evaluation_data["verdict"] in {
            "insufficient_data",
            "promising_added_value",
            "not_predictive",
            "no_demonstrated_added_value",
        }
        assert Path(evaluation_data["report_path"]).exists()

        latest = client.get("/pilot/evaluate/latest")
        assert latest.status_code == 200
        assert latest.json()["benchmark"] == "fvsc-chronological-heldout-v1"

    state_file = tmp_path / ".fvsc" / "pilot-state.json"
    assert state_file.exists()

    # Simulate a backend process restart and verify deterministic restoration.
    pilot_router._runtime = None
    pilot_router._feedback = []
    pilot_router._loaded_vault = None
    with TestClient(app, base_url="http://127.0.0.1") as client:
        restored = client.get("/pilot/status")
        assert restored.status_code == 200
        assert restored.json()["feedback_count"] == 1
        assert restored.json()["active_event_count"] > 0
