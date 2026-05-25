"""
End-to-end test: raw text (any language) -> density matrices.

Demonstrates the full agnostic pipeline:
    text -> text_parser_agnostic -> semantic_input -> density matrices

No spaCy, no language-specific parser. Just regex segmentation +
co-occurrence + the existing FVSC density-matrix builder.
"""

import numpy as np

try:
    from .text_parser_agnostic import (
        text_to_semantic_input,
        parse_text,
        ParseConfig,
        DEFAULT_STOPWORDS_RU_EN,
    )
    from .semantic_input import parse_semantic_input
except ImportError:
    from text_parser_agnostic import (
        text_to_semantic_input,
        parse_text,
        ParseConfig,
        DEFAULT_STOPWORDS_RU_EN,
    )
    from semantic_input import parse_semantic_input


# ─────────────────────────── helpers ───────────────────────────

def containment(rho_a: np.ndarray, rho_b: np.ndarray) -> float:
    tr_a = np.trace(rho_a)
    if tr_a < 1e-12:
        return 0.0
    return float(np.sum(rho_a * rho_b.T) / tr_a)


def von_neumann_entropy(rho: np.ndarray) -> float:
    tr = np.trace(rho)
    if tr < 1e-12:
        return 0.0
    rho_norm = rho / tr
    eig = np.linalg.eigvalsh(rho_norm)
    eig = eig[eig > 1e-12]
    return float(-np.sum(eig * np.log(eig)))


def banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ─────────────────────────── tests ───────────────────────────

RU_TEXT = """
Свобода — это возможность выбора. Выбор требует ответственности.
Ответственность означает долг и честность перед собой.
Любовь невозможна без доверия. Доверие строится на терпении и уязвимости.
Программирование — это творчество, ограниченное рутиной и дисциплиной.
Творчество требует свободы. Свобода требует выбора. Выбор требует мужества.
"""

EN_TEXT = """
Freedom is the possibility of choice. Choice demands responsibility.
Responsibility means duty and honesty toward oneself.
Love is impossible without trust. Trust is built on patience and vulnerability.
Programming is creativity bound by routine and discipline.
Creativity demands freedom. Freedom demands choice. Choice demands courage.
"""

INVENTED_TEXT = """
Zephyr ek luminescence. Luminescence ek resonance. Resonance ek ephemera.
Crystalline ek void. Void ek zephyr. Zephyr ek crystalline ek resonance.
"""


def test_russian_raw_text():
    banner("TEST 1: Russian raw text -> density matrices")
    cfg = ParseConfig(
        window=4, min_freq=2, max_concepts=30,
        stopwords=DEFAULT_STOPWORDS_RU_EN, keep_top_contains=5,
    )
    si, vectors, rhos = parse_text(RU_TEXT, dim=64, config=cfg)

    print(f"Concepts extracted: {len(si)}")
    print("Sample concepts (top by self-weight):")
    sample = sorted(si.items(), key=lambda x: -x[1]["weight"])[:6]
    for name, spec in sample:
        ch = spec.get("contains", {})
        ch_str = ", ".join(f"{k}:{v:.2f}" for k, v in list(ch.items())[:4])
        print(f"  {name:<20} w={spec['weight']:.2f}  contains={{{ch_str}}}")

    # Asymmetry check on a co-occurring pair
    if "свобода" in si and "выбор" in si:
        w_s_v = si["свобода"].get("contains", {}).get("выбор", 0.0)
        w_v_s = si["выбор"].get("contains", {}).get("свобода", 0.0)
        print(f"\nAsymmetry: свобода→выбор={w_s_v:.3f}  выбор→свобода={w_v_s:.3f}")

    # Density matrix sanity
    if rhos:
        any_name = next(iter(rhos))
        rho = rhos[any_name]
        print(f"\nρ[{any_name}] shape={rho.shape}, trace={np.trace(rho):.3f}, "
              f"S(ρ)={von_neumann_entropy(rho):.3f}")


def test_english_raw_text():
    banner("TEST 2: English raw text -> density matrices")
    cfg = ParseConfig(
        window=4, min_freq=2, max_concepts=30,
        stopwords=DEFAULT_STOPWORDS_RU_EN, keep_top_contains=5,
    )
    si, vectors, rhos = parse_text(EN_TEXT, dim=64, config=cfg)

    print(f"Concepts extracted: {len(si)}")
    sample = sorted(si.items(), key=lambda x: -x[1]["weight"])[:6]
    for name, spec in sample:
        ch = spec.get("contains", {})
        ch_str = ", ".join(f"{k}:{v:.2f}" for k, v in list(ch.items())[:4])
        print(f"  {name:<20} w={spec['weight']:.2f}  contains={{{ch_str}}}")

    if "freedom" in si and "choice" in si:
        w_fc = si["freedom"].get("contains", {}).get("choice", 0.0)
        w_cf = si["choice"].get("contains", {}).get("freedom", 0.0)
        print(f"\nAsymmetry: freedom→choice={w_fc:.3f}  choice→freedom={w_cf:.3f}")


