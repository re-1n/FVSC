# -*- coding: utf-8 -*-
"""
Mathematical invariant tests for density_core.

These properties must hold for any input — violations indicate a bug
in the math, not in the data. Run before/after every refactor of
density_core to catch regressions.

Usage: python -X utf8 -m core.test_invariants
"""

import sys
import os
import math
import numpy as np

try:
    from .density_core import (
        SemanticSpace, Judgment, Concept,
        containment, graded_hyponymy, trace_inner_product,
        von_neumann_entropy, purity, facets,
    )
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from density_core import (
        SemanticSpace, Judgment, Concept,
        containment, graded_hyponymy, trace_inner_product,
        von_neumann_entropy, purity, facets,
    )


# ─────────────────────────── helpers ───────────────────────────

_FAILURES: list[str] = []
_PASSES: int = 0


def check(name: str, condition: bool, detail: str = ""):
    global _PASSES
    if condition:
        _PASSES += 1
        print(f"  [+] {name}")
    else:
        _FAILURES.append(f"{name}: {detail}")
        print(f"  [-] {name}  {detail}")


def approx(a: float, b: float, eps: float = 1e-9) -> bool:
    return abs(a - b) < eps


def _make_space(judgments: list[tuple[str, str, str]], dim: int = 32) -> SemanticSpace:
    """Build a space from (subject, verb, object) triples."""
    space = SemanticSpace(dim=dim)
    for s, v, o in judgments:
        space.materialize_judgment(Judgment(subject=s, verb=v, object=o,
                                            modality=1.0, intensity=1.0))
    return space


# ─────────────────────────── invariants ───────────────────────────

def test_density_matrix_properties():
    """ρ must be symmetric and positive semi-definite (PSD)."""
    print("\n[1] Density matrix properties (symmetry, PSD)")
    space = _make_space([
        ("свобода", "требует", "ответственность"),
        ("свобода", "включает", "выбор"),
        ("ответственность", "включает", "долг"),
    ])
    for term, c in space.concepts.items():
        rho = c.rho
        if rho is None:
            continue
        # Symmetry: ρ = ρ^T
        max_asym = float(np.max(np.abs(rho - rho.T)))
        check(f"  {term}: ρ symmetric", max_asym < 1e-9, f"max|ρ-ρᵀ|={max_asym}")
        # PSD: all eigenvalues ≥ 0 (allow tiny numerical noise)
        eigs = np.linalg.eigvalsh(rho)
        check(f"  {term}: ρ PSD",
              bool(np.all(eigs >= -1e-9)),
              f"min eig={float(eigs.min())}")
        # Trace > 0 for non-empty concepts
        check(f"  {term}: Tr(ρ) > 0", float(np.trace(rho)) > 0,
              f"trace={float(np.trace(rho))}")


def test_normalized_trace():
    """rho_norm must have trace == 1."""
    print("\n[2] Normalization (Tr(ρ_norm) = 1)")
    space = _make_space([
        ("свобода", "требует", "ответственность"),
        ("свобода", "включает", "выбор"),
    ])
    for term, c in space.concepts.items():
        rn = c.rho_norm
        if rn is None:
            continue
        tr = float(np.trace(rn))
        check(f"  {term}: Tr(ρ_norm) = 1", approx(tr, 1.0, eps=1e-9),
              f"trace={tr}")


def test_containment_bounds():
    """containment(A,B) ∈ [0, 1] for normalized states; ≥ 0 always."""
    print("\n[3] Containment bounds (≥ 0)")
    space = _make_space([
        ("свобода", "требует", "ответственность"),
        ("свобода", "включает", "выбор"),
        ("любовь", "включает", "доверие"),
    ])
    terms = [t for t, c in space.concepts.items() if c.rho is not None]
    for a in terms:
        for b in terms:
            if a == b:
                continue
            c = containment(space.concepts[a].rho, space.concepts[b].rho)
            check(f"  c({a},{b}) ≥ 0", c >= -1e-9, f"c={c}")


