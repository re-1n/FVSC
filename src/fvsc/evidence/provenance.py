"""
provenance.py — Per-file attribution of concepts and contains-edges, plus
                silent_pool (rarely-uttered tokens that don't make it into the
                strong concept map but are kept for reflection).

Background:
    The agnostic parser builds a global semantic_input by running over a
    concatenated corpus, which makes every concept's `source_text` collapse
    to a single literal (e.g. "[vault]"). That kills reflection — the user
    cannot ask "where did the concept «важно» come from in MY notes?".

    Separately, the parser's `min_freq` cutoff (default 5 for big vaults)
    discards tokens that the user uttered only 1-4 times — silently. But the
    user's example: «я один раз сказал что не люблю когда мне жмут руку, и
    теперь никто не понимает почему я отстраняюсь». That signal must survive,
    even if density-matrix can't be built from a single mention.

Strategy:
    1. Keep the GLOBAL pass (`text_to_semantic_input`) as the source of truth
       for the stable vocabulary and contains-edge weights.
    2. Run a SECOND pass per file using the same `extract_concepts_and_cooccurrence`
       primitive. For each file, count per-file freqs and pair co-occurrence.
    3. Two outputs from this pass:
       a. `provenance`: per-file attribution for strong concepts/edges.
          Feeds `load_from_semantic_input` so Judgments carry real file paths.
       b. `silent_pool`: tokens with freq < min_freq, with global freq + per-file
          attribution. NOT loaded into density-matrix; kept as a side table on
          SemanticSpace for reflection queries.
"""
from __future__ import annotations

from typing import Dict, Mapping, Tuple
from collections import defaultdict, Counter

from ..ingest.parser import (
    ParseConfig,
    extract_concepts_and_cooccurrence,
)


# provenance[concept] = {
#   "self":     {source_path: fraction in [0,1], sums to 1.0},
#   "contains": {child_term: {source_path: fraction, sums to 1.0}}
# }
ProvenanceMap = Dict[str, Dict[str, Dict[str, float]]]

# silent_pool[token] = {
#   "freq":   int,                    # total times across vault
#   "sources": {path: count, ...}     # raw per-file counts
# }
SilentPool = Dict[str, Dict]


def build_provenance_and_silent(
    si: dict,
    files_by_path: Mapping[str, str],
    config: ParseConfig,
) -> Tuple[ProvenanceMap, SilentPool]:
    """Single per-file pass that produces both provenance (for strong concepts)
    and silent_pool (for tokens below min_freq).

    Args:
        si: global semantic_input dict from `text_to_semantic_input` —
            defines the strong vocabulary.
        files_by_path: ordered dict `{relative_path: cleaned_text}`.
        config: same ParseConfig used to build `si`. Must match.

    Returns:
        (provenance, silent_pool). Provenance covers concepts in `si`.
        Silent pool covers any token that passed stopword + min_token_len
        filter but didn't reach min_freq globally.

    Silent_pool entries with freq==1 are kept — that is the user's "said
    once" signal, and the reflection layer needs it. If hapax noise becomes a
    problem we can add a post-filter, but cutting it here would re-introduce
    the very gap we're trying to close.
    """
    strong = set(si.keys())

    # ── per-file token freq + cooccur, restricted to strong vocab where useful
    file_token_freq_strong: Dict[str, Dict[str, int]] = {}
    file_pair_cooccur: Dict[str, Dict[Tuple[str, str], int]] = {}

    # ── global counts for silent: every token that passed the per-file filter
    silent_global_freq: Counter = Counter()
    silent_sources: Dict[str, Counter] = defaultdict(Counter)

    for path, text in files_by_path.items():
        if not text:
            continue
        token_freq, pair_cooccur, _sent = extract_concepts_and_cooccurrence(text, config)

        # Strong-vocab freq for provenance
        ft_strong = {t: f for t, f in token_freq.items() if t in strong}
        if ft_strong:
            file_token_freq_strong[path] = ft_strong

        pc = {}
        for (a, b), c in pair_cooccur.items():
            if a in strong and b in strong:
                pc[(a, b)] = c
        if pc:
            file_pair_cooccur[path] = pc

        # Silent accumulation: tokens NOT in strong vocab.
        # These already passed the per-file stopword + min_token_len filter
        # (that's what extract_concepts_and_cooccurrence outputs in token_freq).
        for tok, f in token_freq.items():
            if tok in strong:
                continue
            silent_global_freq[tok] += f
            silent_sources[tok][path] += f

    # ── provenance for strong concepts
    provenance: ProvenanceMap = {}
    for concept, spec in si.items():
        self_counts: Dict[str, int] = {}
        for path, ft in file_token_freq_strong.items():
            f = ft.get(concept, 0)
            if f > 0:
                self_counts[path] = f
        total_self = sum(self_counts.values())
        self_frac = (
            {p: c / total_self for p, c in self_counts.items()}
            if total_self > 0 else {"[vault]": 1.0}
        )

        contains_frac: Dict[str, Dict[str, float]] = {}
        for child in spec.get("contains", {}).keys():
            child_counts: Dict[str, float] = {}
            for path, pc in file_pair_cooccur.items():
                cooc = pc.get((concept, child), 0)
                if cooc > 0:
                    child_counts[path] = float(cooc)
            total = sum(child_counts.values())
            if total > 0:
                contains_frac[child] = {p: c / total for p, c in child_counts.items()}
            else:
                # Cross-file co-occurrence only — fall back to self(A) distribution.
                contains_frac[child] = dict(self_frac)

        provenance[concept] = {"self": self_frac, "contains": contains_frac}

    # ── silent_pool
    silent_pool: SilentPool = {}
    for tok, freq in silent_global_freq.items():
        srcs = silent_sources[tok]
        silent_pool[tok] = {
            "freq": int(freq),
            "sources": dict(srcs),   # path → raw count
        }

    return provenance, silent_pool


# Back-compat shim: existing callers only want provenance.
def build_provenance(
    si: dict,
    files_by_path: Mapping[str, str],
    config: ParseConfig,
) -> ProvenanceMap:
    provenance, _silent = build_provenance_and_silent(si, files_by_path, config)
    return provenance
