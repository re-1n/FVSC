"""
semantic_chat.py — Interactive chat about the semantic map.

Loads vault -> SemanticSpace (with disk cache), feeds top-N concepts +
relations as text context to a local LLM (Ollama by default), and runs
a REPL where you can ask questions about the map.

Usage:
    python -m core.semantic_chat
    python -m core.semantic_chat --model qwen2.5:14b-instruct-q4_K_M
    python -m core.semantic_chat --rebuild        # force re-ingest
    python -m core.semantic_chat --top 80

Commands inside the REPL:
    /quit            exit
    /reload          rebuild space from vault (ignore cache)
    /top N           print top-N concepts by weight
    /context         dump the context sent to the LLM
    /model NAME      switch Ollama model (must already be pulled)
    /help            show commands
"""
from __future__ import annotations

import argparse
import pickle
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from .density_core import SemanticSpace
from .text_parser_agnostic import text_to_semantic_input, ParseConfig
from .thesaurus_prior import ThesaurusPrior
from .exocortex_ingest import _RU_STOPWORDS
from .vault_ingest import collect_vault, _TG_STRUCTURAL
from .llm import OllamaClient, ChatMessage
from .llm.map_context import SYSTEM_PROMPT, build_full_prompt_context


DEFAULT_VAULT = Path(r"C:\Users\daur1\Desktop\экзокортекс для fvsc map\Rein")
DEFAULT_CONCEPTNET = Path(r"C:\Users\daur1\Desktop\FVSC\data\conceptnet_ru.json")
CACHE_NAME = "_fvsc_cache.pkl"


# ───── build / cache ─────

def _vault_mtime(vault: Path) -> float:
    """Latest mtime of any .md in vault (rough cache validity check)."""
    latest = 0.0
    for p in vault.rglob("*.md"):
        if any(seg in {".obsidian", ".trash", "_fvsc_concepts"} for seg in p.parts):
            continue
        try:
            m = p.stat().st_mtime
            if m > latest:
                latest = m
        except OSError:
            pass
    return latest


def build_space(vault: Path, conceptnet: Path, dim: int = 64):
    print(f"[build] walking {vault}…")
    t0 = time.perf_counter()
    corpus, n_files, _ = collect_vault(vault)
    print(f"[build] {n_files} files, {len(corpus):,} chars  ({time.perf_counter()-t0:.1f}s)")

    prior = None
    if conceptnet.exists():
        prior = ThesaurusPrior.from_conceptnet(str(conceptnet))
        print(f"[build] thesaurus prior: {len(prior):,} pairs")

    cfg = ParseConfig(
        window=4, min_freq=5, max_concepts=1200, min_token_len=3,
        stopwords=_RU_STOPWORDS | {"является", "содержит"} | _TG_STRUCTURAL,
        thesaurus_prior=prior, prior_known_bonus=1.5,
    )
    t0 = time.perf_counter()
    si = text_to_semantic_input(corpus, config=cfg)
    print(f"[build] semantic_input: {len(si)} concepts ({time.perf_counter()-t0:.1f}s)")

    space = SemanticSpace(dim=dim)
    t0 = time.perf_counter()
    space.load_from_semantic_input(si, source_text="[vault]")
    print(f"[build] materialized ({time.perf_counter()-t0:.1f}s)")

    t0 = time.perf_counter()
    space.recursive_deepen(iterations=3, alpha=0.7)
    print(f"[build] recursive_deepen ({time.perf_counter()-t0:.1f}s)")

    return space, si, n_files, len(corpus)


def load_or_build(vault: Path, conceptnet: Path, force_rebuild: bool = False):
    cache_path = vault / CACHE_NAME
    if not force_rebuild and cache_path.exists():
        cache_mtime = cache_path.stat().st_mtime
        vault_mtime = _vault_mtime(vault)
        if cache_mtime > vault_mtime:
            print(f"[cache] loading {cache_path.name}…")
            try:
                with open(cache_path, "rb") as f:
                    blob = pickle.load(f)
                return blob["space"], blob["si"], blob["n_files"], blob["corpus_chars"]
            except Exception as e:
                print(f"[cache] failed ({type(e).__name__}: {e}); rebuilding")
        else:
            print("[cache] vault newer than cache; rebuilding")

    space, si, n_files, corpus_chars = build_space(vault, conceptnet)
    try:
        with open(cache_path, "wb") as f:
            pickle.dump(
                {"space": space, "si": si, "n_files": n_files, "corpus_chars": corpus_chars},
                f, protocol=pickle.HIGHEST_PROTOCOL,
            )
        print(f"[cache] saved {cache_path}")
    except Exception as e:
        print(f"[cache] save failed: {e}")
    return space, si, n_files, corpus_chars


