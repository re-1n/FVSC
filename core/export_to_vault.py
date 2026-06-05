"""
export_to_vault.py — Export a SemanticSpace as one .md note per concept
into an Obsidian vault subfolder. Wikilinks make the native Obsidian graph
render the semantic network.

Layout:
  <vault>/_fvsc_concepts/
    кот.md
    животное.md
    ...
    _index.md       # entry point with top concepts
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

from .density_core import SemanticSpace


_UNSAFE_FS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_filename(term: str) -> str:
    """Obsidian/Windows-safe filename. Term itself is kept as-is in frontmatter."""
    safe = _UNSAFE_FS.sub("_", term).strip()
    if not safe:
        safe = "_"
    if len(safe) > 80:
        safe = safe[:80]
    return safe


def _escape_yaml(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _render_concept_note(
    space: SemanticSpace,
    term: str,
    weight: float,
    top_contains: int = 12,
    top_contained_in: int = 12,
    top_judgments: int = 20,
) -> str:
    concept = space.concepts[term]
    poly = space.query_polysemy(term)
    facets = space.query_facets(term)
    contains = space.query_contains(term, top_k=top_contains)
    contained_in = space.query_contained_in(term, top_k=top_contained_in)

    n_active = sum(1 for c in concept.components if not c.archived)

    lines = []
    lines.append("---")
    lines.append(f'term: "{_escape_yaml(term)}"')
    lines.append(f"weight: {weight:.4f}")
    lines.append(f"polysemy: {poly:.4f}")
    lines.append(f"facets: {len(facets)}")
    lines.append(f"components: {n_active}")
    lines.append("tags: [fvsc/concept]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {term}")
    lines.append("")
    lines.append("## Метрики")
    lines.append(f"- **Частота (w):** {weight:.3f}")
    lines.append(f"- **Полисемия (H):** {poly:.3f}")
    lines.append(f"- **Фасеты:** {len(facets)}")
    lines.append(f"- **Компонент:** {n_active}")
    lines.append("")

    if contains:
        lines.append("## Содержит →")
        for other, score in contains:
            if score <= 0:
                continue
            lines.append(f"- [[{_safe_filename(other)}|{other}]]  —  {score:.2f}")
        lines.append("")

    if contained_in:
        lines.append("## ← Содержится в")
        for other, score in contained_in:
            if score <= 0:
                continue
            lines.append(f"- [[{_safe_filename(other)}|{other}]]  —  {score:.2f}")
        lines.append("")

    # Show a sample of underlying judgments (provenance)
    judgments = [c.judgment for c in concept.components if not c.archived]
    if judgments:
        lines.append("## Суждения (выборка)")
        seen = set()
        shown = 0
        for j in judgments:
            key = (j.subject, j.verb, j.object)
            if key in seen:
                continue
            seen.add(key)
            shown += 1
            if shown > top_judgments:
                break
            s, v, o = j.subject or "?", j.verb or "?", j.object or "?"
            lines.append(f"- {s} — *{v}* — {o}")
        lines.append("")

    lines.append("---")
    lines.append("*Сгенерировано FVSC. Не редактируй вручную — будет перезаписано.*")
    return "\n".join(lines)


def _render_index(
    ranked: list[tuple[str, float]],
    space: SemanticSpace,
    n_files: int,
    corpus_chars: int,
    top_n_in_index: int = 50,
) -> str:
    lines = []
    lines.append("---")
    lines.append("tags: [fvsc/index]")
    lines.append("---")
    lines.append("")
    lines.append("# FVSC — карта смыслов")
    lines.append("")
    lines.append(
        f"Извлечено из {n_files} файлов vault'а ({corpus_chars:,} символов). "
        f"Всего концептов в пространстве: **{len(space.concepts)}**."
    )
    lines.append("")
    lines.append("## Топ концептов по частоте")
    lines.append("")
    lines.append("| # | Концепт | w | H | фасеты |")
    lines.append("|---|---------|---|---|--------|")
    for i, (term, w) in enumerate(ranked[:top_n_in_index], 1):
        poly = space.query_polysemy(term)
        nf = len(space.query_facets(term))
        link = f"[[{_safe_filename(term)}|{term}]]"
        lines.append(f"| {i} | {link} | {w:.3f} | {poly:.3f} | {nf} |")
    lines.append("")
    lines.append("## Использование")
    lines.append(
        "- Открой граф-вью Obsidian (Ctrl+G) и отфильтруй по тегу `#fvsc/concept` — "
        "увидишь семантическую сеть."
    )
    lines.append(
        "- В каждой заметке: метрики, что концепт *содержит* и в чём *содержится*, "
        "и образцы суждений-источников."
    )
    lines.append(
        "- HTML-карта (если построена): `vault_map.html` в корне vault'а."
    )
    lines.append("")
    lines.append("---")
    lines.append("*Сгенерировано FVSC.*")
    return "\n".join(lines)


def export_space_to_vault(
    space: SemanticSpace,
    si: Dict,
    vault_dir: Path,
    folder_name: str = "_fvsc_concepts",
    top_n: int = 150,
    n_files: int = 0,
    corpus_chars: int = 0,
    clean_first: bool = True,
) -> dict:
    """Write one .md per top-N concept into <vault>/<folder_name>/.

    Returns stats dict.
    """
    out_dir = vault_dir / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)

    if clean_first:
        for old in out_dir.glob("*.md"):
            old.unlink()

    skip = {"является", "содержит", "[self]"}
    ranked = sorted(
        [(t, v["weight"]) for t, v in si.items() if t not in skip],
        key=lambda x: -x[1],
    )

    # Filter to queryable concepts (have enough components to produce meaningful queries)
    queryable_terms = {t for t, _ in space._queryable_concepts()}
    ranked = [(t, w) for t, w in ranked if t in queryable_terms][:top_n]

    written = 0
    for term, w in ranked:
        try:
            note = _render_concept_note(space, term, w)
            path = out_dir / f"{_safe_filename(term)}.md"
            path.write_text(note, encoding="utf-8")
            written += 1
        except Exception as e:
            print(f"  [skip] {term}: {type(e).__name__}: {e}")

    # Index file
    index_path = out_dir / "_index.md"
    index_path.write_text(
        _render_index(ranked, space, n_files, corpus_chars, top_n_in_index=min(80, top_n)),
        encoding="utf-8",
    )

    return {
        "written": written,
        "folder": str(out_dir),
        "index": str(index_path),
        "top_n_requested": top_n,
    }