def test_containment_asymmetry():
    """containment must be asymmetric for at least some pairs.
    If c(A,B) = c(B,A) for ALL pairs, the structure is degenerate.
    """
    print("\n[4] Containment asymmetry (some pairs c(A,B) ≠ c(B,A))")
    # Build asymmetric scenario: "свобода" mentioned 3x, "долг" 1x
    space = SemanticSpace(dim=32)
    for _ in range(3):
        space.materialize_judgment(Judgment(
            subject="свобода", verb="требует", object="долг",
            modality=1.0, intensity=1.0))
    space.materialize_judgment(Judgment(
        subject="долг", verb="включает", object="обязанность",
        modality=1.0, intensity=1.0))

    rho_s = space.concepts["свобода"].rho
    rho_d = space.concepts["долг"].rho
    c_sd = containment(rho_s, rho_d)
    c_ds = containment(rho_d, rho_s)
    check("  c(свобода,долг) ≠ c(долг,свобода)",
          abs(c_sd - c_ds) > 1e-6,
          f"c_sd={c_sd:.4f}, c_ds={c_ds:.4f}")


def test_entropy_nonnegativity():
    """von Neumann entropy S(ρ) ≥ 0 always."""
    print("\n[5] Entropy non-negativity")
    space = _make_space([
        ("свобода", "требует", "ответственность"),
        ("свобода", "включает", "выбор"),
        ("свобода", "даёт", "независимость"),
    ])
    for term, c in space.concepts.items():
        rn = c.rho_norm
        if rn is None:
            continue
        s = von_neumann_entropy(rn)
        check(f"  S({term}) ≥ 0", s >= -1e-9, f"S={s}")


def test_entropy_pure_state():
    """S(|ψ⟩⟨ψ|) = 0 for any rank-1 (pure) state."""
    print("\n[6] Entropy of pure state = 0")
    # Single judgment → single component → rank-1 density matrix
    space = _make_space([("одиночество", "даёт", "ясность")])
    for term, c in space.concepts.items():
        rn = c.rho_norm
        if rn is None:
            continue
        s = von_neumann_entropy(rn)
        check(f"  S({term}) ≈ 0 (pure state)", abs(s) < 1e-6, f"S={s}")


def test_entropy_max_bound():
    """S(ρ) ≤ log(d) where d is dimension."""
    print("\n[7] Entropy upper bound (S ≤ log d)")
    dim = 16
    space = SemanticSpace(dim=dim)
    # Lots of diverse judgments to maximize entropy
    objects = [f"obj{i}" for i in range(20)]
    for o in objects:
        space.materialize_judgment(Judgment(
            subject="концепт", verb="связан", object=o,
            modality=1.0, intensity=1.0))
    rn = space.concepts["концепт"].rho_norm
    s = von_neumann_entropy(rn)
    max_s = math.log(dim)
    check(f"  S(концепт)={s:.3f} ≤ log({dim})={max_s:.3f}",
          s <= max_s + 1e-6)


def test_purity_bounds():
    """Purity Tr(ρ²) ∈ [1/d, 1]."""
    print("\n[8] Purity bounds (1/d ≤ Tr(ρ²) ≤ 1)")
    dim = 16
    space = SemanticSpace(dim=dim)
    space.materialize_judgment(Judgment(
        subject="x", verb="y", object="z", modality=1.0, intensity=1.0))
    for term, c in space.concepts.items():
        rn = c.rho_norm
        if rn is None:
            continue
        p = purity(rn)
        check(f"  P({term}) ∈ [{1/dim:.3f}, 1.0]",
              1/dim - 1e-6 <= p <= 1.0 + 1e-6,
              f"P={p}")


def test_trace_inner_product_symmetry():
    """Tr(ρ_A · ρ_B) = Tr(ρ_B · ρ_A) — always symmetric."""
    print("\n[9] Trace inner product symmetry")
    space = _make_space([
        ("свобода", "требует", "ответственность"),
        ("любовь", "включает", "доверие"),
    ])
    terms = [t for t, c in space.concepts.items() if c.rho is not None]
    for i, a in enumerate(terms):
        for b in terms[i+1:]:
            t_ab = trace_inner_product(space.concepts[a].rho, space.concepts[b].rho)
            t_ba = trace_inner_product(space.concepts[b].rho, space.concepts[a].rho)
            check(f"  Tr(ρ_{a}·ρ_{b}) = Tr(ρ_{b}·ρ_{a})",
                  approx(t_ab, t_ba, eps=1e-9),
                  f"Δ={abs(t_ab-t_ba)}")


