# -*- coding: utf-8 -*-
"""Smoke test: skeleton layer is actually wired into the service ingest path.

Principle 15: a cascade layer does not exist until the service calls it.
This test proves the call happens — in-process via TestClient, no live
server needed:

    python -m pytest service/tests/test_skeleton_wiring.py -v

Requires data/conceptnet_ru.json (skipped otherwise).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import service.app as app_module
from core.skeleton import has_skeleton
from service import skeleton_service

pytestmark = pytest.mark.skipif(
    not skeleton_service.conceptnet_path().exists(),
    reason="conceptnet_ru.json not present",
)

# Terms guaranteed to be both extractable by the parser and covered by
# the ConceptNet RU cache.
_TEXT = (
    "Свобода требует ответственности. Ответственность включает долг "
    "и мужество. Любовь дает свободу и требует терпения."
)


@pytest.fixture()
def client():
    with TestClient(app_module.app) as c:
        yield c


def _fresh_space_name() -> str:
    return f"skeltest-{uuid.uuid4().hex[:8]}"


def test_ingest_seeds_skeleton(client, monkeypatch):
    monkeypatch.delenv("FVSC_SKELETON", raising=False)
    name = _fresh_space_name()
    try:
        client.post("/spaces", json={"name": name, "dim": 32})
        r = client.post(f"/spaces/{name}/ingest", json={
            "text": _TEXT, "source_id": "note1", "format": "plain",
        })
        assert r.status_code == 200, r.text
        assert r.json()["concepts_total"] > 0

        space = app_module.store.get(name).space
        index = skeleton_service.get_index()
        covered = [t for t in space.concepts if index.covers(t)]
        assert covered, "no ingested term is covered by the thesaurus index"
        seeded = [t for t in covered if has_skeleton(space, t)]
        assert seeded, (
            f"skeleton wiring broken: covered terms {covered} "
            "have no thesaurus components after ingest"
        )
    finally:
        client.delete(f"/spaces/{name}")


def test_ingest_skeleton_disabled(client, monkeypatch):
    monkeypatch.setenv("FVSC_SKELETON", "0")
    name = _fresh_space_name()
    try:
        client.post("/spaces", json={"name": name, "dim": 32})
        r = client.post(f"/spaces/{name}/ingest", json={
            "text": _TEXT, "source_id": "note1", "format": "plain",
        })
        assert r.status_code == 200, r.text

        space = app_module.store.get(name).space
        assert not any(has_skeleton(space, t) for t in space.concepts), (
            "FVSC_SKELETON=0 must disable seeding"
        )
    finally:
        client.delete(f"/spaces/{name}")


def test_ingest_is_idempotent(client, monkeypatch):
    """Second ingest of the same text must not duplicate skeleton components."""
    monkeypatch.delenv("FVSC_SKELETON", raising=False)
    name = _fresh_space_name()
    try:
        client.post("/spaces", json={"name": name, "dim": 32})
        payload = {"text": _TEXT, "source_id": "note1", "format": "plain"}
        client.post(f"/spaces/{name}/ingest", json=payload)

        space = app_module.store.get(name).space

        def skel_component_count() -> int:
            return sum(
                1
                for c in space.concepts.values()
                for comp in c.components
                if comp.judgment.source_text.startswith("[thesaurus:")
            )

        first = skel_component_count()
        assert first > 0
        client.post(f"/spaces/{name}/ingest", json={**payload, "source_id": "note2"})
        # No new terms → no new seeding; consolidation absorbs exact dupes.
        assert skel_component_count() == first
    finally:
        client.delete(f"/spaces/{name}")
