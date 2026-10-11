import hashlib

import pytest
from fastapi.testclient import TestClient

from fvsc.ingest.vault_ingest import SourceDocument
from fvsc.interpretation.clarifications import ClarificationStore
from fvsc.service.app import create_app
from fvsc.service.runtime import VaultRuntime
from fvsc.ingest.vault_sync import VaultSyncConfig


class Runtime:
    def __init__(self):
        self.doc = SourceDocument.create(source_id="note.md", source_revision=hashlib.sha256(b"revision").hexdigest(),
                                         text="Чужая цитата 🪶", observed_at=1.0, adapter="test")

    def source_document(self, source_id):
        if source_id != self.doc.source_id:
            raise KeyError(source_id)
        return self.doc


@pytest.fixture
def setup():
    runtime = Runtime()
    store = ClarificationStore(":memory:")
    app = create_app(runtime, interpretation_backend=None, clarification_store=store, auto_load=False)
    with TestClient(app) as client:
        yield client, runtime, store
    store.close()


def request(runtime):
    return {"source_id": "note.md", "source_revision": runtime.doc.source_revision,
            "start": 0, "end": len(runtime.doc.text), "question": "Моя позиция?"}


def test_transport_full_loop_with_no_llm(setup):
    client, runtime, store = setup
    prepared = client.post("/v1/clarifications/prepare", json=request(runtime))
    assert prepared.status_code == 200
    body = prepared.json()
    assert body["status"] == "pending"
    answer = client.post("/v1/clarifications/answer", json={
        "clarification_id": body["clarification_id"], "action": "agree",
    })
    assert answer.status_code == 200
    assert answer.json()["usable_as_owner_position"] is True
    assert client.post("/v1/clarifications/prepare", json=request(runtime)).json() == answer.json()
    assert len(store.history(body["clarification_id"])) == 1


def test_transport_rejects_stale_missing_and_invalid_targets(setup):
    client, runtime, _ = setup
    payload = request(runtime)
    assert client.post("/v1/clarifications/prepare", json={**payload, "source_revision": "f" * 64}).status_code == 409
    assert client.post("/v1/clarifications/prepare", json={**payload, "source_id": "absent.md"}).status_code == 404
    for invalid in ({"end": 9999}, {"start": True}, {"question": "  "}, {"start": 3, "end": 2}):
        assert client.post("/v1/clarifications/prepare", json={**payload, **invalid}).status_code == 422
    assert client.post("/v1/clarifications/answer", json={"clarification_id": "f" * 64, "action": "agree"}).status_code == 404


def test_real_vault_restart_preserves_skip_and_keeps_ingest_independent(tmp_path):
    note = tmp_path / "note.md"
    original = "Я сохранил чужую мысль: можно передумать."
    note.write_text(original, encoding="utf-8")
    runtime = VaultRuntime(tmp_path, sync_config=VaultSyncConfig(enable_russian_judgments=False))
    runtime.sync(sync_time=1.0)
    doc = runtime.documents[0]
    ledger_before = runtime.ledger.digest
    payload = {"source_id": doc.source_id, "source_revision": doc.source_revision,
               "start": 0, "end": len(doc.text), "question": "Что я думаю об изменениях?"}
    with TestClient(create_app(runtime, interpretation_backend=None, auto_load=False)) as client:
        prepared = client.post("/v1/clarifications/prepare", json=payload)
        assert prepared.status_code == 200
        target_id = prepared.json()["clarification_id"]
        saved = client.post("/v1/clarifications/answer", json={"clarification_id": target_id, "action": "skip"})
        assert saved.json()["status"] == "deferred"
    assert note.read_text(encoding="utf-8") == original
    assert runtime.ledger.digest == ledger_before
    with TestClient(create_app(runtime, interpretation_backend=None, auto_load=False)) as client:
        assert client.post("/v1/clarifications/prepare", json=payload).json()["status"] == "deferred"
        note.write_text(original + " Я передумал.", encoding="utf-8")
        runtime.sync(sync_time=2.0)
        stale = client.post("/v1/clarifications/answer", json={"clarification_id": target_id, "action": "agree"})
        assert stale.status_code == 409
    assert len(runtime.documents) == 1  # journal is not ingested as a source
