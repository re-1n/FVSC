from __future__ import annotations

import hashlib

import pytest

from fvsc.ingest import SourceDocument
from fvsc.semantic.graph import import_umr_subset


_SEPARATOR = "#" * 80


def _document(text: str) -> SourceDocument:
    return SourceDocument.create(
        source_id="public/synthetic/umr-1.txt",
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=100.0,
        text=text,
        adapter="synthetic-umr-test",
    )


def _umr(*, alignment: str | None = None) -> str:
    return f"""{_SEPARATOR}
# :: snt1
Index: 1 2 3 4
Words: Freedom requires responsibility .

# sentence level graph:
(s1r / require-01
    :ARG0 (s1f / freedom)
    :ARG1 (s1x / responsibility)
    :aspect state)

# alignment:
{alignment or '''s1f: 1-1
s1r: 2-2
s1x: 3-3'''}

# document level annotation:
(s1s0 / sentence
    :modal ((root :modal author)
            (author :full-affirmative s1r)))
"""


def test_imports_sentence_alignment_attributes_and_document_relations() -> None:
    document = _document("Freedom requires responsibility.")

    result = import_umr_subset(_umr(), document=document, language_tag="en")

    result.verify(document)
    assert [item.node_id for item in result.graph.nodes] == [
        "author",
        "root",
        "s1f",
        "s1r",
        "s1x",
    ]
    assert {(item.source_id, item.relation, item.target_id, item.scope) for item in result.graph.edges} == {
        ("author", "full-affirmative", "s1r", "document"),
        ("root", "modal", "author", "document"),
        ("s1r", "ARG0", "s1f", "sentence"),
        ("s1r", "ARG1", "s1x", "sentence"),
    }
    assert [(item.node_id, item.name, item.value) for item in result.graph.attributes] == [
        ("s1r", "aspect", "state")
    ]
    assert result.graph.losses == ()
    assert "Freedom requires responsibility" not in str(result.graph.to_dict())


def test_missing_alignment_is_explicit_loss_not_silent_guess() -> None:
    document = _document("Freedom requires responsibility.")

    result = import_umr_subset(
        _umr(alignment="s1r: 2-2\ns1x: 3-3"),
        document=document,
        language_tag="en",
    )

    freedom = next(item for item in result.graph.nodes if item.node_id == "s1f")
    assert freedom.alignment_status == "unknown"
    assert freedom.aligned_token_ids == ()
    assert any(
        item.path == "sentence:s1:node:s1f:alignment"
        and item.reason == "missing-or-invalid-alignment"
        for item in result.graph.losses
    )


def test_import_preserves_reentrancy_as_two_edges_to_one_node() -> None:
    document = _document("Boy wants go.")
    value = f"""{_SEPARATOR}
# :: snt1
Words: Boy wants go .

# sentence level graph:
(s1w / want-01
    :ARG0 (s1b / boy)
    :ARG1 (s1g / go-01 :ARG0 s1b))

# alignment:
s1b: 1-1
s1w: 2-2
s1g: 3-3

# document level annotation:
"""

    result = import_umr_subset(value, document=document, language_tag="en")

    assert {(item.source_id, item.relation, item.target_id) for item in result.graph.edges} == {
        ("s1g", "ARG0", "s1b"),
        ("s1w", "ARG0", "s1b"),
        ("s1w", "ARG1", "s1g"),
    }


def test_import_fails_closed_when_umr_tokens_do_not_match_source_revision() -> None:
    document = _document("Freedom permits responsibility.")

    with pytest.raises(ValueError, match="cannot be aligned"):
        import_umr_subset(_umr(), document=document, language_tag="en")
