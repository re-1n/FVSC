from __future__ import annotations

import hashlib

import pytest

from fvsc.ingest import SourceDocument
from fvsc.semantic import LinguisticFrontendResult, LinguisticToken
from fvsc.semantic.graph import (
    RepresentationLoss,
    SemanticAttribute,
    SemanticEdge,
    SemanticGraphView,
    SemanticNode,
)


def _frontend(text: str, *, language_tag: str) -> tuple[SourceDocument, LinguisticFrontendResult]:
    document = SourceDocument.create(
        source_id=f"public/synthetic/{language_tag}/meaning-1.txt",
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=100.0,
        text=text,
        adapter="synthetic-test",
    )
    words = text.rstrip(".").split()
    tokens: list[LinguisticToken] = []
    cursor = 0
    for index, word in enumerate(words, start=1):
        start = text.index(word, cursor)
        end = start + len(word)
        cursor = end
        tokens.append(
            LinguisticToken.from_text(
                text,
                token_id=f"s1t{index}",
                sentence_id="s1",
                index=index,
                start=start,
                end=end,
            )
        )
    frontend = LinguisticFrontendResult(
        source_id=document.source_id,
        source_revision=document.source_revision,
        language_tag=language_tag,
        frontend="synthetic",
        frontend_version="1",
        tokens=tuple(tokens),
    )
    return document, frontend


def _graph(frontend: LinguisticFrontendResult) -> SemanticGraphView:
    return SemanticGraphView(
        source_id=frontend.source_id,
        source_revision=frontend.source_revision,
        language_tag=frontend.language_tag,
        frontend_digest=frontend.digest,
        extractor="manual-umr-subset",
        extractor_version="1",
        nodes=(
            SemanticNode(
                "author",
                "author",
                None,
                alignment_status="implicit",
                kind="metanode",
            ),
            SemanticNode("s1f", "freedom", "s1", ("s1t1",)),
            SemanticNode("s1r", "require-01", "s1", ("s1t2",)),
            SemanticNode("s1x", "responsibility", "s1", ("s1t3",)),
        ),
        edges=(
            SemanticEdge("author", "full-affirmative", "s1r", scope="document"),
            SemanticEdge("s1r", "ARG0", "s1f"),
            SemanticEdge("s1r", "ARG1", "s1x"),
        ),
        attributes=(SemanticAttribute("s1r", "aspect", "state"),),
        losses=(
            RepresentationLoss(
                path="sentence:s1:surface-punctuation",
                reason="not-semantic",
            ),
        ),
    )


def test_semantic_graph_round_trip_is_deterministic_and_frontend_bound() -> None:
    document, frontend = _frontend(
        "Freedom requires responsibility.",
        language_tag="en",
    )
    graph = _graph(frontend)

    frontend.verify(document)
    graph.verify(frontend)
    restored = SemanticGraphView.from_dict(graph.to_dict())

    assert restored == graph
    assert restored.digest == graph.digest
    assert graph.to_dict()["source_revision"] == document.source_revision
    assert "Freedom requires responsibility" not in str(graph.to_dict())


def test_same_contract_accepts_a_different_language_frontend() -> None:
    _, frontend = _frontend("Свобода требует ответственности.", language_tag="ru")
    graph = _graph(frontend)

    graph.verify(frontend)

    assert graph.language_tag == "ru"
    assert {(edge.relation, edge.scope) for edge in graph.edges} == {
        ("ARG0", "sentence"),
        ("ARG1", "sentence"),
        ("full-affirmative", "document"),
    }


def test_graph_rejects_cross_sentence_edge_and_stale_frontend() -> None:
    _, frontend = _frontend("One relation object.", language_tag="en")

    with pytest.raises(ValueError, match="inside one sentence"):
        SemanticGraphView(
            source_id=frontend.source_id,
            source_revision=frontend.source_revision,
            language_tag=frontend.language_tag,
            frontend_digest=frontend.digest,
            extractor="test",
            extractor_version="1",
            nodes=(
                SemanticNode("a", "one", "s1", ("s1t1",)),
                SemanticNode("b", "two", "s2", alignment_status="unknown"),
            ),
            edges=(SemanticEdge("a", "related", "b"),),
        )

    _, other_frontend = _frontend("Other relation object.", language_tag="en")
    with pytest.raises(ValueError, match="source_revision"):
        _graph(frontend).verify(other_frontend)