def test_invented_language():
    banner("TEST 3: Invented language -> density matrices (true agnosticism)")
    cfg = ParseConfig(window=3, min_freq=2, max_concepts=20, keep_top_contains=4)
    si, vectors, rhos = parse_text(INVENTED_TEXT, dim=32, config=cfg)

    print(f"Concepts extracted: {len(si)}")
    for name, spec in si.items():
        ch = spec.get("contains", {})
        ch_str = ", ".join(f"{k}:{v:.2f}" for k, v in ch.items())
        print(f"  {name:<14} w={spec['weight']:.2f}  contains={{{ch_str}}}")


def test_cooccurrence_asymmetry():
    banner("TEST 4: Asymmetry property — P(B|A) != P(A|B)")

    # Asymmetric containment is a core FVSC invariant:
    # weight(A contains B) = cooccur(A,B) / freq(A)
    # weight(B contains A) = cooccur(A,B) / freq(B)
    # These differ when freq(A) != freq(B) — which is almost always.
    cfg = ParseConfig(
        window=4, min_freq=2, max_concepts=30,
        stopwords=DEFAULT_STOPWORDS_RU_EN, keep_top_contains=6,
    )
    si, vectors, rhos = parse_text(RU_TEXT, dim=64, config=cfg)

    asymmetric_pairs = []
    names = list(si.keys())
    for i, a in enumerate(names):
        for b in names[i+1:]:
            w_ab = si[a].get("contains", {}).get(b, 0.0)
            w_ba = si[b].get("contains", {}).get(a, 0.0)
            if w_ab > 0 or w_ba > 0:
                asymmetric_pairs.append((a, b, w_ab, w_ba))

    print(f"Asymmetric pairs found: {len(asymmetric_pairs)}")
    for a, b, w_ab, w_ba in asymmetric_pairs[:6]:
        sym = "=" if abs(w_ab - w_ba) < 1e-6 else "!="
        print(f"  {a}→{b}: {w_ab:.3f}  {sym}  {b}→{a}: {w_ba:.3f}")

    symmetric = sum(1 for _, _, w_ab, w_ba in asymmetric_pairs if abs(w_ab - w_ba) < 1e-6)
    print(f"\n  Truly symmetric (freq equal): {symmetric}/{len(asymmetric_pairs)}")
    print("  Non-commutative structure confirmed." if symmetric < len(asymmetric_pairs) else "  WARNING: all pairs symmetric")



def test_density_matrix_properties():
    banner("TEST 5: Density-matrix properties from raw text")
    cfg = ParseConfig(
        window=4, min_freq=2, max_concepts=20,
        stopwords=DEFAULT_STOPWORDS_RU_EN, keep_top_contains=5,
    )
    si, vectors, rhos = parse_text(RU_TEXT, dim=64, config=cfg)
    if not rhos:
        print("(no concepts extracted — skipping)")
        return

    # Top-3 concepts by ρ trace (most "massive")
    by_mass = sorted(rhos.items(), key=lambda kv: -np.trace(kv[1]))[:3]
    print("Top-3 by trace (concept mass):")
    for name, rho in by_mass:
        print(f"  {name:<16} trace={np.trace(rho):.3f}  S(ρ)={von_neumann_entropy(rho):.3f}")

    # Pairwise containment across top concepts (asymmetric)
    names = [n for n, _ in by_mass]
    print("\nContainment matrix (rows contain columns):")
    print("           " + "  ".join(f"{n[:8]:>8}" for n in names))
    for a in names:
        row = [f"{containment(rhos[a], rhos[b]):>8.3f}" for b in names]
        print(f"  {a[:10]:<10} " + "  ".join(row))


def main():
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + "  Raw-text → FVSC density matrices (language-agnostic)".center(68) + "║")
    print("╚" + "=" * 68 + "╝")

    test_russian_raw_text()
    test_english_raw_text()
    test_invented_language()
    test_cooccurrence_asymmetry()
    test_density_matrix_properties()

    print("\n" + "=" * 70)
    print("DONE — pipeline works end-to-end with no spaCy, no language model.")
    print("=" * 70)


if __name__ == "__main__":
    main()