def test_consolidation_no_duplicates():
    """Adding same judgment twice → activation_count grows, not components."""
    print("\n[10] Consolidation (cosine > 0.85 → reinforce, not duplicate)")
    space = SemanticSpace(dim=32)
    j = Judgment(subject="свобода", verb="требует", object="долг",
                 modality=1.0, intensity=1.0)
    space.materialize_judgment(j)
    n1 = len(space.concepts["свобода"].components)
    # Same judgment again (same timestamp, same vectors)
    space.materialize_judgment(Judgment(
        subject="свобода", verb="требует", object="долг",
        modality=1.0, intensity=1.0, timestamp=j.timestamp))
    n2 = len(space.concepts["свобода"].components)
    check("  Same judgment → no new component",
          n1 == n2, f"n1={n1}, n2={n2}")
    counts = [c.activation_count for c in space.concepts["свобода"].components]
    check("  activation_count incremented",
          max(counts) >= 2, f"counts={counts}")


def test_layered_rho_filtering():
    """rho_layer(0) only includes L0 components."""
    print("\n[11] Layered ρ filtering (L0 vs L1+)")
    space = SemanticSpace(dim=32)
    space.materialize_judgment(Judgment(
        subject="свобода", verb="требует", object="долг",
        modality=1.0, intensity=1.0, interpretation_layer=0))
    space.materialize_judgment(Judgment(
        subject="свобода", verb="намекает", object="ответственность",
        modality=0.5, intensity=1.0, interpretation_layer=1))

    c = space.concepts["свобода"]
    r0 = c.rho_layer(max_layer=0)
    r1 = c.rho_layer(max_layer=1)
    check("  ρ_L0 exists", r0 is not None)
    check("  ρ_L1 exists", r1 is not None)
    if r0 is not None and r1 is not None:
        # L1 trace should be >= L0 trace (more components)
        check("  Tr(ρ_L1) > Tr(ρ_L0)",
              float(np.trace(r1)) > float(np.trace(r0)) - 1e-9)


def test_decay_monotonic():
    """Weight decay must be monotonically non-increasing over time."""
    print("\n[12] Decay monotonicity")
    space = SemanticSpace(dim=32)
    import time
    t0 = time.time()
    space.materialize_judgment(Judgment(
        subject="x", verb="y", object="z",
        modality=1.0, intensity=1.0, timestamp=t0))
    c = space.concepts["x"]
    comp = c.components[0]
    w_now = c._decayed_weight(comp, t0)
    w_later = c._decayed_weight(comp, t0 + 365 * 86400)  # 1 year later
    check("  decay: w(t+Δt) ≤ w(t)",
          w_later <= w_now + 1e-9,
          f"w_now={w_now}, w_later={w_later}")
    check("  decay actually decreases over a year",
          w_later < w_now,
          f"w_now={w_now}, w_later={w_later}")


def test_load_from_semantic_input_roundtrip():
    """Concepts loaded from semantic_input dict appear in SemanticSpace."""
    print("\n[13] load_from_semantic_input — concept presence")
    space = SemanticSpace(dim=32)
    si = {
        "свобода": {"weight": 1.0, "contains": {"ответственность": 0.7, "выбор": 0.5}},
        "ответственность": {"weight": 0.8, "contains": {"долг": 0.6}},
    }
    space.load_from_semantic_input(si)
    for term in si:
        check(f"  concept '{term}' present", term in space.concepts)
        if term in space.concepts:
            check(f"  '{term}' has ρ", space.concepts[term].rho is not None)


