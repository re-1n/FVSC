"""Unit tests for the language-agnostic text parser (ingest layer).

Covers the self-contained text-processing primitives. The full end-to-end demo
(core/test_text_parser_agnostic.py on the security branch) is deferred — it needs
``semantic_input``, not yet ported.
"""

from __future__ import annotations

from fvsc.ingest import (
    DEFAULT_COORDINATORS,
    ParseConfig,
    extract_concepts_and_cooccurrence,
    split_paragraphs,
    split_sentences,
    text_to_semantic_input,
    tokenize,
)


def test_tokenize_is_lowercase_and_unicode_aware() -> None:
    assert tokenize("Hello, World!") == ["hello", "world"]
    # language-agnostic: Cyrillic word boundaries respected
    assert tokenize("два слова") == ["два", "слова"]
    assert tokenize("Foo BAR", lowercase=False) == ["Foo", "BAR"]


def test_split_sentences_and_paragraphs_segment_text() -> None:
    assert len(split_sentences("First. Second! Third?")) == 3
    assert len(split_paragraphs("Para one.\n\nPara two.")) == 2


def test_parseconfig_has_sensible_defaults() -> None:
    cfg = ParseConfig()
    assert cfg.window == 5
    assert cfg.min_freq == 2
    assert cfg.coordination_aware is True
    assert "и" in DEFAULT_COORDINATORS and "or" in DEFAULT_COORDINATORS


def test_directed_cooccurrence_is_asymmetric() -> None:
    # The parser's core invariant: containment is directed. "a before b" is
    # counted; "b before a" is a separate (here, zero) count.
    cfg = ParseConfig(min_freq=1, window=5)
    _freq, pairs, _sents = extract_concepts_and_cooccurrence(
        "alpha beta gamma.", cfg
    )
    assert pairs.get(("alpha", "beta"), 0) > 0
    assert pairs.get(("alpha", "gamma"), 0) > 0
    # nothing precedes alpha in this sentence
    assert pairs.get(("beta", "alpha"), 0) == 0
    assert pairs.get(("gamma", "alpha"), 0) == 0


def test_text_to_semantic_input_returns_weighted_concept_tree() -> None:
    cfg = ParseConfig(min_freq=2, window=5, weight_threshold=0.0, keep_top_contains=20)
    si = text_to_semantic_input(
        "alpha beta gamma. alpha beta gamma. alpha delta.", cfg
    )
    assert "alpha" in si and "beta" in si and "gamma" in si
    # delta appears once → below min_freq → dropped
    assert "delta" not in si
    for body in si.values():
        assert 0.0 <= body["weight"] <= 1.0
        # "contains" is present only when the concept has surviving children
        contains = body.get("contains", {})
        assert isinstance(contains, dict)
        for weight in contains.values():
            assert 0.0 <= weight <= 1.0 + 1e-9
