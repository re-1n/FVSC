# -*- coding: utf-8 -*-
"""
T7: Scale testing on real Telegram corpus.

Runs the full pipeline on a large corpus and reports:
- Extraction stats (judgments, concepts, extraction times)
- Top concepts by richness
- Anomaly distribution
- Memory usage
- extraction_confidence distribution

Usage: python -X utf8 test_scale.py <path_to_result.json> [max_messages] [sender_filter]

Example:
  python -X utf8 test_scale.py "../экспорты чатов/result глубокий (Davurr and Sqmos).json" 5000 Davurr
"""

import sys
import os
import json
import time
import tracemalloc
import numpy as np

try:
    from .density_core import (SemanticSpace, Judgment, von_neumann_entropy,
                               purity, facets, containment)
    from .tree_extractor import extract_judgments_recursive
    from .live_test import read_telegram_messages, read_telegram_messages_by_sender, build_seed_vectors
    from .thesaurus_loader import ThesaurusLoader
    from .sentence_segmenter import segment_and_flatten
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from density_core import (SemanticSpace, Judgment, von_neumann_entropy,
                              purity, facets, containment)
    from tree_extractor import extract_judgments_recursive
    from live_test import read_telegram_messages, read_telegram_messages_by_sender, build_seed_vectors
    from thesaurus_loader import ThesaurusLoader
    from sentence_segmenter import segment_and_flatten


