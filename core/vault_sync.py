"""
vault_sync.py — One-shot pipeline: vault -> SemanticSpace -> .md concept notes
(and optional HTML map). Use this to update the FVSC view inside the Obsidian
vault after editing notes.

Usage:
    python -m core.vault_sync                       # default vault path
    python -m core.vault_sync --vault "C:\\path\\to\\vault"
    python -m core.vault_sync --top 200 --no-html

What it does:
    1. Walks vault, strips Markdown, builds corpus.
    2. Loads ConceptNet RU thesaurus prior.
    3. Extracts semantic_input → SemanticSpace (dim=64).
    4. Recursive deepening (3 iters).
    5. Writes top-N concept notes to <vault>/_fvsc_concepts/*.md
    6. (Optional) Renders interactive HTML map to <vault>/vault_map.html
    7. Prints perf summary.
"""
from __future__ import annotations

import argparse
import pickle
import sys
import time
from pathlib import Path
from typing import Callable, Optional

# Windows console often defaults to cp1251; force UTF-8 for our prints.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from .density_core import SemanticSpace
from .text_parser_agnostic import text_to_semantic_input, ParseConfig
from .thesaurus_prior import ThesaurusPrior
from .exocortex_ingest import _RU_STOPWORDS
from .vault_ingest import collect_vault, collect_vault_per_file, _TG_STRUCTURAL
from .export_to_vault import export_space_to_vault
from .visualize_space import render_html
from .provenance import build_provenance_and_silent


DEFAULT_VAULT = Path(r"C:\Users\daur1\Desktop\экзокортекс для fvsc map\Rein")
DEFAULT_CONCEPTNET = Path(r"C:\Users\daur1\Desktop\FVSC\data\conceptnet_ru.json")
CACHE_NAME = "_fvsc_cache.pkl"


# Stage weights based on ~95s pipeline perf on a ~700-file vault (see EVOLUTION).
# Each entry: (start_percent, end_percent, default_message).
ProgressCallback = Callable[[str, float, str], None]

STAGE_WEIGHTS: dict[str, tuple[float, float, str]] = {
    "collect":    (0,   2,   "Читаю файлы vault'а"),
    "prior":      (2,   3,   "Загружаю тезаурус"),
    "parse":      (3,   6,   "Извлекаю концепты"),
    "provenance": (6,   8,   "Привязываю концепты к заметкам"),
    "materialize":(8,   45,  "Строю смысловое пространство"),
    "deepen":     (45,  55,  "Углубляю связи"),
    "export":     (55,  87,  "Сохраняю заметки концептов"),
    "render":     (87,  97,  "Рендерю карту"),
    "save":       (97,  100, "Сохраняю кэш"),
}


def _emit(cb: Optional[ProgressCallback], stage: str, percent: float, message: str) -> None:
    """Safely fire a progress callback — never let it break the pipeline."""
    if cb is None:
        return
    try:
        cb(stage, percent, message)
    except Exception:
        pass


