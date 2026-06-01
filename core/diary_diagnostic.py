"""
diary_diagnostic.py — Inspect ρ-graph from personal diary corpus.

Runs the FVSC pipeline on `личный дневник тг` and reports:
  - Top concepts by frequency-weight in si
  - Per top-concept: containment (what it contains, what contains it),
    polysemy (von Neumann entropy), facet count
  - High-polysemy concepts (candidates for Antourage L6 questions)
  - Asymmetric pairs (where containment is strongly directional)
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from .exocortex_ingest import (
    load_channel,
    _clean_for_fvsc,
    _RU_STOPWORDS,
    CHANNEL_META,
)
from .text_parser_agnostic import text_to_semantic_input, ParseConfig
from .density_core import SemanticSpace


def build_space_for_diary(json_path: Path, top_n: int = 800) -> tuple[SemanticSpace, dict]:
    """Build SemanticSpace for the diary corpus."""
    _, messages = load_channel(json_path)
    cleaned = [_clean_for_fvsc(m["text"]) for m in messages]
    corpus = "\n\n".join(t for t in cleaned if len(t) >= 5)

    _synthetic = {"является", "содержит"}
    cfg = ParseConfig(
        window=4,
        min_freq=3,           # raise threshold for large corpus
        max_concepts=top_n,
        min_token_len=3,
        stopwords=_RU_STOPWORDS | _synthetic,
    )
    si = text_to_semantic_input(corpus, config=cfg)

    space = SemanticSpace(dim=64)
    space.load_from_semantic_input(si, source_text="[diary]")
    space.recursive_deepen(iterations=3, alpha=0.7)
    return space, si


def report_concept(space: SemanticSpace, term: str, top_k: int = 5):
    """Print full diagnostic for one concept."""
    print(f"\n  ── {term} ──")
    poly = space.query_polysemy(term)
    facets = space.query_facets(term)
    print(f"     polysemy(von Neumann H) = {poly:.3f}    facets = {len(facets)}")

    contains = space.query_contains(term, top_k=top_k)
    if contains:
        items = ", ".join(f"{t}={s:.2f}" for t, s in contains)
        print(f"     CONTAINS → {items}")

    in_what = space.query_contained_in(term, top_k=top_k)
    if in_what:
        items = ", ".join(f"{t}={s:.2f}" for t, s in in_what)
        print(f"     INSIDE  ← {items}")


def main():
    diary_path = Path(
        "/mnt/c/Users/daur1/Desktop/экзокортекс для fvsc map/личный дневник тг/result.json"
    )
    print(f"Loading {diary_path.parent.name} …")
    space, si = build_space_for_diary(diary_path, top_n=800)
    print(f"SemanticSpace: dim={space.dim}, concepts={len(space.concepts)}, si={len(si)}")
    print(f"Recursive deepen complete (iterations=3, alpha=0.7)")

    # Skip synthetic + meta concepts for ranking
    _skip = {"является", "содержит", "[self]"}
    ranked = sorted(
        [(c, v["weight"]) for c, v in si.items() if c not in _skip],
        key=lambda x: -x[1],
    )

    print("\n" + "═" * 70)
    print("TOP-15 КОНЦЕПТОВ ПО ЧАСТОТЕ (si weight)")
    print("═" * 70)
    for term, w in ranked[:15]:
        poly = space.query_polysemy(term)
        n_facets = len(space.query_facets(term))
        print(f"  {term:20s}  w={w:.3f}  poly={poly:.3f}  facets={n_facets}")

    print("\n" + "═" * 70)
    print("ρ-ГРАФ TOP-8 (детальная развёртка)")
    print("═" * 70)
    for term, _ in ranked[:8]:
        report_concept(space, term, top_k=5)

    # Polysemy ranking — candidates for L6 Antourage questions
    print("\n" + "═" * 70)
    print("ТОП-15 ПО ПОЛИСЕМИИ (кандидаты на вопросы Антуража)")
    print("═" * 70)
    poly_ranked = sorted(
        [(t, space.query_polysemy(t)) for t, _ in ranked[:200]],
        key=lambda x: -x[1],
    )
    for term, poly in poly_ranked[:15]:
        n_facets = len(space.query_facets(term))
        print(f"  {term:20s}  poly={poly:.3f}  facets={n_facets}")

    # Asymmetric pairs — A contains B much more than B contains A
    print("\n" + "═" * 70)
    print("СИЛЬНО АСИММЕТРИЧНЫЕ ПАРЫ (A ⊃ B, не B ⊃ A)")
    print("═" * 70)
    seen = set()
    asym = []
    top_terms = [t for t, _ in ranked[:80]]
    for a in top_terms:
        for b, score_ab in space.query_contains(a, top_k=10):
            if (b, a) in seen or b not in top_terms:
                continue
            seen.add((a, b))
            # reverse direction
            score_ba = 0.0
            for cand, s in space.query_contains(b, top_k=20):
                if cand == a:
                    score_ba = s
                    break
            diff = score_ab - score_ba
            if score_ab > 0.15 and diff > 0.10:
                asym.append((a, b, score_ab, score_ba, diff))

    asym.sort(key=lambda x: -x[4])
    for a, b, sab, sba, diff in asym[:20]:
        print(f"  {a:18s} ⊃ {b:18s}  A→B={sab:.2f}  B→A={sba:.2f}  Δ={diff:.2f}")

    # Save space for later
    import pickle
    out_path = Path("/mnt/c/Users/daur1/Desktop/FVSC/core/_diary_space.pkl")
    try:
        with open(out_path, "wb") as f:
            pickle.dump({"si": si, "concepts": list(space.concepts.keys())}, f)
        print(f"\n[saved] {out_path}")
    except Exception as e:
        print(f"\n[save failed] {e}")


if __name__ == "__main__":
    main()