def test_rich_judgment_layers():
    """RichJudgment: all 6 layers preserved through materialize_judgment."""
    print("\n[14] RichJudgment — 6-layer fields preserved in components")
    space = SemanticSpace(dim=32)
    j = Judgment(
        subject="свобода", verb="требует", object="ответственность",
        # Layer 1 extras
        negation_scope=False, modality_type="DEONTIC",
        # Layer 2: Frame
        frame_name="Required_event",
        semantic_roles={"AGENT": "свобода", "PATIENT": "ответственность"},
        role_intensity=0.8,
        # Layer 3: Polysemy
        facet_id=2, polysemy_degree=0.4,
        # Layer 4: Bodily
        perceptual_modalities={"kinesthetic"},
        perceptual_features={"texture": "rough", "size": 0.7},
        emotion_tags={"determination": 0.6},
        # Layer 5: Social
        context_metadata={"source": "self", "social_group": "philosophy",
                          "register": "formal", "medium": "writing"},
        # Layer 6: Reflective
        user_marked_facet=True, user_confidence=0.9,
    )
    space.materialize_judgment(j)
    # Pull the stored judgment back out of the component
    comp = space.concepts["свобода"].components[0]
    sj = comp.judgment
    check("  Layer 1: modality_type preserved", sj.modality_type == "DEONTIC")
    check("  Layer 2: frame_name preserved", sj.frame_name == "Required_event")
    check("  Layer 2: semantic_roles preserved",
          sj.semantic_roles.get("AGENT") == "свобода")
    check("  Layer 2: role_intensity preserved", sj.role_intensity == 0.8)
    check("  Layer 3: facet_id preserved", sj.facet_id == 2)
    check("  Layer 3: polysemy_degree preserved", sj.polysemy_degree == 0.4)
    check("  Layer 4: perceptual_modalities preserved",
          "kinesthetic" in sj.perceptual_modalities)
    check("  Layer 4: perceptual_features preserved",
          sj.perceptual_features.get("texture") == "rough")
    check("  Layer 4: emotion_tags preserved",
          sj.emotion_tags.get("determination") == 0.6)
    check("  Layer 5: context_metadata preserved",
          sj.context_metadata.get("social_group") == "philosophy")
    check("  Layer 6: user_marked_facet preserved", sj.user_marked_facet is True)
    check("  Layer 6: user_confidence preserved", sj.user_confidence == 0.9)


def test_judgment_defaults_backward_compat():
    """Minimal Judgment (only required fields) still works — backward compat."""
    print("\n[15] Judgment defaults — backward compatibility")
    space = SemanticSpace(dim=32)
    # Old-style call with only S, V, O
    j = Judgment(subject="a", verb="b", object="c")
    space.materialize_judgment(j)
    check("  minimal Judgment materializes", "a" in space.concepts)
    sj = space.concepts["a"].components[0].judgment
    check("  default modality_type=FACTUAL", sj.modality_type == "FACTUAL")
    check("  default frame_name=None", sj.frame_name is None)
    check("  default semantic_roles={}", sj.semantic_roles == {})
    check("  default perceptual_modalities=set()", sj.perceptual_modalities == set())
    check("  default emotion_tags={}", sj.emotion_tags == {})
    check("  default user_confidence=0.0", sj.user_confidence == 0.0)


# ─────────────────────────── runner ───────────────────────────

def main():
    print("=" * 65)
    print("FVSC density_core — Mathematical Invariants")
    print("=" * 65)

    test_density_matrix_properties()
    test_normalized_trace()
    test_containment_bounds()
    test_containment_asymmetry()
    test_entropy_nonnegativity()
    test_entropy_pure_state()
    test_entropy_max_bound()
    test_purity_bounds()
    test_trace_inner_product_symmetry()
    test_consolidation_no_duplicates()
    test_layered_rho_filtering()
    test_decay_monotonic()
    test_load_from_semantic_input_roundtrip()
    test_rich_judgment_layers()
    test_judgment_defaults_backward_compat()

    print("\n" + "=" * 65)
    print(f"PASSED: {_PASSES}")
    print(f"FAILED: {len(_FAILURES)}")
    if _FAILURES:
        print("\nFailures:")
        for f in _FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("All invariants hold.")


if __name__ == "__main__":
    main()