def run(
    vault_dir: Path,
    conceptnet_path: Path,
    top_n: int = 150,
    render_html_map: bool = True,
    dim: int = 64,
    progress_callback: Optional[ProgressCallback] = None,
):
    perf = {}
    cb = progress_callback

    def _start(stage: str) -> None:
        s, _e, msg = STAGE_WEIGHTS[stage]
        _emit(cb, stage, s, f"Стадия: {msg}")

    def _end(stage: str, elapsed: float) -> None:
        _s, e, msg = STAGE_WEIGHTS[stage]
        _emit(cb, stage, e, f"Готово: {msg} ({elapsed:.1f}с)")

    print(f"Vault: {vault_dir}")
    if not vault_dir.exists():
        raise SystemExit(f"Vault not found: {vault_dir}")

    _start("collect")
    t0 = time.perf_counter()
    files_by_path, per_folder = collect_vault_per_file(vault_dir)
    n_files = len(files_by_path)
    corpus = "\n\n".join(files_by_path.values())
    perf["collect_vault"] = time.perf_counter() - t0
    print(f"  collected {n_files} files, {len(corpus):,} chars in {perf['collect_vault']:.1f}s")
    _end("collect", perf["collect_vault"])

    _start("prior")
    t0 = time.perf_counter()
    prior = None
    if conceptnet_path.exists():
        prior = ThesaurusPrior.from_conceptnet(str(conceptnet_path))
        perf["load_prior"] = time.perf_counter() - t0
        print(f"  loaded thesaurus prior ({len(prior):,} pairs) in {perf['load_prior']:.1f}s")
    else:
        perf["load_prior"] = time.perf_counter() - t0
        print(f"  [warn] ConceptNet not found at {conceptnet_path} — running without prior")
    _end("prior", perf["load_prior"])

    cfg = ParseConfig(
        window=4,
        min_freq=5,
        max_concepts=1200,
        min_token_len=3,
        stopwords=_RU_STOPWORDS | {"является", "содержит"} | _TG_STRUCTURAL,
        thesaurus_prior=prior,
        prior_known_bonus=1.5,
    )

    _start("parse")
    t0 = time.perf_counter()
    si = text_to_semantic_input(corpus, config=cfg)
    perf["parse"] = time.perf_counter() - t0
    print(f"  semantic_input: {len(si)} concepts in {perf['parse']:.1f}s")
    _end("parse", perf["parse"])

    _start("provenance")
    t0 = time.perf_counter()
    provenance, silent_pool = build_provenance_and_silent(si, files_by_path, cfg)
    perf["provenance"] = time.perf_counter() - t0
    n_files_attributed = sum(1 for v in provenance.values() if any(
        src != "[vault]" for src in v.get("self", {})
    ))
    silent_hapax = sum(1 for v in silent_pool.values() if v["freq"] == 1)
    print(
        f"  provenance: {n_files_attributed}/{len(provenance)} concepts attributed | "
        f"silent_pool: {len(silent_pool):,} tokens ({silent_hapax:,} said once) "
        f"in {perf['provenance']:.1f}s"
    )
    _end("provenance", perf["provenance"])

    _start("materialize")
    t0 = time.perf_counter()
    space = SemanticSpace(dim=dim)
    space.load_from_semantic_input(si, source_text="[vault]", provenance=provenance)
    space.silent_pool = silent_pool
    perf["materialize"] = time.perf_counter() - t0
    print(f"  materialized {len(space.concepts)} concepts in {perf['materialize']:.1f}s")
    _end("materialize", perf["materialize"])

    _start("deepen")
    t0 = time.perf_counter()
    space.recursive_deepen(iterations=3, alpha=0.7)
    perf["recursive_deepen"] = time.perf_counter() - t0
    print(f"  recursive_deepen (3 iters) in {perf['recursive_deepen']:.1f}s")
    _end("deepen", perf["recursive_deepen"])

    print()
    print(f"Exporting top-{top_n} concepts -> vault...")
    _start("export")
    t0 = time.perf_counter()
    stats = export_space_to_vault(
        space, si, vault_dir,
        folder_name="_fvsc_concepts",
        top_n=top_n,
        n_files=n_files,
        corpus_chars=len(corpus),
    )
    perf["export"] = time.perf_counter() - t0
    print(f"  wrote {stats['written']} notes in {perf['export']:.1f}s")
    print(f"  folder: {stats['folder']}")
    print(f"  index:  {stats['index']}")
    _end("export", perf["export"])

    if render_html_map:
        print()
        print("Rendering HTML map…")
        _start("render")
        t0 = time.perf_counter()
        out_html = vault_dir / "vault_map.html"
        data = render_html(
            space, si, out_html,
            title="Rein vault — карта смыслов",
            subtitle=f"{n_files} файлов · {len(corpus):,} символов · top-100 концептов",
            top_n=100,
            edge_threshold=0.50,
            max_edges_per_node=6,
        )
        perf["render_html"] = time.perf_counter() - t0
        print(f"  nodes={len(data['nodes'])} edges={len(data['edges'])} in {perf['render_html']:.1f}s")
        print(f"  saved: {out_html}")
        _end("render", perf["render_html"])

    # ── persist the cache so /viz can lazy-load it on first request
    print()
    print("Saving cache…")
    _start("save")
    t0 = time.perf_counter()
    cache_path = vault_dir / CACHE_NAME
    try:
        with open(cache_path, "wb") as f:
            pickle.dump(
                {"space": space, "si": si, "n_files": n_files, "corpus_chars": len(corpus)},
                f, protocol=pickle.HIGHEST_PROTOCOL,
            )
        perf["save_cache"] = time.perf_counter() - t0
        print(f"  saved {cache_path.name} ({cache_path.stat().st_size / 1024 / 1024:.1f} MB) in {perf['save_cache']:.1f}s")
    except Exception as e:
        perf["save_cache"] = time.perf_counter() - t0
        print(f"  [error] cache save failed: {e}")
    _end("save", perf["save_cache"])

    print()
    print("─── perf summary ───")
    total = sum(perf.values())
    for k, v in perf.items():
        pct = 100 * v / total if total else 0
        print(f"  {k:20s} {v:7.2f}s  ({pct:4.1f}%)")
    print(f"  {'TOTAL':20s} {total:7.2f}s")

    return space, si, stats


def main():
    ap = argparse.ArgumentParser(description="Sync Obsidian vault into FVSC concept notes.")
    ap.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    ap.add_argument("--conceptnet", type=Path, default=DEFAULT_CONCEPTNET)
    ap.add_argument("--top", type=int, default=150, help="Top N concepts to export as notes")
    ap.add_argument("--no-html", action="store_true", help="Skip HTML map rendering")
    ap.add_argument("--dim", type=int, default=64)
    args = ap.parse_args()

    run(
        vault_dir=args.vault,
        conceptnet_path=args.conceptnet,
        top_n=args.top,
        render_html_map=not args.no_html,
        dim=args.dim,
    )


if __name__ == "__main__":
    main()
