from __future__ import annotations

from core.density_core import SemanticSpace
from core.text_parser_agnostic import ParseConfig
from service.ingest import ingest_text
from service.store import SpaceBundle


CONFIG = ParseConfig(min_freq=1, min_token_len=3, max_concepts=100)


def test_reingest_replaces_old_chunks() -> None:
    bundle = SpaceBundle(name="test", space=SemanticSpace(dim=16))
    first = (
        "Свобода требует ответственности и внимательного отношения к последствиям.\n\n"
        "Мужество помогает принимать сложные решения и сохранять честность."
    )
    second = "Терпение помогает сохранять ясность во время сложного разговора."

    _, first_added, _ = ingest_text(bundle, first, "note.md", config=CONFIG)
    assert first_added == 2
    assert set(bundle.chunks) == {"note.md:0", "note.md:1"}

    _, second_added, _ = ingest_text(bundle, second, "note.md", config=CONFIG)

    assert second_added == 1
    assert set(bundle.chunks) == {"note.md:0"}
    assert bundle.chunks["note.md:0"].text == second
    assert all(
        component.archived
        for concept in bundle.space.concepts.values()
        for component in concept.components
        if component.judgment.source_text == "note.md:1"
    )


def test_reingest_with_empty_text_removes_old_source() -> None:
    bundle = SpaceBundle(name="test", space=SemanticSpace(dim=16))
    text = "Свобода требует ответственности и внимательного отношения к последствиям."
    ingest_text(bundle, text, "note.md", config=CONFIG)

    _, added, _ = ingest_text(bundle, "", "note.md", config=CONFIG)

    assert added == 0
    assert bundle.chunks == {}
    assert all(
        component.archived
        for concept in bundle.space.concepts.values()
        for component in concept.components
        if component.judgment.source_text.startswith("note.md:")
    )
