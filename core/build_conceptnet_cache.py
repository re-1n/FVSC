# -*- coding: utf-8 -*-
"""
Build a Russian-only ConceptNet cache from the full assertions dump.

Input:  data/conceptnet-assertions-5.7.0.csv.gz (download from ConceptNet S3)
Output: data/conceptnet_ru.json — lightweight JSON with Russian-only edges

The full dump is ~1 GB compressed, ~10 GB uncompressed.
Russian subset is typically ~100-200K edges → ~10-20 MB JSON.

Usage:
    python build_conceptnet_cache.py [min_weight]

    min_weight: minimum edge weight to include (default: 1.0)
                higher = fewer but more reliable edges
"""

import gzip
import json
import os
import sys
import time


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DUMP_PATH = os.path.join(DATA_DIR, "conceptnet-assertions-5.7.0.csv.gz")
CACHE_PATH = os.path.join(DATA_DIR, "conceptnet_ru.json")

# Relations we actually use (skip FormOf, ExternalURL, dbpedia, etc.)
USEFUL_RELATIONS = {
    "IsA", "PartOf", "HasA", "UsedFor", "CapableOf", "HasProperty",
    "MadeOf", "Causes", "CreatedBy", "DefinedAs", "Synonym", "Antonym",
    "AtLocation", "RelatedTo", "DerivedFrom", "SimilarTo", "Desires",
    "ReceivesAction", "HasSubevent", "HasPrerequisite",
    "HasFirstSubevent", "HasLastSubevent", "MotivatedByGoal", "CausesDesire",
}


def extract_term(uri: str) -> str | None:
    """Extract Russian term from ConceptNet URI like /c/ru/банан/n."""
    if not uri.startswith("/c/ru/"):
        return None
    parts = uri.split("/")
    if len(parts) < 4:
        return None
    return parts[3].replace("_", " ")


def extract_relation(uri: str) -> str | None:
    """Extract relation name from URI like /r/IsA."""
    if not uri.startswith("/r/"):
        return None
    return uri.split("/")[2]


def build_cache(min_weight: float = 1.0):
    """Parse ConceptNet dump, filter Russian edges, write JSON cache."""
    if not os.path.exists(DUMP_PATH):
        print(f"ERROR: ConceptNet dump not found at {DUMP_PATH}")
        print(f"Download it from:")
        print(f"  https://s3.amazonaws.com/conceptnet/downloads/2019/edges/conceptnet-assertions-5.7.0.csv.gz")
        sys.exit(1)

    print(f"Parsing {DUMP_PATH}...")
    print(f"  min_weight = {min_weight}")
    t0 = time.time()

    edges = []
    total_lines = 0
    russian_lines = 0

    with gzip.open(DUMP_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            total_lines += 1
            if total_lines % 5_000_000 == 0:
                print(f"  {total_lines:,} lines processed, {len(edges)} Russian edges found...")

            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue

            # columns: assertion_uri, relation, start, end, metadata_json
            rel_uri = parts[1]
            start_uri = parts[2]
            end_uri = parts[3]
            meta_json = parts[4]

            # Both must be Russian
            start_term = extract_term(start_uri)
            if start_term is None:
                continue
            end_term = extract_term(end_uri)
            if end_term is None:
                continue

            russian_lines += 1

            # Filter relation
            rel = extract_relation(rel_uri)
            if rel not in USEFUL_RELATIONS:
                continue

            # Parse weight from metadata
            try:
                meta = json.loads(meta_json)
                weight = meta.get("weight", 1.0)
            except (json.JSONDecodeError, KeyError):
                weight = 1.0

            if weight < min_weight:
                continue

            # Skip single-character terms and self-loops
            if len(start_term) < 2 or len(end_term) < 2:
                continue
            if start_term == end_term:
                continue

            edges.append({
                "rel": rel,
                "start": start_term,
                "end": end_term,
                "weight": round(weight, 2),
            })

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Total lines: {total_lines:,}")
    print(f"  Russian lines: {russian_lines:,}")
    print(f"  Filtered edges: {len(edges)}")

    # Sort by weight descending for easy inspection
    edges.sort(key=lambda x: -x["weight"])

    # Write cache
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(edges, f, ensure_ascii=False, indent=None)

    size_mb = os.path.getsize(CACHE_PATH) / 1024 / 1024
    print(f"\nCache written: {CACHE_PATH} ({size_mb:.1f} MB, {len(edges)} edges)")

    # Print sample
    print("\nSample edges:")
    for e in edges[:20]:
        print(f"  {e['start']} --[{e['rel']}]--> {e['end']}  (w={e['weight']})")

    # Stats by relation
    print("\nEdges by relation:")
    from collections import Counter
    rel_counts = Counter(e["rel"] for e in edges)
    for rel, count in rel_counts.most_common():
        print(f"  {rel}: {count}")


if __name__ == "__main__":
    min_w = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    build_cache(min_weight=min_w)
