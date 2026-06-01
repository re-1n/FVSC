"""
vault_ingest.py — Walk an Obsidian vault, parse all .md files, run full FVSC
pipeline with thesaurus prior enabled, and visualize.

Pipeline:
    walk vault → strip frontmatter + Markdown → clean (URLs/code/Latin)
      → text_to_semantic_input(thesaurus_prior=ConceptNet RU)
      → SemanticSpace.load_from_semantic_input + recursive_deepen
      → render HTML map
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import List, Tuple

from .density_core import SemanticSpace
from .text_parser_agnostic import text_to_semantic_input, ParseConfig
from .thesaurus_prior import ThesaurusPrior
from .exocortex_ingest import _clean_for_fvsc, _RU_STOPWORDS
from .visualize_space import render_html


# ───── Markdown stripping ─────

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")  # [[target|alias]] → target
_MDLINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")  # [text](url) → text
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^\)]+\)")
_OBSIDIAN_EMBED_RE = re.compile(r"!\[\[[^\]]+\]\]")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_TABLE_PIPE_RE = re.compile(r"[\|`*_~]")
_HR_RE = re.compile(r"^[-=*_]{3,}\s*$", re.MULTILINE)


def strip_markdown(text: str) -> str:
    """Strip YAML frontmatter, headings, code, links, images, HTML, table markers."""
    text = _FRONTMATTER_RE.sub("", text)
    text = _IMAGE_RE.sub(" ", text)
    text = _OBSIDIAN_EMBED_RE.sub(" ", text)
    text = _WIKILINK_RE.sub(r"\1", text)
    text = _MDLINK_RE.sub(r"\1", text)
    text = _HEADING_RE.sub("", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _HR_RE.sub("", text)
    text = _TABLE_PIPE_RE.sub(" ", text)
    return text


# ───── Vault walker ─────

DEFAULT_EXCLUDE = {".obsidian", ".trash", "вложения", "attachments"}

# TG export structural markers that leak into vault parsing through the
# auto-generated тг-каналы/ folder. They are not personal semantics — they're
# Telegram UI labels for media types and reply structure.
_TG_STRUCTURAL = frozenset({
    "ред", "фото", "видео", "голосовое", "видеосообщение",
    "наклейка", "стикер", "анимация", "файл", "опрос",
    "переслано", "сообщение", "ответ", "медиа",
    "ссылка", "контакт", "геолокация",
})

# Digit-only tokens (years, dates from TG headings like "## 2024-11-01")
_DIGITS_TOKEN_RE = re.compile(r"^\d+$")


def collect_vault(
    vault_dir: Path,
    exclude_dirs: set = None,
    include_subpath: list = None,
) -> Tuple[str, int, dict]:
    """Walk vault, concatenate all .md content (after Markdown stripping).

    Returns (corpus_text, file_count, per_folder_stats).
    """
    exclude = exclude_dirs if exclude_dirs is not None else DEFAULT_EXCLUDE
    files = []
    for p in vault_dir.rglob("*.md"):
        if any(seg in exclude for seg in p.parts):
            continue
        files.append(p)

    files.sort()
    chunks = []
    per_folder = {}
    for path in files:
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                raw = path.read_text(encoding="cp1251")
            except Exception:
                continue
        stripped = strip_markdown(raw)
        cleaned = _clean_for_fvsc(stripped)
        if len(cleaned) < 20:
            continue
        chunks.append(cleaned)
        # Track top-level folder for stats
        rel = path.relative_to(vault_dir)
        top = rel.parts[0] if len(rel.parts) > 1 else "_root"
        per_folder.setdefault(top, {"files": 0, "chars": 0})
        per_folder[top]["files"] += 1
        per_folder[top]["chars"] += len(cleaned)

    corpus = "\n\n".join(chunks)
    return corpus, len(chunks), per_folder


# ───── Main pipeline ─────

def main():
    vault_dir = Path("/mnt/c/Users/daur1/Desktop/экзокортекс для fvsc map/Rein")
    conceptnet_path = Path("/mnt/c/Users/daur1/Desktop/FVSC/data/conceptnet_ru.json")

    print(f"Vault: {vault_dir}")
    print(f"Walking files…")
    t0 = time.time()
    corpus, n_files, per_folder = collect_vault(vault_dir)
    t1 = time.time()
    print(f"  collected {n_files} files, {len(corpus):,} chars in {t1-t0:.1f}s")
    print()
    print("Per top-level folder:")
    for folder, stats in sorted(per_folder.items(), key=lambda x: -x[1]["chars"]):
        print(f"  {folder:30s}  files={stats['files']:4d}  chars={stats['chars']:>10,}")
    print()

    print(f"Loading ConceptNet thesaurus prior…")
    t0 = time.time()
    prior = ThesaurusPrior.from_conceptnet(str(conceptnet_path))
    t1 = time.time()
    print(f"  loaded {len(prior):,} pairs in {t1-t0:.1f}s")
    print()

    _synthetic = {"является", "содержит"}
    cfg = ParseConfig(
        window=4,
        min_freq=5,           # higher threshold for big vault corpus
        max_concepts=1200,
        min_token_len=3,
        stopwords=_RU_STOPWORDS | _synthetic | _TG_STRUCTURAL,
        thesaurus_prior=prior,
        prior_known_bonus=1.5,  # stronger than default 1.2 — test the effect
    )

    print("Building semantic_input…")
    t0 = time.time()
    si = text_to_semantic_input(corpus, config=cfg)
    t1 = time.time()
    print(f"  {len(si)} concepts extracted in {t1-t0:.1f}s")

    # Count how many pairs got boosted by thesaurus
    boosted = 0
    total_pairs = 0
    for concept, spec in si.items():
        for child in spec.get("contains", {}):
            total_pairs += 1
            if prior.score(concept, child) > 0:
                boosted += 1
    pct = 100 * boosted / total_pairs if total_pairs else 0
    print(f"  thesaurus confirmed: {boosted}/{total_pairs} pairs ({pct:.1f}%)")
    print()

    print("Materializing into SemanticSpace…")
    t0 = time.time()
    space = SemanticSpace(dim=64)
    space.load_from_semantic_input(si, source_text="[vault]")
    t1 = time.time()
    print(f"  {len(space.concepts)} concepts loaded in {t1-t0:.1f}s")

    print("Recursive deepening (iterations=3, alpha=0.7)…")
    t0 = time.time()
    space.recursive_deepen(iterations=3, alpha=0.7)
    t1 = time.time()
    print(f"  done in {t1-t0:.1f}s")
    print()

    # Quick top-15 diagnostic
    skip = {"является", "содержит", "[self]"}
    ranked = sorted(
        [(c, v["weight"]) for c, v in si.items() if c not in skip],
        key=lambda x: -x[1],
    )
    print("TOP-15 концептов (vault + thesaurus prior):")
    for term, w in ranked[:15]:
        poly = space.query_polysemy(term)
        n_facets = len(space.query_facets(term))
        in_thes = "✓" if prior.covers(term) else " "
        print(f"  [{in_thes}] {term:25s}  w={w:.3f}  poly={poly:.3f}  facets={n_facets}")
    print()

    # Visualize
    out_path = Path("/mnt/c/Users/daur1/Desktop/FVSC/core/vault_map.html")
    data = render_html(
        space, si, out_path,
        title="Rein vault — карта смыслов с тезаурусом",
        subtitle=(
            f"{n_files} файлов · {len(corpus):,} символов · "
            f"top-100 · тезаурус-приор bonus={cfg.prior_known_bonus} "
            f"({boosted}/{total_pairs} пар подтверждены)"
        ),
        top_n=100,
        edge_threshold=0.50,
        max_edges_per_node=6,
    )
    print(f"  nodes={len(data['nodes'])}  edges={len(data['edges'])}")
    print(f"[saved] {out_path}")

    # Copy to vault for easy access
    vault_out = vault_dir / "vault_map.html"
    vault_out.write_bytes(out_path.read_bytes())
    print(f"[saved] {vault_out}")

    return space, si


if __name__ == "__main__":
    main()
