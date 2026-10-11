import sqlite3
from types import SimpleNamespace

from fastapi.testclient import TestClient

from fvsc.ingest import ParseConfig
from fvsc.ingest.vault_sync import VaultSyncConfig
from fvsc.retrieval.concept_map import ConceptMap
from fvsc.retrieval.containers import ContainerStore
from fvsc.service.app import create_app
from fvsc.service.runtime import VaultRuntime


def test_recursive_composition_survives_restart_without_changing_evidence(tmp_path):
    note = tmp_path / "note.md"
    text = "Freedom allows choice. Choice needs attention."
    note.write_text(text, encoding="utf-8")
    runtime = VaultRuntime(tmp_path, sync_config=VaultSyncConfig(
        parser_config=ParseConfig(min_freq=1, min_token_len=2, max_concepts=None),
        materializer_dim=8, enable_russian_judgments=False,
    ))
    runtime.sync(sync_time=1.0)
    digest = runtime.ledger.digest
    with TestClient(create_app(runtime, auto_load=False)) as client:
        focus = client.get("/v1/map").json()["focus"]
        assert client.get("/v1/map/container", params={"focus": focus}).json()["components"] == []
        for parent, child in [(focus, "My component"), ("My component", "Deep concept"), ("Other", "Deep concept"), ("Deep concept", focus)]:
            response = client.post("/v1/map/component", json={"parent": parent, "child": child})
            assert response.status_code == 200
        graph = client.get("/v1/map/container", params={"focus": focus}).json()
        assert graph["components"] == ["My component"]
        assert graph["nodes"][1]["component_count"] == 1
        assert graph["nodes"][1]["source_count"] == 0
        assert all(n["term"] != "My component" for n in graph["suggestions"])
        assert client.post("/v1/map/component", json={"parent": focus, "child": focus}).status_code == 422
        assert client.post("/v1/map/component", json={"parent": focus, "child": "   "}).status_code == 422
        assert client.get("/v1/map/container", params={"focus": "\n"}).status_code == 422
    with TestClient(create_app(runtime, auto_load=False)) as client:
        assert client.get("/v1/map/container", params={"focus": "My component"}).json()["components"] == ["Deep concept"]
        assert "My component" in client.get("/v1/map/containers").json()
        assert client.post("/v1/map/component", json={"parent": focus, "child": "My component", "present": False}).status_code == 200
        assert client.get("/v1/map/container", params={"focus": focus}).json()["components"] == []
        # Removing membership doesn't delete the nested concept or other memberships.
        assert client.get("/v1/map/container", params={"focus": "Other"}).json()["components"] == ["Deep concept"]
        assert "My component" in client.get("/v1/map/containers").json()
    assert runtime.ledger.digest == digest
    assert note.read_text(encoding="utf-8") == text


def test_composition_keeps_links_beyond_neighborhood_limit():
    terms = ["a", *(f"b{i}" for i in range(30))]
    snapshot = SimpleNamespace(snapshot_id="s", concepts=[SimpleNamespace(term=t, evidence_ids=("e",)) for t in terms])
    events = [SimpleNamespace(subject="a", object=t, relation="requires", polarity=-1, modality=0.4, source_id="note") for t in terms[1:]]
    graph = ConceptMap(snapshot, SimpleNamespace(active_events=events))
    result = graph.composition("container", terms)
    assert len(result["edges"]) == 30
    assert all(e["polarity"] == -1 and e["modality"] == 0.4 for e in result["edges"])
    assert result["nodes"][0]["source_count"] == 0


def test_component_changes_are_idempotent_audited_and_bounded(tmp_path):
    path = tmp_path / "containers.sqlite3"
    store = ContainerStore(path)
    store.set_component("parent", " child ", True)
    store.set_component("parent", "child", True)
    store.set_component("parent", "child", False)
    store.set_component("parent", "child", False)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT action FROM changes").fetchall() == [("add",), ("remove",)]
    for i in range(100):
        store.set_component("parent", str(i), True)
    import pytest
    with pytest.raises(ValueError, match="100"):
        store.set_component("parent", "overflow", True)
    assert len(store.children("parent")) == 100