# ───── REPL ─────

HELP = """
Commands:
  /quit  /exit       exit
  /reload            rebuild space from vault (ignore cache)
  /top N             print top-N concepts
  /context           print the context block sent to the model
  /model NAME        switch Ollama model
  /help              show this
Anything else is sent to the model as a question about your map.
"""


def cmd_top(space, si, n: int):
    skip = {"является", "содержит", "[self]"}
    ranked = sorted(
        [(t, v["weight"]) for t, v in si.items() if t not in skip],
        key=lambda x: -x[1],
    )[:n]
    for i, (term, w) in enumerate(ranked, 1):
        poly = space.query_polysemy(term)
        facets = len(space.query_facets(term))
        print(f"  {i:3d}. {term:25s}  w={w:.3f}  H={poly:.3f}  facets={facets}")


def repl(space, si, llm: OllamaClient, top_n: int):
    context = build_full_prompt_context(space, si, top_n=top_n)
    history: list[ChatMessage] = [
        ChatMessage("system", SYSTEM_PROMPT),
        ChatMessage("system", f"Контекст карты:\n\n{context}"),
    ]

    print()
    print(f"Model: {llm.model}   |   context: top-{top_n} concepts   |   /help for commands")
    print()

    while True:
        try:
            user = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not user:
            continue

        if user in ("/quit", "/exit"):
            return
        if user == "/help":
            print(HELP)
            continue
        if user == "/context":
            print(context)
            continue
        if user.startswith("/top"):
            parts = user.split()
            n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
            cmd_top(space, si, n)
            continue
        if user.startswith("/model"):
            parts = user.split(maxsplit=1)
            if len(parts) == 2:
                llm.model = parts[1].strip()
                print(f"[model] -> {llm.model}")
            else:
                print(f"current: {llm.model}")
            continue
        if user == "/reload":
            return "reload"

        # Send as question
        history.append(ChatMessage("user", user))
        try:
            reply = llm.chat(history, stream=True)
        except RuntimeError as e:
            print(f"[error] {e}")
            history.pop()
            continue
        history.append(ChatMessage("assistant", reply))


# ───── main ─────

def main():
    ap = argparse.ArgumentParser(description="Chat about your FVSC semantic map.")
    ap.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    ap.add_argument("--conceptnet", type=Path, default=DEFAULT_CONCEPTNET)
    ap.add_argument("--model", default="qwen2.5:7b-instruct-q4_K_M")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--top", type=int, default=50, help="top-N concepts in LLM context")
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--temperature", type=float, default=0.4)
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args()

    llm = OllamaClient(
        model=args.model, host=args.host,
        temperature=args.temperature, num_ctx=args.num_ctx,
    )
    if not llm.ping():
        print(f"[error] Ollama daemon not responding at {args.host}.")
        print("Start it (Windows: launch Ollama app) or `ollama serve` and try again.")
        sys.exit(1)

    local = llm.list_local_models()
    if args.model not in local:
        print(f"[warn] model '{args.model}' is not pulled.")
        print(f"       local models: {local or '(none)'}")
        print(f"       run:  ollama pull {args.model}")
        # don't exit — user may pull in another terminal and retry

    rebuild = args.rebuild
    while True:
        space, si, n_files, corpus_chars = load_or_build(
            args.vault, args.conceptnet, force_rebuild=rebuild,
        )
        print(f"[ready] {len(space.concepts)} concepts in space, {n_files} vault files indexed")
        result = repl(space, si, llm, top_n=args.top)
        if result == "reload":
            rebuild = True
            continue
        break


if __name__ == "__main__":
    main()
