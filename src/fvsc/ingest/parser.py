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


# Coordinator tokens for the sibling-FP pre-pass. Pairs of content tokens that
# flank a coordinator like "X и Y" / "X or Y" are marked sibling and their
# *direct* sliding-window co-occurrence is dropped — they remain linked to
# the shared verb-parent through normal co-occurrence, which captures genuine
# textual structure. See ParseConfig.coordination_aware below.
#
# Limits (honest):
#   - Single-token-coordinator languages only. Prefixal (Arabic wa-), enclitic
#     (Latin -que), or zero-marked juxtaposition (Chinese) coordination won't
#     fire this rule. Languages without a coordinator in this set fall back to
#     unmodified sliding-window behaviour.
#   - The "nearest content token left / right of the coordinator" heuristic
#     captures only the *last* pair in a long list "A, B, C, и D" (here: C↔D).
#     Full list-coordination handling is a separate (future) task.
DEFAULT_COORDINATORS = frozenset({
    # Russian
    "и", "или", "да",   # "да" in the conjunctive sense ("хлеб да соль")
    # English
    "and", "or",
})


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
    # --- Optional thesaurus prior (bonus-only — see text_to_semantic_input) ---
    thesaurus_prior: object = None        # ThesaurusPrior instance (or None to disable)
    prior_known_bonus: float = 1.2        # weight multiplier for pairs confirmed by thesaurus
    # --- Coordination-aware sibling-FP suppression ---
    # When True, content tokens flanking a coordinator (default: и/или/да/and/or)
    # don't accumulate direct sibling-sibling co-occurrence. They remain
    # linked to other tokens via the normal window pass — only the spurious
    # direct sibling link is suppressed. Stenographic principle: we don't
    # invent a hidden verb-parent edge, we just don't manufacture a containment
    # edge the text doesn't license.
    coordination_aware: bool = True
    coordinators: Optional[Iterable[str]] = None  # None → DEFAULT_COORDINATORS


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

    pair_cooccur[(a, b)] counts directed co-occurrences: a appears before b
    within `config.window` tokens in the same sentence.
    Asymmetric by construction: pair_cooccur[(a,b)] != pair_cooccur[(b,a)].

    When `config.coordination_aware` is True, a per-sentence pre-pass over the
    raw token stream identifies pairs of content tokens flanking each
    coordinator (e.g. "силы и терпения" → sibling pair {силы, терпения}).
    Direct sibling-sibling co-occurrence is then suppressed in both directions
    inside the sliding window — they remain linked to other tokens (notably
    the verb-parent on the left) through unmodified co-occurrence.
    """
    stop = set(config.stopwords) if config.stopwords else set()
    coordinators = set(config.coordinators) if config.coordinators is not None \
        else set(DEFAULT_COORDINATORS)
    coord_active = bool(config.coordination_aware) and bool(coordinators)

    token_freq: Counter = Counter()
    pair_cooccur: Dict[Tuple[str, str], int] = defaultdict(int)
    sentence_tokens: List[List[str]] = []

    for sent in split_sentences(text):
        raw = tokenize(sent, lowercase=config.lowercase)
        if not raw:
            continue

        # --- Step B: coordinator-aware sibling detection on the raw stream.
        # We need the raw tokens (coordinators still present) to locate
        # coordinator positions; the content filter below restricts what
        # counts as a "sibling" (no stopwords, length >= min_token_len).
        sibling_pairs: set = set()
        if coord_active:
            for k, tok in enumerate(raw):
                if tok not in coordinators:
                    continue
                left = _nearest_content(raw, k, -1, config, stop, coordinators)
                right = _nearest_content(raw, k, +1, config, stop, coordinators)
                if left and right and left != right:
                    sibling_pairs.add(frozenset({left, right}))

        # --- Step C: existing stopword + length filter for the window pass.
        toks = [
            t for t in raw
            if len(t) >= config.min_token_len and t not in stop
        ]
        if not toks:
            continue
        sentence_tokens.append(toks)
        token_freq.update(toks)

        # --- Step D: directed sliding window with sibling-pair skip-guard.
        n = len(toks)
        for i, ti in enumerate(toks):
            j_max = min(n, i + 1 + config.window)
            for j in range(i + 1, j_max):
                tj = toks[j]
                if ti == tj:
                    continue
                if coord_active and frozenset({ti, tj}) in sibling_pairs:
                    continue
                pair_cooccur[(ti, tj)] += 1  # directed: ti → tj

    return token_freq, dict(pair_cooccur), sentence_tokens


def _nearest_content(
    raw: List[str],
    start: int,
    direction: int,
    config: ParseConfig,
    stop: set,
    coordinators: set,
) -> Optional[str]:
    """Walk `direction` (+1 right, -1 left) from `start` and return the first
    content token: not a coordinator, not a stopword, length >= min_token_len.
    Returns None if none found.
    """
    n = len(raw)
    j = start + direction
    while 0 <= j < n:
        t = raw[j]
        if t not in coordinators and t not in stop and len(t) >= config.min_token_len:
            return t
        j += direction
    return None


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
    """Directed: P(B follows A | A) = cooccur(A→B) / freq(A).
    Asymmetric by construction: concept precedes other in text.
    """
    f_a = token_freq.get(concept, 0)
    if f_a == 0:
        return {}
    out: Dict[str, float] = {}
    for other in concepts:
        if other == concept:
            continue
        c = pair_cooccur.get((concept, other), 0)
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

        # Apply thesaurus prior if configured.
        # Strategy: BONUS-ONLY. Confirm what co-occurrence already found by
        # boosting pairs that the thesaurus also knows. Don't penalize unknown
        # pairs — most abstract/philosophical pairs are missing from
        # ConceptNet/WordNet by design (knowledge bases cover concrete nouns
        # much better than abstract relations).
        prior = cfg.thesaurus_prior
        if prior is not None:
            adjusted: Dict[str, float] = {}
            for other, w in raw_contains.items():
                if prior.score(c, other) > 0:
                    adjusted[other] = w * cfg.prior_known_bonus
                else:
                    adjusted[other] = w
            raw_contains = adjusted

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
