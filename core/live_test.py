# -*- coding: utf-8 -*-
"""
FVSC Density Matrix -- Live Test on Telegram Data

Reads a Telegram JSON export, extracts judgments via spaCy,
builds density matrices, reports containment/polysemy/facets.

Usage: python -X utf8 live_test.py <path_to_result.json> [max_messages]
"""

import os
import sys
import json
import time
import numpy as np
import spacy

try:
    from .density_core import SemanticSpace, Judgment, graded_hyponymy, von_neumann_entropy, purity
    from .tree_extractor import extract_judgments_recursive
    from .thesaurus_loader import ThesaurusLoader
except ImportError:
    from density_core import SemanticSpace, Judgment, graded_hyponymy, von_neumann_entropy, purity
    from tree_extractor import extract_judgments_recursive
    from thesaurus_loader import ThesaurusLoader


# ---------------------------------------------------------------------------
# Telegram reader
# ---------------------------------------------------------------------------

def _extract_text(msg) -> str:
    """Extract text from a Telegram message (handles mixed text/entities)."""
    raw = msg.get("text", "")
    if isinstance(raw, list):
        parts = []
        for part in raw:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(part.get("text", ""))
        raw = " ".join(parts)
    if not isinstance(raw, str):
        return ""
    return raw.strip()


def _parse_date(date_str: str) -> float:
    """Parse Telegram date string to epoch seconds."""
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


def read_telegram_messages(path: str, max_msgs: int = 500,
                           merge_window_sec: float = 45.0) -> tuple[list[str], list[float]]:
    """Read text messages from Telegram JSON export.

    Merges consecutive messages from the same sender within merge_window_sec
    into single text blocks. This captures the Telegram pattern of splitting
    one thought across multiple rapid messages.

    Returns:
        (texts, timestamps) — parallel lists of message texts and their epoch timestamps.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # First pass: collect raw messages with metadata
    raw_messages = []
    for m in data.get("messages", []):
        if m.get("type") != "message":
            continue
        text = _extract_text(m)
        if not text:
            continue
        sender = m.get("from", m.get("from_id", "unknown"))
        ts = _parse_date(m.get("date", ""))
        raw_messages.append((sender, ts, text))

    if not raw_messages:
        return [], []

    # Second pass: merge by time window + same sender
    merged = []
    merged_ts = []
    current_sender = raw_messages[0][0]
    current_ts = raw_messages[0][1]
    current_parts = [raw_messages[0][2]]

    for sender, ts, text in raw_messages[1:]:
        same_sender = (sender == current_sender)
        within_window = (ts - current_ts < merge_window_sec) if ts > 0 and current_ts > 0 else False

        if same_sender and within_window:
            # Same person, quick succession -> merge
            current_parts.append(text)
            # Don't update current_ts — measure from start of burst
        else:
            # New block
            block = "\n".join(current_parts)
            if len(block) >= 10:
                merged.append(block)
                merged_ts.append(current_ts)
            current_sender = sender
            current_ts = ts
            current_parts = [text]

        if len(merged) >= max_msgs:
            break

    # Don't forget last block
    block = "\n".join(current_parts)
    if len(block) >= 10 and len(merged) < max_msgs:
        merged.append(block)
        merged_ts.append(current_ts)

    return merged, merged_ts


def read_telegram_messages_by_sender(path: str, max_msgs: int = 0,
                                     merge_window_sec: float = 45.0) -> list[tuple[str, str]]:
    """Read messages with sender info. Returns [(sender, text), ...].

    If max_msgs=0, reads ALL messages (no limit).
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    raw_messages = []
    for m in data.get("messages", []):
        if m.get("type") != "message":
            continue
        text = _extract_text(m)
        if not text:
            continue
        sender = m.get("from", m.get("from_id", "unknown"))
        ts = _parse_date(m.get("date", ""))
        raw_messages.append((sender, ts, text))

    if not raw_messages:
        return []

    merged = []
    current_sender = raw_messages[0][0]
    current_ts = raw_messages[0][1]
    current_parts = [raw_messages[0][2]]

    for sender, ts, text in raw_messages[1:]:
        same_sender = (sender == current_sender)
        within_window = (ts - current_ts < merge_window_sec) if ts > 0 and current_ts > 0 else False

        if same_sender and within_window:
            current_parts.append(text)
        else:
            block = "\n".join(current_parts)
            if len(block) >= 10:
                merged.append((current_sender, block))
            current_sender = sender
            current_ts = ts
            current_parts = [text]

        if max_msgs > 0 and len(merged) >= max_msgs:
            break

    block = "\n".join(current_parts)
    if len(block) >= 10 and (max_msgs == 0 or len(merged) < max_msgs):
        merged.append((current_sender, block))

    return merged


# ---------------------------------------------------------------------------
# Build semantic space with real spaCy vectors
# ---------------------------------------------------------------------------

