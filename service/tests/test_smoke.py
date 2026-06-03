"""Smoke tests for FVSC Core Service — run against a live server.

Usage:
    Start the server in one terminal:
        python -m uvicorn service.app:app --host 127.0.0.1 --port 8765

    Then run tests:
        python -m pytest service/tests/test_smoke.py -v
"""

from __future__ import annotations

import httpx

BASE = "http://127.0.0.1:8765"


def _post_safe(path, json_dict):
    r = httpx.post(f"{BASE}{path}", json=json_dict)
    assert r.status_code in (200, 201, 409), f"{path}: {r.status_code} {r.text}"
    return r


def test_create_space():
    r = _post_safe("/spaces", {"name": "test", "dim": 32})
    data = r.json()
    assert data["name"] == "test"
    assert "dim" in data


def test_ingest():
    _post_safe("/spaces", {"name": "test", "dim": 32})
    r = _post_safe("/spaces/test/ingest", {
        "text": "Свобода требует ответственности. Ответственность включает долг и мужество. Любовь дает свободу и требует терпения.",
        "source_id": "note1",
        "format": "plain",
    })
    data = r.json()
    assert data["chunks_added"] >= 1
    assert data["concepts_total"] > 0


def test_concept_contains():
    r = httpx.get(f"{BASE}/spaces/test/concepts/свобода/contains?top_k=5")
    assert r.status_code == 200, f"contains: {r.status_code} {r.text}"
    assert len(r.json()) > 0


def test_concept_polysemy():
    r = httpx.get(f"{BASE}/spaces/test/concepts/свобода/polysemy")
    assert r.status_code == 200
    assert "polysemy" in r.json()


def test_concept_report():
    r = httpx.get(f"{BASE}/spaces/test/concepts/свобода/report")
    assert r.status_code == 200, f"report: {r.status_code} {r.text}"
    rep = r.json()
    assert rep["found"]
    assert rep["component_count"] > 0
    assert rep["contains"]


def test_similarity():
    r = httpx.get(f"{BASE}/spaces/test/similarity?a=свобода&b=ответственность")
    assert r.status_code == 200
    assert "similarity" in r.json()


def test_retrieve():
    r = httpx.post(f"{BASE}/spaces/test/retrieve", json={"query": "ответственность", "top_k": 3})
    assert r.status_code == 200, f"retrieve: {r.status_code} {r.text}"
    data = r.json()
    assert len(data["hits"]) > 0
    assert "score" in data["hits"][0]


def test_compare():
    _post_safe("/spaces", {"name": "test2", "dim": 32})
    _post_safe("/spaces/test2/ingest", {
        "text": "Свобода не требует ответственности. Свобода это одиночество.",
        "source_id": "note2",
        "format": "plain",
    })
    r = httpx.get(f"{BASE}/compare?a=test&b=test2&top_k=10")
    assert r.status_code == 200, f"compare: {r.status_code} {r.text}"
    data = r.json()
    assert "shared_concepts" in data
    assert "divergent" in data


def test_list_spaces():
    r = httpx.get(f"{BASE}/spaces")
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_save_space():
    r = httpx.post(f"{BASE}/spaces/test/save")
    assert r.status_code == 200
    assert r.json()["saved"]


def test_cleanup():
    httpx.delete(f"{BASE}/spaces/test")
    httpx.delete(f"{BASE}/spaces/test2")
    r = httpx.get(f"{BASE}/spaces/test")
    assert r.status_code == 404
