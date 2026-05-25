"""
Language-Agnostic Text Parser for FVSC

Converts raw text (any language) into a semantic_input dict compatible with
`semantic_input.parse_semantic_input()`. No spaCy, no language-specific parser.

Pipeline:
    raw_text
      → paragraph segmentation (blank lines)
      → sentence segmentation (regex on . ! ? + Chinese/Japanese terminators)
      → token extraction (\\b\\w+\\b, lowercase, Unicode-aware)
      → optional stopword filter (callable, language-agnostic by default → off)
      → co-occurrence within sliding window
      → asymmetric containment weights P(T' | T in window)
      → semantic_input dict

The output preserves the asymmetry of containment that density matrices
encode naturally:
    weight(A contains B) = co-occur(A,B) / freq(A)
    weight(B contains A) = co-occur(A,B) / freq(B)
These are generally different — exactly the non-commutative structure
the FVSC formalism expects.

NOTE on embedders: external embedding models (BGE-m3, SBERT, etc.) must NOT
be used to construct basis vectors |v⟩ for ρ = Σwᵢ|vᵢ⟩⟨vᵢ|.
A single BGE vector collapses ρ to a rank-1 pure state — losing asymmetric
containment, mixture, and partial trace that motivate the FVSC framework.
The correct role of embedders is concept-resolution (multilingual alias
clustering at the ID layer), not weight computation.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np


# Multilingual sentence terminators: Latin, Chinese, Japanese, Arabic, Devanagari, Armenian
_SENT_SPLIT_RE = re.compile(r"[.!?。！？؟।՞]+\s*")
_PARA_SPLIT_RE = re.compile(r"\n\s*\n")
# Unicode word boundary: handles Cyrillic, CJK, Latin, etc.
_TOKEN_RE = re.compile(r"\b\w+\b", flags=re.UNICODE)


@dataclass
class ParseConfig:
    """Configuration for the agnostic text parser."""
    window: int = 5                       # co-occurrence half-window in tokens
    min_freq: int = 2                     # drop concepts seen fewer than this
    max_concepts: Optional[int] = 200     # keep top-N by frequency, None = all
    min_token_len: int = 2                # drop very short tokens (digits, "a", etc.)
    lowercase: bool = True
    stopwords: Optional[Iterable[str]] = None  # iterable of words to ignore
    keep_top_contains: int = 8            # max children per container
    weight_threshold: float = 0.05        # drop child weights below this


# ─────────────────────────── Segmentation ───────────────────────────

def split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in _PARA_SPLIT_RE.split(text) if p.strip()]


def split_sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENT_SPLIT_RE.split(text) if s.strip()]


def tokenize(text: str, lowercase: bool = True) -> List[str]:
    if lowercase:
        text = text.lower()
    return _TOKEN_RE.findall(text)


# ─────────────────────────── Core extraction ───────────────────────────

def extract_concepts_and_cooccurrence(
    text: str,
    config: ParseConfig,
) -> Tuple[Counter, Dict[Tuple[str, str], int], List[List[str]]]:
    """Return (token_freq, pair_cooccur, sentence_tokens).

    pair_cooccur[(a, b)] counts co-occurrences within `config.window` tokens
    in the same sentence. Symmetric: stored only with a < b.
    """
    stop = set(config.stopwords) if config.stopwords else set()
    token_freq: Counter = Counter()
    pair_cooccur: Dict[Tuple[str, str], int] = defaultdict(int)
    sentence_tokens: List[List[str]] = []

    for sent in split_sentences(text):
        toks = [
            t for t in tokenize(sent, lowercase=config.lowercase)
            if len(t) >= config.min_token_len and t not in stop
        ]
        if not toks:
            continue
        sentence_tokens.append(toks)
        token_freq.update(toks)

        # Sliding window co-occurrence within this sentence
        n = len(toks)
        for i, ti in enumerate(toks):
            j_max = min(n, i + 1 + config.window)
            for j in range(i + 1, j_max):
                tj = toks[j]
                if ti == tj:
                    continue
                a, b = (ti, tj) if ti < tj else (tj, ti)
                pair_cooccur[(a, b)] += 1

    return token_freq, dict(pair_cooccur), sentence_tokens


def _pick_concepts(token_freq: Counter, config: ParseConfig) -> List[str]:
    items = [(t, f) for t, f in token_freq.items() if f >= config.min_freq]
    items.sort(key=lambda x: (-x[1], x[0]))
    if config.max_concepts is not None:
        items = items[: config.max_concepts]
    return [t for t, _ in items]


# ─────────────────────────── Weighting strategies ───────────────────────────

def _cooccur_contains_weights(
    concept: str,
    concepts: Sequence[str],
    token_freq: Counter,
    pair_cooccur: Dict[Tuple[str, str], int],
) -> Dict[str, float]:
    """P(B in window | A) = cooccur(A,B) / freq(A) — asymmetric by construction."""
    f_a = token_freq.get(concept, 0)
    if f_a == 0:
        return {}
    out: Dict[str, float] = {}
    concept_set = set(concepts)
    for other in concept_set:
        if other == concept:
            continue
        a, b = (concept, other) if concept < other else (other, concept)
        c = pair_cooccur.get((a, b), 0)
        if c == 0:
            continue
        out[other] = c / f_a
    return out



# ─────────────────────────── Public API ───────────────────────────

def text_to_semantic_input(
    text: str,
    config: Optional[ParseConfig] = None,
) -> Dict[str, Dict]:
    """Convert raw text into a semantic_input dict.

    Args:
        text: raw text in any language.
        config: ParseConfig (defaults are sensible for short docs).

    Returns:
        Dict suitable for `semantic_input.parse_semantic_input()`:
            {
                concept: {
                    "weight": <relative frequency, 0..1>,
                    "contains": { other_concept: weight, ... }
                },
                ...
            }
    """
    cfg = config or ParseConfig()

    token_freq, pair_cooccur, _sent_tokens = extract_concepts_and_cooccurrence(text, cfg)
    concepts = _pick_concepts(token_freq, cfg)
    if not concepts:
        return {}

    max_freq = max(token_freq[c] for c in concepts)

    semantic_input: Dict[str, Dict] = {}
    for c in concepts:
        self_weight = token_freq[c] / max_freq

        raw_contains = _cooccur_contains_weights(
            c, concepts, token_freq, pair_cooccur
        )

        filtered = [(k, w) for k, w in raw_contains.items() if w >= cfg.weight_threshold]
        filtered.sort(key=lambda x: -x[1])
        filtered = filtered[: cfg.keep_top_contains]

        entry: Dict = {"weight": float(self_weight)}
        if filtered:
            entry["contains"] = {k: float(w) for k, w in filtered}
        semantic_input[c] = entry

    return semantic_input


def parse_text(
    text: str,
    dim: int = 64,
    config: Optional[ParseConfig] = None,
) -> Tuple[Dict[str, Dict], Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    """End-to-end: raw text → (semantic_input, concept_vectors, concept_rhos).

    Convenience wrapper that calls `text_to_semantic_input` and then
    `semantic_input.parse_semantic_input` to produce density matrices.
    """
    try:
        from .semantic_input import parse_semantic_input
    except ImportError:  # script-mode fallback
        from semantic_input import parse_semantic_input

    si = text_to_semantic_input(text, config=config)
    if not si:
        return {}, {}, {}
    vectors, rhos = parse_semantic_input(si, dim=dim)
    return si, vectors, rhos



# ─────────────────────────── Utilities ───────────────────────────

# Minimal multilingual stopword list — opt-in. Empty by default to stay
# truly language-agnostic. Users can pass their own via ParseConfig.stopwords.
DEFAULT_STOPWORDS_RU_EN = frozenset({
    # Russian
    "и", "в", "не", "на", "с", "что", "это", "как", "по", "из", "для",
    "у", "к", "о", "а", "но", "или", "же", "бы", "ли", "то", "так", "вот",
    "если", "когда", "она", "он", "они", "оно", "мы", "вы", "ты", "я",
    "его", "её", "их", "был", "была", "было", "были", "есть", "быть",
    "только", "ещё", "уже", "там", "тут", "где", "куда", "откуда",
    # English
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "if", "then", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "as", "that", "this", "these", "those", "it",
    "its", "i", "you", "he", "she", "we", "they", "them", "his", "her",
    "have", "has", "had", "do", "does", "did", "not", "no", "so", "such",
})
