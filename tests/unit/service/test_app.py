from __future__ import annotations

import os

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from fvsc.ingest import ParseConfig
from fvsc.ingest.vault_sync import VaultSyncConfig
from fvsc.interpretation import GeneratedClaim, GeneratedInterpretation
from fvsc.service.app import create_app
from fvsc.service.runtime import VaultRuntime


def _runtime(tmp_path) -> VaultRuntime:
    note = tmp_path / "note.md"
    note.write_text("Свобода требует ответственности.", encoding="utf-8")
    os.utime(note, (10.0, 10.0))
    return VaultRuntime(
        tmp_path,
        sync_config=VaultSyncConfig(
            parser_config=ParseConfig(min_freq=1, min_token_len=2, max_concepts=None),
            materializer_dim=16,
            enable_russian_judgments=False,
        ),
    )


class _Backend:
    backend_id = "test.backend"
    model = "fake"
    prompt_version = "1"
    interpretation_layer = 3

    def generate(self, question, sources):
        return GeneratedInterpretation(
            answer="Ответ с опорой на исходник.",
            claims=(
                GeneratedClaim(
                    text="Свобода связана с ответственностью.",
                    source_labels=("S1",),
                ),
            ),
        )


def test_http_transport_delegates_sync_search_source_interpretation_and_feedback(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    with TestClient(
        create_app(runtime, interpretation_backend=_Backend(), auto_load=False)
    ) as client:
        assert client.get("/health").json()["loaded"] is False
        synced = client.post("/v1/vault/sync")
        assert synced.status_code == 200
        assert synced.json()["source_count"] == 1

        search = client.post(
            "/v1/search",
            json={"query": "ответственность", "top_k": 1, "context_depth": 0},
        )
        assert search.status_code == 200
        body = search.json()
        assert body["ranking"] == "lexical-char-ngram-v1"
        assert body["semantic_reranking"] is False
        hit = body["hits"][0]

        source = client.get(
            "/v1/source",
            params={
                "source_id": hit["source_id"],
                "source_revision": hit["source_revision"],
            },
        )
        assert source.status_code == 200
        assert source.json()["text"] == "Свобода требует ответственности."

        proposal = client.post(
            "/v1/interpret",
            json={"question": "свобода и ответственность", "top_k": 1},
        )
        assert proposal.status_code == 200
        assert proposal.json()["citations"][0]["source_id"] == "note.md"
        assert proposal.json()["defeasible"] is True
        proposal_body = proposal.json()
        assessment = client.post(
            "/v1/interpret/assess",
            json={
                "proposal_id": proposal_body["proposal_id"],
                "case_id": "interactive-1",
                "verdict": "accepted",
                "accepted_claim_ids": [proposal_body["claims"][0]["claim_id"]],
                "recorded_at": 40.0,
            },
        )
        assert assessment.status_code == 200
        assert assessment.json()["verdict"] == "accepted"

        target = next(iter(runtime.ledger.active_events))
        feedback = client.post(
            "/v1/feedback",
            json={
                "target_event_id": target.event_id,
                "action": "confirm",
                "observed_at": 30.0,
            },
        )
        assert feedback.status_code == 200
        assert feedback.json()["target_event_id"] == target.event_id


def test_unconfigured_app_is_healthy_but_refuses_stateful_routes() -> None:
    with TestClient(
        create_app(None, interpretation_backend=None, auto_load=False)
    ) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "unconfigured"
        assert client.get("/v1/status").status_code == 503
