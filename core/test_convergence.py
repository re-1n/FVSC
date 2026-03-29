# -*- coding: utf-8 -*-
"""
T4: Recursive deepening convergence analysis.

Sweep over alpha values and iteration counts.
Measures: eigenvalue stability, containment stability, trace growth.
Finds optimal alpha and early stopping criterion.

Usage: python -X utf8 test_convergence.py
"""

import sys
import os
import time
import numpy as np

try:
    from .density_core import (SemanticSpace, Judgment, von_neumann_entropy,
                               purity, containment)
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from density_core import (SemanticSpace, Judgment, von_neumann_entropy,
                              purity, containment)


def build_test_space(n_judgments: int = 50, dim: int = 50) -> SemanticSpace:
    """Build a reasonably rich test space from synthetic judgments."""
    np.random.seed(42)
    space = SemanticSpace(dim=dim)

    concepts = ["свобода", "ответственность", "выбор", "любовь", "страх",
                "доверие", "мужество", "долг", "независимость", "одиночество",
                "сила", "слабость", "честность", "ложь", "справедливость"]
    verbs = ["требовать", "включать", "порождать", "давать", "разрушать",
             "укреплять", "являться", "противостоять"]

    rng = np.random.default_rng(42)
    judgments = []
    for _ in range(n_judgments):
        s = rng.choice(concepts)
        o = rng.choice([c for c in concepts if c != s])
        v = rng.choice(verbs)
        quality = rng.choice(["AFFIRMATIVE", "AFFIRMATIVE", "AFFIRMATIVE", "NEGATIVE"])
        modality = rng.choice([1.0, 0.7, 0.5, 0.4])
        intensity = rng.uniform(0.3, 0.9)
        j = Judgment(subject=s, verb=v, object=o, quality=quality,
                     modality=modality, intensity=intensity)
        judgments.append(j)
        space.materialize_judgment(j)

    return space


def snapshot_eigenvalues(space: SemanticSpace, top_n: int = 10) -> dict[str, np.ndarray]:
    """Capture eigenvalues of top concepts' rho_deep."""
    result = {}
    by_count = sorted(space.concepts.items(),
                      key=lambda x: len(x[1].components), reverse=True)
    for term, concept in by_count[:top_n]:
        rho = concept.rho_deep
        if rho is not None:
            eigvals = np.sort(np.linalg.eigvalsh(rho))[::-1]
            result[term] = eigvals
    return result


def snapshot_containments(space: SemanticSpace, pairs: list[tuple[str, str]]) -> dict:
    """Capture containment values for specific pairs."""
    result = {}
    for a, b in pairs:
        ca = space.concepts.get(a)
        cb = space.concepts.get(b)
        if ca and cb and ca.rho_deep is not None and cb.rho_deep is not None:
            result[(a, b)] = containment(ca.rho_deep, cb.rho_deep)
        else:
            result[(a, b)] = 0.0
    return result


def eigenvalue_delta(snap_a: dict, snap_b: dict) -> float:
    """Mean absolute change in eigenvalues between two snapshots."""
    deltas = []
    for term in snap_a:
        if term in snap_b:
            d = np.abs(snap_a[term] - snap_b[term])
            deltas.append(np.mean(d))
    return float(np.mean(deltas)) if deltas else 0.0


def containment_delta(snap_a: dict, snap_b: dict) -> float:
    """Mean absolute change in containment values."""
    deltas = []
    for key in snap_a:
        if key in snap_b:
            deltas.append(abs(snap_a[key] - snap_b[key]))
    return float(np.mean(deltas)) if deltas else 0.0


def run_sweep():
    print("=" * 70)
    print("T4: Recursive Deepening — Convergence Analysis")
    print("=" * 70)

    # Key pairs to track
    pairs = [
        ("свобода", "ответственность"), ("ответственность", "свобода"),
        ("свобода", "выбор"), ("любовь", "доверие"),
        ("мужество", "страх"), ("сила", "слабость"),
    ]

    alphas = [0.5, 0.6, 0.7, 0.8, 0.9]
    max_iters = 10

    print(f"\nSweep: alpha ∈ {alphas}, iterations 1..{max_iters}")
    print(f"Test space: 50 synthetic judgments, 15 concepts, dim=50\n")

    results = {}

    for alpha in alphas:
        print(f"--- alpha = {alpha} ---")
        eig_deltas = []
        cont_deltas = []
        traces = []

        for k in range(1, max_iters + 1):
            # Rebuild space fresh each time (deepening is cumulative)
            space = build_test_space(n_judgments=50, dim=50)

            # Take snapshot before deepening
            if k == 1:
                prev_eig = snapshot_eigenvalues(space)
                prev_cont = snapshot_containments(space, pairs)

            # Deepen exactly k iterations
            space.recursive_deepen(iterations=k, alpha=alpha)

            # Take snapshot after
            curr_eig = snapshot_eigenvalues(space)
            curr_cont = snapshot_containments(space, pairs)

            # Compute deltas vs previous iteration
            if k > 1:
                ed = eigenvalue_delta(prev_eig, curr_eig)
                cd = containment_delta(prev_cont, curr_cont)
                eig_deltas.append(ed)
                cont_deltas.append(cd)

                # Total trace (mass)
                total_trace = sum(
                    float(np.trace(c.rho_deep)) for c in space.concepts.values()
                    if c.rho_deep is not None
                )
                traces.append(total_trace)

                print(f"  k={k}: Δeig={ed:.6f}  Δcont={cd:.6f}  total_mass={total_trace:.2f}")

                # Early stopping check
                if ed < 1e-6 and cd < 1e-5:
                    print(f"  → Converged at k={k}")
                    break

            prev_eig = curr_eig
            prev_cont = curr_cont

        results[alpha] = {
            "eig_deltas": eig_deltas,
            "cont_deltas": cont_deltas,
            "traces": traces,
            "converged_at": k if (eig_deltas and eig_deltas[-1] < 1e-6) else None,
        }
        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'alpha':>6} | {'conv_k':>6} | {'final Δeig':>12} | {'final Δcont':>12} | {'mass_growth':>12}")
    print("-" * 70)
    for alpha, r in results.items():
        conv = r["converged_at"] or "—"
        feig = f"{r['eig_deltas'][-1]:.8f}" if r['eig_deltas'] else "—"
        fcont = f"{r['cont_deltas'][-1]:.8f}" if r['cont_deltas'] else "—"
        if len(r['traces']) >= 2:
            growth = f"{r['traces'][-1] / r['traces'][0]:.3f}x"
        else:
            growth = "—"
        print(f"{alpha:>6} | {str(conv):>6} | {feig:>12} | {fcont:>12} | {growth:>12}")

    print()

    # Recommendation
    best_alpha = min(results.keys(),
                     key=lambda a: results[a]["eig_deltas"][-1] if results[a]["eig_deltas"] else 999)
    best = results[best_alpha]
    print(f"Recommendation: alpha={best_alpha}")
    if best["converged_at"]:
        print(f"  Converges at k={best['converged_at']}")
    print(f"  Final eigenvalue delta: {best['eig_deltas'][-1]:.8f}" if best['eig_deltas'] else "")
    print(f"  Mass growth: {best['traces'][-1]/best['traces'][0]:.3f}x" if len(best['traces']) >= 2 else "")

    # Early stopping criterion
    print(f"\nEarly stopping criterion: Δeig < 1e-6 AND Δcont < 1e-5")
    print("This means eigenvalues and containment values have stabilized.")


if __name__ == "__main__":
    run_sweep()
