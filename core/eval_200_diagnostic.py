"""
200-sentence diagnostic for text_parser_agnostic.

Descriptive run over eval_sentences_200.txt — the file is unannotated, so this
is NOT precision/recall against gold. It tabulates per-sentence parser output
by linguistic category (heuristic) and measures the sibling-FP baseline on the
coordination subset.

Key output: sibling_fp_rate on the coordination category — the fraction of
pairs in coordination sentences that link two tokens directly across a
coordinator (e.g. силы↔терпения in "Мужество требует силы и терпения").
Expected to be > 0 before the #6 sibling-FP fix lands and near 0 after.

Run:
    python -X utf8 -m core.eval_200_diagnostic

Output:
    stdout — per-category summary table
    eval_200_results.json (next to this file) — per-sentence detail
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

try:
    from .text_parser_agnostic import (
        DEFAULT_STOPWORDS_RU_EN,
        ParseConfig,
        text_to_semantic_input,
        tokenize,
    )
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from text_parser_agnostic import (  # type: ignore
        DEFAULT_STOPWORDS_RU_EN,
        ParseConfig,
        text_to_semantic_input,
        tokenize,
    )


# ---------------------------------------------------------------------------
# File-format reader
# ---------------------------------------------------------------------------

SENTENCE_LINE_RE = re.compile(r"^\s*(\d+)\.\s*\[([^\]]+)\]\s*(.*?)\s*$")


def load_sentences(path: str) -> List[Dict]:
    """Read eval_sentences_200.txt — skip banner and footer.

    Returns list of {n: int, source: str, text: str, category_hints: set}.
    A sentence may carry multiple hints (e.g. coordination + negation).

    The file has both a header banner (lines 1–2, terminated by ===…) AND a
    footer banner that starts the same way (line 215, "===…" before the
    `STATS:` block). We only break out of the loop on the *footer*, recognised
    by the presence of `STATS:` or `By source:` / `By category:` lines —
    not on the bare ===-separator, which appears in both header and footer.
    """
    out: List[Dict] = []
    seen_first_sentence = False
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            stripped = line.strip()
            # Footer markers — only fire AFTER we've seen at least one
            # sentence, so the header ===… separator doesn't break us out.
            if seen_first_sentence and (
                stripped.startswith("STATS:")
                or stripped.startswith("By source:")
                or stripped.startswith("By category:")
                or (stripped.startswith("===") and len(stripped) >= 10)
            ):
                break

            m = SENTENCE_LINE_RE.match(line)
            if not m:
                continue
            n = int(m.group(1))
            source = m.group(2).strip()
            text = m.group(3).strip()
            if not text:
                continue
            seen_first_sentence = True
            out.append({
                "n": n,
                "source": source,
                "text": text,
                "category_hints": _detect_categories(text),
            })
    return out


# ---------------------------------------------------------------------------
# Category heuristics (surface triggers)
#
# Reliable categories first (coordination/negation are the easiest to detect
# from surface tokens). Passive/reported/generic/simple_svo are intentionally
# omitted — surface heuristics for them are too noisy to be useful.
# ---------------------------------------------------------------------------

# Match parser default coordinator set. Diagnostic is independent of the
# parser's coordination_aware flag, so import-side coupling is intentional —
# we want both to see the same surface coordinators.
COORDINATOR_TRIGGERS = frozenset({"и", "или", "да", "and", "or"})

CATEGORY_HEURISTICS: Dict[str, frozenset] = {
    "coordination": COORDINATOR_TRIGGERS,
    "negation": frozenset({"не", "нет", "никогда", "ни", "not", "no", "never"}),
    "modal": frozenset({"должен", "может", "хочет", "нужно", "надо",
                        "must", "can", "should", "would", "could"}),
    "copular": frozenset({"это", "является", "is", "are"}),
    "conditional": frozenset({"если", "когда", "if", "when"}),
}


def _detect_categories(text: str) -> Set[str]:
    raw_tokens = tokenize(text, lowercase=True)
    token_set = set(raw_tokens)
    hits: Set[str] = set()
    for category, triggers in CATEGORY_HEURISTICS.items():
        if token_set & triggers:
            hits.add(category)
    # Em-dash copula: "X — Y" (Russian written-language pattern)
    if " — " in text and "copular" not in hits:
        hits.add("copular")
    if not hits:
        hits.add("other")
    return hits


# ---------------------------------------------------------------------------
# Sibling-FP detection
# ---------------------------------------------------------------------------

def _detect_sibling_pairs(text: str) -> List[Tuple[str, str]]:
    """Find {left, right} content tokens flanking each coordinator.

    Mirrors the logic the sibling-FP fix will use, but runs on the raw text
    independently — diagnostic must show the same baseline number whether the
    parser fix is active or not (at this stage it isn't).
    """
    raw = tokenize(text, lowercase=True)
    siblings: List[Tuple[str, str]] = []

    for k, tok in enumerate(raw):
        if tok not in COORDINATOR_TRIGGERS:
            continue
        # Walk left for a content token (skip other coordinators / very short
        # function words)
        left = None
        for j in range(k - 1, -1, -1):
            t = raw[j]
            if t in COORDINATOR_TRIGGERS:
                continue
            if len(t) < 2:
                continue
            if t in DEFAULT_STOPWORDS_RU_EN:
                continue
            left = t
            break
        # Walk right for a content token
        right = None
        for j in range(k + 1, len(raw)):
            t = raw[j]
            if t in COORDINATOR_TRIGGERS:
                continue
            if len(t) < 2:
                continue
            if t in DEFAULT_STOPWORDS_RU_EN:
                continue
            right = t
            break
        if left and right:
            siblings.append((left, right))
    return siblings


def _prefix_match(a: str, b: str, prefix_len: int = 4) -> bool:
    """Same lenient prefix match used by evaluation._find_key."""
    if a == b:
        return True
    return a.startswith(b[:prefix_len]) or b.startswith(a[:prefix_len])


def _count_sibling_fp_pairs(si: Dict, siblings: List[Tuple[str, str]]) -> int:
    """For each parsed (a, b) in any contains-dict, check if {a, b} matches
    some {left, right} sibling pair via prefix matching.
    """
    if not siblings:
        return 0
    count = 0
    for ka, spec in si.items():
        for kb in spec.get("contains", {}):
            for left, right in siblings:
                if (_prefix_match(ka, left) and _prefix_match(kb, right)) or \
                   (_prefix_match(ka, right) and _prefix_match(kb, left)):
                    count += 1
                    break  # don't double-count this (ka, kb) against other sibs
    return count


# ---------------------------------------------------------------------------
# Diagnostic driver
# ---------------------------------------------------------------------------

def diagnose(path: str, config: Optional[ParseConfig] = None,
             dim: int = 32) -> Dict:
    """Run parser on every sentence; collect per-sentence + per-category stats.

    Returns a dict with two top-level keys:
      - per_sentence: list of detail dicts (one per sentence)
      - by_category: dict[category] -> aggregate stats
    """
    if config is None:
        config = ParseConfig(min_freq=1, window=5)

    sentences = load_sentences(path)
    per_sentence: List[Dict] = []
    by_category: Dict[str, Dict] = defaultdict(lambda: {
        "n_sent": 0,
        "concepts": [],
        "pairs": [],
        "ms": [],
        "zero_pair": 0,
        "high_pair": 0,
        "sibling_fp_pairs": 0,
        "total_pairs_for_sibling_check": 0,
    })

    for entry in sentences:
        text = entry["text"]
        t0 = time.perf_counter()
        si = text_to_semantic_input(text, config=config)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        n_concepts = len(si)
        all_pairs = [(ka, kb, float(w))
                     for ka, spec in si.items()
                     for kb, w in spec.get("contains", {}).items()]
        n_pairs = len(all_pairs)

        siblings = _detect_sibling_pairs(text) if "coordination" in entry["category_hints"] else []
        sibling_fp = _count_sibling_fp_pairs(si, siblings)
        top_pairs = sorted(all_pairs, key=lambda x: -x[2])[:5]

        detail = {
            "n": entry["n"],
            "source": entry["source"],
            "text": text,
            "category_hints": sorted(entry["category_hints"]),
            "n_concepts": n_concepts,
            "n_pairs": n_pairs,
            "top_pairs": top_pairs,
            "elapsed_ms": round(elapsed_ms, 3),
            "sibling_pairs_detected": siblings,
            "sibling_fp_pairs": sibling_fp,
        }
        per_sentence.append(detail)

        for cat in entry["category_hints"]:
            bucket = by_category[cat]
            bucket["n_sent"] += 1
            bucket["concepts"].append(n_concepts)
            bucket["pairs"].append(n_pairs)
            bucket["ms"].append(elapsed_ms)
            if n_pairs == 0:
                bucket["zero_pair"] += 1
            if n_pairs > 20:
                bucket["high_pair"] += 1
            if cat == "coordination":
                bucket["sibling_fp_pairs"] += sibling_fp
                bucket["total_pairs_for_sibling_check"] += n_pairs

    # Finalize per-category aggregates
    aggregates: Dict[str, Dict] = {}
    for cat, bucket in by_category.items():
        n = bucket["n_sent"]
        agg = {
            "n_sent": n,
            "avg_concepts": statistics.mean(bucket["concepts"]) if bucket["concepts"] else 0.0,
            "avg_pairs": statistics.mean(bucket["pairs"]) if bucket["pairs"] else 0.0,
            "pct_zero_pair": bucket["zero_pair"] / max(1, n),
            "pct_high_pair": bucket["high_pair"] / max(1, n),
            "avg_ms": statistics.mean(bucket["ms"]) if bucket["ms"] else 0.0,
        }
        if cat == "coordination":
            denom = bucket["total_pairs_for_sibling_check"]
            agg["sibling_fp_pairs"] = bucket["sibling_fp_pairs"]
            agg["total_pairs"] = denom
            agg["sibling_fp_rate"] = (
                bucket["sibling_fp_pairs"] / denom if denom > 0 else 0.0
            )
        aggregates[cat] = agg

    return {
        "per_sentence": per_sentence,
        "by_category": aggregates,
        "total_sentences": len(sentences),
        "config": {
            "min_freq": config.min_freq,
            "window": config.window,
            "coordination_aware": getattr(config, "coordination_aware", False),
        },
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _print_summary(result: Dict):
    print(f"\n{'=' * 78}")
    print(f"200-sentence diagnostic — {result['total_sentences']} sentences parsed")
    print(f"config: min_freq={result['config']['min_freq']}, "
          f"window={result['config']['window']}, "
          f"coordination_aware={result['config']['coordination_aware']}")
    print(f"{'=' * 78}\n")

    cols = ["category", "n_sent", "avg_concepts", "avg_pairs",
            "pct_zero", "pct_high", "avg_ms"]
    print(f"{cols[0]:<14}{cols[1]:>7}{cols[2]:>14}{cols[3]:>11}"
          f"{cols[4]:>10}{cols[5]:>10}{cols[6]:>10}")
    print("-" * 78)
    for cat in sorted(result["by_category"]):
        agg = result["by_category"][cat]
        print(f"{cat:<14}{agg['n_sent']:>7}{agg['avg_concepts']:>14.2f}"
              f"{agg['avg_pairs']:>11.2f}{agg['pct_zero_pair']:>10.1%}"
              f"{agg['pct_high_pair']:>10.1%}{agg['avg_ms']:>10.2f}")

    coord = result["by_category"].get("coordination")
    if coord:
        print(f"\nCoordination sibling-FP:  "
              f"{coord['sibling_fp_pairs']} sibling pairs out of "
              f"{coord['total_pairs']} total pairs in coordination sentences  "
              f"=  sibling_fp_rate = {coord['sibling_fp_rate']:.1%}")

    # Per-category samples: 3 highest pair-count, 3 zero-pair
    print("\n--- failure-mode samples ---")
    for cat in ("coordination", "negation", "modal", "copular", "conditional"):
        if cat not in result["by_category"]:
            continue
        sents_in_cat = [s for s in result["per_sentence"]
                        if cat in s["category_hints"]]
        if not sents_in_cat:
            continue
        zeros = [s for s in sents_in_cat if s["n_pairs"] == 0][:3]
        highs = sorted(sents_in_cat, key=lambda s: -s["n_pairs"])[:3]
        print(f"\n[{cat}] top-pair-count:")
        for s in highs:
            print(f"  #{s['n']:>3} ({s['n_pairs']} pairs): {s['text'][:80]}")
        if zeros:
            print(f"[{cat}] zero-pair (parser failures):")
            for s in zeros:
                print(f"  #{s['n']:>3}: {s['text'][:80]}")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(os.path.dirname(here), "eval_sentences_200.txt")
    if not os.path.exists(path):
        print(f"[error] eval_sentences_200.txt not found at {path}", file=sys.stderr)
        sys.exit(1)

    result = diagnose(path)
    _print_summary(result)

    out_path = os.path.join(here, "eval_200_results.json")
    # Make detail JSON-serialisable (sets, tuples)
    serialisable = {
        "total_sentences": result["total_sentences"],
        "config": result["config"],
        "by_category": result["by_category"],
        "per_sentence": [
            {**s,
             "top_pairs": [list(p) for p in s["top_pairs"]],
             "sibling_pairs_detected": [list(p) for p in s["sibling_pairs_detected"]]}
            for s in result["per_sentence"]
        ],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(serialisable, f, ensure_ascii=False, indent=2)
    print(f"\n[saved] per-sentence detail → {out_path}")


if __name__ == "__main__":
    main()
