"""
FVSC Density Matrix -- Proof of Concept Test

Tests the core density matrix operations on Russian semantic data.
No external dependencies beyond numpy.

Run: python test_poc.py
"""

import numpy as np
try:
    from .density_core import SemanticSpace, Judgment, containment, graded_hyponymy, von_neumann_entropy, purity
except ImportError:
    from density_core import SemanticSpace, Judgment, containment, graded_hyponymy, von_neumann_entropy, purity

def main():
    print("=" * 60)
    print("FVSC Density Matrix -- Proof of Concept")
    print("=" * 60)

    # Create semantic space (d=50 for speed)
    space = SemanticSpace(dim=50)

    # ----- Feed judgments -----
    # Person A's understanding of "свобода"
    judgments = [
        Judgment("свобода", "требовать", "ответственность",
                 intensity=0.9, modality=1.0,
                 source_text="Свобода требует ответственности"),
        Judgment("свобода", "требовать", "ответственность",
                 intensity=0.9, modality=1.0,
                 source_text="Свобода всегда требует ответственности"),
        Judgment("свобода", "требовать", "ответственность",
                 intensity=0.8, modality=1.0,
                 source_text="Настоящая свобода требует ответственности"),
        Judgment("свобода", "включать", "выбор",
                 intensity=0.7, modality=1.0,
                 source_text="Свобода включает в себя выбор"),
        Judgment("свобода", "включать", "выбор",
                 intensity=0.6, modality=1.0,
                 source_text="Свобода это прежде всего выбор"),
        Judgment("свобода", "являться", "независимость",
                 intensity=0.5, modality=1.0,
                 source_text="Свобода -- это независимость"),
        Judgment("свобода", "порождать", "страх",
                 intensity=0.4, modality=0.5,
                 source_text="Может ли свобода порождать страх?"),

        # "ответственность"
        Judgment("ответственность", "требовать", "мужество",
                 intensity=0.8, modality=1.0,
                 source_text="Ответственность требует мужества"),
        Judgment("ответственность", "включать", "долг",
                 intensity=0.7, modality=1.0,
                 source_text="Ответственность включает долг"),
        Judgment("ответственность", "являться", "зрелость",
                 intensity=0.6, modality=1.0,
                 source_text="Ответственность -- признак зрелости"),

        # Mutual containment: "ответственность" also contains "свобода"
        Judgment("ответственность", "давать", "свобода",
                 intensity=0.4, modality=0.7,
                 source_text="Ответственность даёт свободу"),

        # "любовь"
        Judgment("любовь", "давать", "свобода",
                 intensity=0.7, modality=1.0,
                 source_text="Любовь даёт свободу"),
        Judgment("любовь", "требовать", "терпение",
                 intensity=0.6, modality=1.0,
                 source_text="Любовь требует терпения"),
        Judgment("любовь", "включать", "доверие",
                 intensity=0.8, modality=1.0,
                 source_text="Любовь включает доверие"),
        Judgment("любовь", "порождать", "уязвимость",
                 intensity=0.5, modality=0.7,
                 source_text="Любовь порождает уязвимость"),

        # "выбор"
        Judgment("выбор", "требовать", "ответственность",
                 intensity=0.7, modality=1.0,
                 source_text="Выбор требует ответственности"),
        Judgment("выбор", "включать", "отказ",
                 intensity=0.5, modality=1.0,
                 source_text="Выбор включает в себя отказ"),
    ]

    print(f"\nMaterializing {len(judgments)} judgments...")
    for j in judgments:
        space.materialize_judgment(j)

    print(f"Concepts created: {len(space.concepts)}")
    for term in space.concepts:
        c = space.concepts[term]
        print(f"  {term}: {len(c.components)} components")

    # ----- Before recursion -----
    print("\n" + "=" * 60)
    print("BEFORE RECURSIVE DEEPENING")
    print("=" * 60)

    print("\n--- Containment (свобода -> ?) ---")
    for term, score in space.query_contains("свобода"):
        print(f"  свобода contains {term}: {score:.3f}")

    print("\n--- Containment (ответственность -> ?) ---")
    for term, score in space.query_contains("ответственность"):
        print(f"  ответственность contains {term}: {score:.3f}")

    # Asymmetry test (graded hyponymy -- asymmetric by construction)
    print("\n--- Asymmetry test (graded hyponymy) ---")
    rho_s = space.concepts["свобода"].rho
    rho_o = space.concepts["ответственность"].rho
    # hyp(отв, своб) = degree отв is inside своб = "своб contains отв"
    h_so = graded_hyponymy(rho_o, rho_s)
    # hyp(своб, отв) = degree своб is inside отв = "отв contains своб"
    h_os = graded_hyponymy(rho_s, rho_o)
    print(f"  свобода contains ответственность: {h_so:.3f}")
    print(f"  ответственность contains свобода: {h_os:.3f}")
    print(f"  Asymmetric: {'YES' if abs(h_so - h_os) > 0.01 else 'NO'} (diff={abs(h_so-h_os):.3f})")
    print(f"  Mass свобода: {np.trace(rho_s):.3f}")
    print(f"  Mass ответственность: {np.trace(rho_o):.3f}")

    # ----- Recursive deepening -----
    print("\n" + "=" * 60)
    print("RECURSIVE DEEPENING (3 iterations)")
    print("=" * 60)

    space.recursive_deepen(iterations=3, alpha=0.7)

    print("\n--- Containment AFTER recursion (свобода -> ?) ---")
    for term, score in space.query_contains("свобода"):
        print(f"  свобода contains {term}: {score:.3f}")

    print("\n--- Containment AFTER recursion (ответственность -> ?) ---")
    for term, score in space.query_contains("ответственность"):
        print(f"  ответственность contains {term}: {score:.3f}")

    # Asymmetry after recursion
    print("\n--- Asymmetry AFTER recursion ---")
    rho_sd = space.concepts["свобода"].rho_deep
    rho_od = space.concepts["ответственность"].rho_deep
    h_so = graded_hyponymy(rho_od, rho_sd)
    h_os = graded_hyponymy(rho_sd, rho_od)
    print(f"  свобода contains ответственность: {h_so:.3f}")
    print(f"  ответственность contains свобода: {h_os:.3f}")
    print(f"  Asymmetric: {'YES' if abs(h_so - h_os) > 0.01 else 'NO'} (diff={abs(h_so-h_os):.3f})")

    # ----- Polysemy -----
    print("\n" + "=" * 60)
    print("POLYSEMY (von Neumann entropy)")
    print("=" * 60)

    for term in ["свобода", "ответственность", "любовь", "выбор", "мужество", "долг"]:
        c = space.concepts.get(term)
        if c and c.rho_deep_norm is not None:
            e = space.query_polysemy(term)
            p = purity(c.rho_deep_norm)
            n_facets = len(space.query_facets(term))
            mass = np.trace(c.rho_deep)
            print(f"  {term}: entropy={e:.3f}, purity={p:.3f}, facets={n_facets}, mass={mass:.2f}")

    # ----- Full reports -----
    print("\n" + "=" * 60)
    print("FULL REPORTS")
    print("=" * 60)

    for term in ["свобода", "ответственность", "любовь"]:
        space.report(term)

    # ----- Similarity -----
    print("\n" + "=" * 60)
    print("SIMILARITY (trace inner product)")
    print("=" * 60)

    pairs = [
        ("свобода", "ответственность"),
        ("свобода", "любовь"),
        ("свобода", "выбор"),
        ("любовь", "доверие"),
        ("мужество", "долг"),
    ]
    for a, b in pairs:
        s = space.query_similarity(a, b)
        print(f"  {a} ~ {b}: {s:.3f}")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
