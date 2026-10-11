from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from fvsc.ingest import ParseConfig
from fvsc.ingest.vault_sync import VaultSyncConfig
from fvsc.interpretation import GeneratedClaim, GeneratedInterpretation, InterpretationStore
from fvsc.retrieval.concept_map import ConceptMap
from fvsc.service.app import create_app
from fvsc.service.runtime import VaultRuntime


class DialogueBackend:
    backend_id = "test.dialogue"
    model = "fake"
    prompt_version = "1"
    interpretation_layer = 3

    def __init__(self):
        self.history = ()

    def generate(self, question, sources, *, history=()):
        self.history = history
        return GeneratedInterpretation("Freedom needs attention.", (
            GeneratedClaim("Freedom needs attention.", (sources[0].label,)),
        ))


def test_dialogue_context_is_persistent_isolated_and_not_owner_evidence(tmp_path):
    (tmp_path / "note.md").write_text("Freedom needs attention. Freedom allows choice.", encoding="utf-8")
    runtime = VaultRuntime(tmp_path, sync_config=VaultSyncConfig(
        parser_config=ParseConfig(min_freq=1, min_token_len=2, max_concepts=None),
        materializer_dim=8, enable_russian_judgments=False,
    ))
    runtime.sync(sync_time=1.0)
    digest = runtime.ledger.digest
    backend = DialogueBackend()
    path = tmp_path / ".fvsc" / "interpretations.json"
    with TestClient(create_app(runtime, interpretation_backend=backend, auto_load=False)) as client:
        first = client.post("/v1/interpret", json={"question": "Freedom?", "conversation_id": "one"})
        assert first.status_code == 200
        first_id = first.json()["proposal_id"]
        next_turn = client.post("/v1/interpret", json={"question": "Why?", "conversation_id": "one",
                                                       "previous_proposal_ids": [first_id]})
        assert next_turn.status_code == 200
        assert backend.history == ({"question": "Freedom?", "answer": "Freedom needs attention."},)
        assert next_turn.json()["question"] == "Why?"
        assert client.get("/v1/dialogues/one").json()[0]["proposal_id"] == first_id
        assert client.get("/v1/dialogues").json()[0]["turns"] == 2
        third = client.post("/v1/interpret", json={"question": "What about it?", "conversation_id": "one",
            "previous_proposal_ids": [first_id, next_turn.json()["proposal_id"]]})
        assert third.status_code == 200  # first turn's topic survives two short follow-ups
        forbidden = client.post("/v1/interpret", json={"question": "Why?", "conversation_id": "two",
                                                       "previous_proposal_ids": [first_id]})
        assert forbidden.status_code == 422
        assert client.get("/v1/dialogues/two").json() == []
        assert runtime.ledger.digest == digest
        graph = client.get("/v1/map").json()
        assert graph["focus"] in {n["term"] for n in graph["nodes"]}
        assert client.get("/v1/map", params={"focus": "nonexistent-node-842"}).status_code == 404
        text = graph["focus"] + " <script>alert(1)</script>"
        parts = client.post("/v1/map/mentions", json={"texts": [text]}).json()[0]
        assert "".join(p["text"] for p in parts) == text
        assert parts[0]["term"] == graph["focus"]
        assert client.get("/health").json()["vault_id"]
    assert len(InterpretationStore(path).journal.proposals) == 3
    with TestClient(create_app(runtime, interpretation_backend=backend, auto_load=False)) as client:
        assert len(client.get("/v1/dialogues/one").json()) == 3


def test_map_mentions_are_exact_longest_and_text_preserving():
    snapshot = SimpleNamespace(snapshot_id="snapshot", concepts=[
        SimpleNamespace(term=t, evidence_ids=("e",)) for t in ("смысл", "личный смысл", "свобода")
    ])
    graph = ConceptMap(snapshot, SimpleNamespace(active_events=()))
    text = "Личный смысл, бессмыслица и СВОБОДА 🪶 <b>."
    result = graph.mentions(text)
    assert "".join(p["text"] for p in result) == text
    assert [p["term"] for p in result if p["term"]] == ["личный смысл", "свобода"]
    assert graph.view("смысл")["nodes"][0]["term"] == "смысл"
    assert graph.view("смысл")["edges"] == []


def test_map_preserves_polarity_and_bounds_neighbors():
    terms = ["focus", *(f"node{i}" for i in range(40))]
    snapshot = SimpleNamespace(snapshot_id="snapshot", concepts=[SimpleNamespace(term=t, evidence_ids=("e",)) for t in terms])
    events = [SimpleNamespace(subject="focus", object=t, relation="requires", polarity=-1 if i % 2 else 1,
                              modality=0.5, source_id="note.md") for i, t in enumerate(terms[1:])]
    graph = ConceptMap(snapshot, SimpleNamespace(active_events=events))
    result = graph.view("focus")
    assert len(result["nodes"]) == 17
    assert result["total_neighbors"] == 40
    assert {e["polarity"] for e in result["edges"]} == {-1, 1}
    assert all(e["modality"] == 0.5 and e["source_ids"] == ["note.md"] for e in result["edges"])