def build_seed_vectors(nlp, terms: set[str], dim: int) -> dict[str, np.ndarray]:
    """Build seed vectors from spaCy word vectors.
    spaCy ru_core_news_md has 300D vectors. We use PCA or truncation to match dim.
    """
    vectors = {}
    for term in terms:
        token = nlp.vocab[term]
        if token.has_vector:
            v = token.vector
            # Truncate or pad to target dim
            if len(v) >= dim:
                v = v[:dim]
            else:
                v = np.pad(v, (0, dim - len(v)))
            norm = np.linalg.norm(v)
            if norm > 1e-10:
                vectors[term] = v / norm
    return vectors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python -X utf8 live_test.py <path_to_result.json> [max_messages]")
        sys.exit(1)

    path = sys.argv[1]
    max_msgs = int(sys.argv[2]) if len(sys.argv) > 2 else 500

    print("=" * 60)
    print("FVSC Density Matrix -- Live Telegram Test")
    print("=" * 60)

    # Load messages
    print(f"\nLoading messages from {path}...")
    texts, timestamps = read_telegram_messages(path, max_msgs)
    print(f"  Loaded {len(texts)} text messages")

    # Load spaCy
    print("\nLoading spaCy ru_core_news_md...")
    t0 = time.time()
    nlp = spacy.load("ru_core_news_md")
    print(f"  Loaded in {time.time()-t0:.1f}s")

    # Extract judgments
    print("\nExtracting judgments...")
    t0 = time.time()
    judgments = extract_judgments_recursive(nlp, texts, timestamps=timestamps)
    print(f"  Extracted {len(judgments)} judgments in {time.time()-t0:.1f}s")

    if not judgments:
        print("  No judgments found. Try a larger corpus.")
        return

    # Show sample judgments
    print("\n  Sample judgments:")
    for j in judgments[:20]:
        neg = " [NEG]" if j.quality == "NEGATIVE" else ""
        mod = f" mod={j.modality:.1f}" if j.modality != 1.0 else ""
        cond = f" [COND:{j.condition_role}]" if j.condition_id else ""
        print(f"    {j.subject} --[{j.verb}]--> {j.object}{neg}{mod}{cond}  | \"{j.source_text[:70]}\"")

    # Collect all terms
    all_terms = set()
    for j in judgments:
        all_terms.add(j.subject)
        all_terms.add(j.verb)
        all_terms.add(j.object)
    print(f"\n  Unique terms: {len(all_terms)}")

    # Build seed vectors from spaCy
    print("\nBuilding seed vectors from spaCy word vectors...")
    dim = 100  # spaCy md model has 300D, we use 100
    seed_vectors = build_seed_vectors(nlp, all_terms, dim)
    print(f"  Terms with vectors: {len(seed_vectors)}/{len(all_terms)}")

    # Create semantic space (min 3 components to appear in queries)
    space = SemanticSpace(dim=dim, seed_vectors=seed_vectors, min_components_for_query=3)

    # Load thesaurus layer (base knowledge — low modality)
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    thesaurus_path = os.path.join(data_dir, "conceptnet_ru.json")
    if os.path.exists(thesaurus_path):
        print("\nLoading thesaurus layer...")
        loader = ThesaurusLoader(conceptnet_cache=thesaurus_path, ruwordnet_dir=data_dir)
        thesaurus_judgments = loader.load_for_terms(all_terms)
        for j in thesaurus_judgments:
            space.materialize_judgment(j)
    else:
        print(f"\n  [thesaurus] No cache at {thesaurus_path} — skipping (run build_conceptnet_cache.py first)")

    # Materialize personal judgments (higher modality — dominate over thesaurus)
    print("\nMaterializing personal judgments...")
    t0 = time.time()
    for j in judgments:
        space.materialize_judgment(j)
    print(f"  Done in {time.time()-t0:.3f}s")
    print(f"  Concepts: {len(space.concepts)}")

    # Sort concepts by component count
    by_count = sorted(
        space.concepts.items(),
        key=lambda x: len(x[1].components),
        reverse=True
    )
    print("\n  Top concepts by richness:")
    for term, concept in by_count[:15]:
        print(f"    {term}: {len(concept.components)} components, mass={np.trace(concept.rho):.2f}")

    # Recursive deepening
    print("\nRecursive deepening (3 iterations)...")
    t0 = time.time()
    space.recursive_deepen(iterations=3, alpha=0.7)
    print(f"  Done in {time.time()-t0:.3f}s")

    # Reports for top concepts
    print("\n" + "=" * 60)
    print("REPORTS FOR TOP CONCEPTS")
    print("=" * 60)

    for term, concept in by_count[:8]:
        space.report(term)

    # Asymmetry examples
    print("\n" + "=" * 60)
    print("ASYMMETRY EXAMPLES")
    print("=" * 60)

    top_terms = [t for t, _ in by_count[:8]]
    for i, a in enumerate(top_terms):
        for b in top_terms[i+1:i+4]:
            ra = space.concepts[a].rho_deep
            rb = space.concepts[b].rho_deep
            if ra is None or rb is None:
                continue
            h_ab = graded_hyponymy(rb, ra)  # a contains b
            h_ba = graded_hyponymy(ra, rb)  # b contains a
            if abs(h_ab - h_ba) > 0.01:
                direction = ">>>" if h_ab > h_ba else "<<<"
                print(f"  {a} contains {b}: {h_ab:.3f}  |  {b} contains {a}: {h_ba:.3f}  {direction}")

    # Self-container report
    print("\n" + "=" * 60)
    print("[SELF] CONTAINER")
    print("=" * 60)
    space.report_self()

    # Polysemy ranking (only concepts with >= 3 components)
    print("\n" + "=" * 60)
    print("POLYSEMY RANKING (top 15, min 3 components)")
    print("=" * 60)

    polysemy_scores = []
    for term, concept in space.concepts.items():
        if concept.rho_deep_norm is not None and len(concept.components) >= 3:
            e = von_neumann_entropy(concept.rho_deep_norm)
            polysemy_scores.append((term, e, len(concept.components)))
    polysemy_scores.sort(key=lambda x: -x[1])
    for term, entropy, n_comp in polysemy_scores[:15]:
        print(f"  {term}: entropy={entropy:.3f} ({n_comp} components)")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