def main():
    if len(sys.argv) < 2:
        print("Usage: python -X utf8 test_scale.py <result.json> [max_messages] [sender_filter]")
        sys.exit(1)

    path = sys.argv[1]
    max_msgs = int(sys.argv[2]) if len(sys.argv) > 2 else 0  # 0 = all
    sender_filter = sys.argv[3] if len(sys.argv) > 3 else None

    print("=" * 70)
    print("T7: Scale Testing — Full Pipeline on Real Corpus")
    print("=" * 70)

    tracemalloc.start()

    # --- Load messages ---
    print(f"\nLoading: {os.path.basename(path)}")
    if sender_filter:
        print(f"  Filtering sender: {sender_filter}")
        all_msgs = read_telegram_messages_by_sender(path, max_msgs=max_msgs)
        filtered = [(s, t) for s, t in all_msgs if s == sender_filter]
        texts = [t for _, t in filtered]
        # For timestamps, re-read with read_telegram_messages
        texts_with_ts, timestamps = read_telegram_messages(path, max_msgs=max_msgs or 999999)
        # Use only texts from filtered sender (approximate — timestamps may not align perfectly)
        timestamps = timestamps[:len(texts)] if timestamps else []
        print(f"  {len(all_msgs)} total blocks → {len(texts)} from {sender_filter}")
    else:
        texts, timestamps = read_telegram_messages(path, max_msgs=max_msgs or 999999)
        print(f"  {len(texts)} text blocks")

    if not texts:
        print("No texts found.")
        return

    # --- Segment merged blocks into sentences (SaT L1 preprocessor) ---
    block_count = len(texts)
    texts, timestamps = segment_and_flatten(texts, timestamps)
    print(f"  SaT segmentation: {block_count} blocks -> {len(texts)} sentences")

    # --- Load spaCy ---
    print("\nLoading spaCy ru_core_news_md...")
    import spacy
    t0 = time.time()
    nlp = spacy.load("ru_core_news_md")
    spacy_time = time.time() - t0
    print(f"  Loaded in {spacy_time:.1f}s")

    # --- Extract judgments ---
    print(f"\nExtracting judgments from {len(texts)} texts...")
    t0 = time.time()
    judgments = extract_judgments_recursive(nlp, texts, timestamps=timestamps)
    extract_time = time.time() - t0
    print(f"  {len(judgments)} judgments in {extract_time:.1f}s")
    print(f"  Rate: {len(texts)/extract_time:.0f} texts/sec, {len(judgments)/max(0.01,extract_time):.0f} judgments/sec")

    if not judgments:
        print("No judgments extracted.")
        return

    # --- Stats ---
    # Extraction confidence distribution
    confidences = [j.extraction_confidence for j in judgments]
    print(f"\n  extraction_confidence:")
    print(f"    mean={np.mean(confidences):.3f}, median={np.median(confidences):.3f}")
    print(f"    min={np.min(confidences):.3f}, max={np.max(confidences):.3f}")
    print(f"    <0.5: {sum(1 for c in confidences if c < 0.5)} ({sum(1 for c in confidences if c < 0.5)/len(confidences):.1%})")
    print(f"    <0.7: {sum(1 for c in confidences if c < 0.7)} ({sum(1 for c in confidences if c < 0.7)/len(confidences):.1%})")

    # Quality distribution
    neg = sum(1 for j in judgments if j.quality == "NEGATIVE")
    print(f"\n  Quality: {len(judgments)-neg} AFFIRM, {neg} NEGATIVE ({neg/len(judgments):.1%})")

    # Modality distribution
    factual = sum(1 for j in judgments if j.modality >= 0.9)
    epistemic = sum(1 for j in judgments if 0.4 < j.modality < 0.9)
    conditional = sum(1 for j in judgments if j.modality <= 0.4)
    print(f"  Modality: {factual} factual, {epistemic} epistemic, {conditional} conditional")

    # Unique terms
    all_terms = set()
    for j in judgments:
        all_terms.update([j.subject, j.verb, j.object])
    print(f"  Unique terms: {len(all_terms)}")

    # --- Build semantic space ---
    print("\nBuilding seed vectors...")
    dim = 100
    seed_vectors = build_seed_vectors(nlp, all_terms, dim)
    print(f"  Terms with vectors: {len(seed_vectors)}/{len(all_terms)}")

    space = SemanticSpace(dim=dim, seed_vectors=seed_vectors, min_components_for_query=3)

    # Thesaurus layer
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    thesaurus_path = os.path.join(data_dir, "conceptnet_ru.json")
    if os.path.exists(thesaurus_path):
        print("Loading thesaurus...")
        loader = ThesaurusLoader(conceptnet_cache=thesaurus_path, ruwordnet_dir=data_dir)
        thes_j = loader.load_for_terms(all_terms)
        for j in thes_j:
            space.materialize_judgment(j)
        print(f"  {len(thes_j)} thesaurus judgments")

    # Materialize personal judgments
    print("\nMaterializing personal judgments...")
    t0 = time.time()
    for j in judgments:
        space.materialize_judgment(j)
    mat_time = time.time() - t0
    print(f"  {len(space.concepts)} concepts in {mat_time:.3f}s")

    # --- Recursive deepening ---
    print("\nRecursive deepening (k=4, alpha=0.8)...")
    t0 = time.time()
    space.recursive_deepen(iterations=4, alpha=0.8)
    deep_time = time.time() - t0
    print(f"  Done in {deep_time:.1f}s")

    # --- Analysis ---
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    # Top concepts
    by_count = sorted(
        space.concepts.items(),
        key=lambda x: sum(1 for c in x[1].components if not c.archived),
        reverse=True
    )

    print(f"\nTop 20 concepts by richness:")
    for term, concept in by_count[:20]:
        active = sum(1 for c in concept.components if not c.archived)
        rho_n = concept.rho_deep_norm
        ent = von_neumann_entropy(rho_n) if rho_n is not None else 0
        pur = purity(rho_n) if rho_n is not None else 0
        print(f"  {term:25s}  components={active:4d}  entropy={ent:.3f}  purity={pur:.3f}")

    # Anomaly distribution
    anomalies = [j.anomaly_score for j in judgments if j.anomaly_score is not None]
    if anomalies:
        print(f"\nAnomaly scores ({len(anomalies)} scored):")
        print(f"  mean={np.mean(anomalies):.3f}, median={np.median(anomalies):.3f}")
        print(f"  >0.7 (unusual): {sum(1 for a in anomalies if a > 0.7)} ({sum(1 for a in anomalies if a > 0.7)/len(anomalies):.1%})")
        print(f"  >0.85 (anomaly): {sum(1 for a in anomalies if a > 0.85)} ({sum(1 for a in anomalies if a > 0.85)/len(anomalies):.1%})")

    # Self container
    sc = space.self_concept
    if sc.components:
        active_self = sum(1 for c in sc.components if not c.archived)
        print(f"\n[self] container: {active_self} active components")

    # Memory
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"\nMemory: current={current/1024/1024:.1f} MB, peak={peak/1024/1024:.1f} MB")

    # Timing summary
    print(f"\nTiming:")
    print(f"  spaCy load:       {spacy_time:.1f}s")
    print(f"  Extraction:       {extract_time:.1f}s ({len(judgments)} judgments)")
    print(f"  Materialization:  {mat_time:.3f}s ({len(space.concepts)} concepts)")
    print(f"  Recursive deepen: {deep_time:.1f}s (k=4, alpha=0.8)")

    print(f"\nVerb concepts (top 10):")
    verbs = [(t, c) for t, c in by_count if c.is_verb]
    for term, concept in verbs[:10]:
        active = sum(1 for c in concept.components if not c.archived)
        print(f"  [{term}]: {active} components")


if __name__ == "__main__":
    main()
