"""
viz_router.py — /viz endpoints: HTML page + SSE chat stream.

Loads the vault SemanticSpace from disk cache on first access. The HTML page
embeds the graph data (nodes/edges JSON) and connects to /viz/ask for chat.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from core.density_core import SemanticSpace
from core.visualize_space import build_graph_data
from core.llm import OllamaClient
from core.text_parser_agnostic import text_to_semantic_input, ParseConfig
from core.thesaurus_prior import ThesaurusPrior
from core.exocortex_ingest import _RU_STOPWORDS
from core.vault_ingest import strip_markdown, _TG_STRUCTURAL
from core.exocortex_ingest import _clean_for_fvsc
from .viz_session import (
    VizConfig,
    stream_response,
    stream_stub,
)


router = APIRouter(prefix="/viz", tags=["viz"])


# ───── lazy-loaded vault space ─────

DEFAULT_VAULT = Path(r"C:\Users\daur1\Desktop\экзокортекс для fvsc map\Rein")
CACHE_NAME = "_fvsc_cache.pkl"

_state = {
    "space": None,
    "si": None,
    "vault_path": DEFAULT_VAULT,
    "config": VizConfig(),
    "parse_config": None,    # lazy-built ParseConfig matching vault_sync
    "live_dirty_count": 0,   # number of ingests since last cache save
    "live_save_every": 5,    # auto-save threshold
}


def _load_vault_cache(vault_dir: Path):
    cache_path = vault_dir / CACHE_NAME
    if not cache_path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Vault cache not found at {cache_path}. "
                f"Run `python -m core.vault_sync` first to build it."
            ),
        )
    with open(cache_path, "rb") as f:
        blob = pickle.load(f)
    _state["space"] = blob["space"]
    _state["si"] = blob["si"]
    return blob


def _get_space():
    if _state["space"] is None:
        _load_vault_cache(_state["vault_path"])
    return _state["space"], _state["si"]


def configure(vault_path: Optional[Path] = None, config: Optional[VizConfig] = None):
    """Programmatic override for tests / alternate vaults."""
    if vault_path:
        _state["vault_path"] = vault_path
        _state["space"] = None
        _state["si"] = None
    if config:
        _state["config"] = config


# ───── HTML page ─────

def _viz_template_path() -> Path:
    return Path(__file__).parent / "viz_template.html"


@router.get("", response_class=HTMLResponse)
async def viz_page(top_n: int = 100):
    space, si = _get_space()
    data = build_graph_data(
        space, si,
        top_n=top_n,
        edge_threshold=0.35,
        max_edges_per_node=10,
    )
    template = _viz_template_path().read_text(encoding="utf-8")
    n_concepts = len(space.concepts)
    subtitle = f"vault · {n_concepts} концептов · top-{top_n}"
    html = (
        template
        .replace("__TITLE__", "Антураж — карта смыслов")
        .replace("__SUBTITLE__", subtitle)
        .replace("__GRAPH_DATA__", json.dumps(data, ensure_ascii=False))
        .replace("__MODEL__", _state["config"].model)
        .replace("__VAULT_NAME__", _state["vault_path"].name)
    )
    return HTMLResponse(html)


# ───── chat stream ─────

class AskRequest(BaseModel):
    messages: list[dict]   # [{role, content}]
    stub: bool = False


@router.post("/ask")
async def viz_ask(req: AskRequest):
    space, si = _get_space()
    cfg = _state["config"]

    if req.stub:
        gen = stream_stub(req.messages)
    else:
        llm = OllamaClient(
            model=cfg.model, host=cfg.host,
            temperature=cfg.temperature, num_ctx=cfg.num_ctx,
        )
        if not llm.ping():
            raise HTTPException(503, "Ollama daemon not running")
        known_terms = set(space.concepts.keys())
        gen = stream_response(llm, space, si, req.messages, cfg, known_terms=known_terms)

    return StreamingResponse(gen, media_type="text/event-stream")


@router.get("/concepts/{term}/sources")
async def viz_concept_sources(term: str, top_k: int = 10):
    """Drill-down: which vault notes formed this concept's meaning.
    Returns top-k source paths with normalized weights, plus the vault name
    so the frontend can build obsidian://open?vault=...&file=... links.
    """
    from collections import Counter
    space, _ = _get_space()
    concept = space.concepts.get(term)
    if concept is None:
        # Strong concept not found — maybe it's in the silent pool?
        silent = getattr(space, "silent_pool", {}) or {}
        entry = silent.get(term)
        if entry:
            # Format as a sources-like response with a "silent" flag.
            total = sum(entry["sources"].values()) or 1
            srcs = sorted(entry["sources"].items(), key=lambda x: -x[1])[:top_k]
            return {
                "term": term,
                "vault_name": _state["vault_path"].name,
                "silent": True,
                "freq": entry["freq"],
                "total_components": 0,
                "sources": [
                    {"path": p, "weight": round(c / total, 4)}
                    for p, c in srcs
                ],
            }
        raise HTTPException(404, detail=f"Concept '{term}' not found")

    agg: "Counter[str]" = Counter()
    for c in concept.components:
        if c.archived:
            continue
        src = c.judgment.source_text or ""
        if not src:
            continue
        if src.startswith("[") and src.endswith("]"):
            continue
        agg[src] += float(c.weight)

    total = sum(agg.values())
    sources = [
        {"path": s, "weight": round(w / total, 4) if total else 0.0}
        for s, w in agg.most_common(top_k)
    ]
    return {
        "term": term,
        "vault_name": _state["vault_path"].name,
        "silent": False,
        "total_components": len(concept.components),
        "sources": sources,
    }


def _get_parse_config() -> ParseConfig:
    """Build (and cache) the ParseConfig matching vault_sync's defaults so
    live ingest stays compatible with the global vocabulary.
    """
    cfg = _state.get("parse_config")
    if cfg is not None:
        return cfg
    # Try to pick up the same thesaurus prior the offline pipeline uses.
    project_root = Path(__file__).resolve().parent.parent
    conceptnet_path = project_root / "data" / "conceptnet_ru.json"
    prior = None
    if conceptnet_path.exists():
        try:
            prior = ThesaurusPrior.from_conceptnet(str(conceptnet_path))
        except Exception:
            prior = None
    cfg = ParseConfig(
        window=4,
        min_freq=1,        # live mode: a single fresh utterance is allowed to count
        max_concepts=200,  # per-file cap — keeps live ingest fast
        min_token_len=3,
        stopwords=_RU_STOPWORDS | {"является", "содержит"} | _TG_STRUCTURAL,
        thesaurus_prior=prior,
        prior_known_bonus=1.5,
    )
    _state["parse_config"] = cfg
    return cfg


class FileIngestRequest(BaseModel):
    path: str                      # vault-relative posix path, e.g. "дневник/2026-06-06.md"
    action: str                    # "create" | "modify" | "delete" | "rename"
    text: Optional[str] = None     # full file text for create/modify
    old_path: Optional[str] = None # previous path for rename


@router.post("/file_ingest")
async def viz_file_ingest(req: FileIngestRequest):
    """Live vault-watch endpoint. The Obsidian plugin posts here on every
    vault change (debounced). We mutate the in-memory space incrementally
    and persist the cache every N ingests.

    Behavior:
      - delete:  purge all Judgments + silent_pool entries for this path.
      - rename:  purge old_path, then process new path as modify if text given.
      - create:  ingest fresh; add new tokens to silent_pool if below threshold.
      - modify:  purge old contributions of this file, then ingest fresh.
    """
    space, _si = _get_space()
    cfg = _get_parse_config()

    action = (req.action or "").lower()
    purged = 0
    added = 0

    if action == "delete":
        purged = space.purge_source(req.path)
    elif action == "rename":
        if req.old_path:
            purged += space.purge_source(req.old_path)
        if req.text:
            purged += space.purge_source(req.path)
            added = _ingest_text_into(space, req.path, req.text, cfg)
        # else: nothing to add — file content not provided
    elif action in ("create", "modify"):
        if req.text is None:
            raise HTTPException(400, detail=f"action={action} requires text")
        purged = space.purge_source(req.path)
        added = _ingest_text_into(space, req.path, req.text, cfg)
    else:
        raise HTTPException(400, detail=f"unknown action: {action}")

    _state["live_dirty_count"] += 1
    saved = False
    if _state["live_dirty_count"] >= _state["live_save_every"]:
        try:
            _save_cache()
            _state["live_dirty_count"] = 0
            saved = True
        except Exception as e:
            return {"path": req.path, "action": action, "added": added,
                    "purged": purged, "saved": False, "save_error": str(e)}

    return {
        "path": req.path, "action": action,
        "added": added, "purged": purged,
        "concept_count": len(space.concepts),
        "silent_count": len(getattr(space, "silent_pool", {}) or {}),
        "dirty": _state["live_dirty_count"],
        "saved": saved,
    }


def _ingest_text_into(space: SemanticSpace, path: str, raw_text: str,
                      cfg: ParseConfig) -> int:
    """Strip markdown + clean, parse, add to space. Returns Judgments added."""
    stripped = strip_markdown(raw_text)
    cleaned = _clean_for_fvsc(stripped)
    if len(cleaned) < 20:
        return 0
    si_local = text_to_semantic_input(cleaned, config=cfg)
    if not si_local:
        return 0
    # Silent additions: per-file tokens that would normally fall below the
    # global min_freq (here we let everything through, but we still log a
    # silent entry for tokens that don't reach repeated mention).
    silent_local = {}
    for tok, spec in si_local.items():
        # weight is normalized 0..1 — treat as a freq proxy; if very low,
        # also write to silent_pool so search can find it later.
        w = float(spec.get("weight", 0))
        if w < 0.25:
            silent_local[tok] = {"freq": 1, "sources": {path: 1}}
    return space.ingest_one_file(path, si_local, silent_local=silent_local)


def _save_cache():
    """Persist the current space + si to the vault cache file."""
    vault = _state["vault_path"]
    cache_path = vault / CACHE_NAME
    blob = {
        "space": _state["space"],
        "si": _state["si"],
        "n_files": None,
        "corpus_chars": None,
    }
    with open(cache_path, "wb") as f:
        pickle.dump(blob, f, protocol=pickle.HIGHEST_PROTOCOL)


@router.post("/save_cache")
async def viz_save_cache():
    """Force-save the cache (used by the plugin on unload to flush dirty
    live-ingested changes without waiting for the auto-save threshold).
    """
    if _state["space"] is None:
        return {"saved": False, "reason": "no space loaded"}
    try:
        _save_cache()
        _state["live_dirty_count"] = 0
        return {"saved": True, "path": str(_state["vault_path"] / CACHE_NAME)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@router.get("/silent")
async def viz_silent(query: str = "", min_freq: int = 1, max_freq: int = 4, limit: int = 50):
    """Browse the silent_pool: tokens that didn't reach min_freq for the strong
    concept map, but were uttered at least once.

    Args:
        query: optional substring filter on the token (case-insensitive).
        min_freq, max_freq: bounds on global frequency. Default 1..4 (hapax + low).
        limit: max entries to return, sorted by freq descending.
    """
    space, _ = _get_space()
    silent = getattr(space, "silent_pool", {}) or {}
    q = query.strip().lower()

    rows = []
    for tok, e in silent.items():
        f = e["freq"]
        if f < min_freq or f > max_freq:
            continue
        if q and q not in tok:
            continue
        rows.append((tok, f, len(e["sources"])))
    rows.sort(key=lambda r: (-r[1], r[0]))
    rows = rows[:limit]
    return {
        "vault_name": _state["vault_path"].name,
        "total_silent": len(silent),
        "results": [
            {"term": t, "freq": f, "n_sources": n}
            for t, f, n in rows
        ],
    }


@router.get("/status")
async def viz_status():
    cfg = _state["config"]
    vault = _state["vault_path"]
    space_loaded = _state["space"] is not None
    llm = OllamaClient(model=cfg.model, host=cfg.host)
    return {
        "vault": str(vault),
        "vault_cache_exists": (vault / CACHE_NAME).exists(),
        "space_loaded": space_loaded,
        "concept_count": len(_state["space"].concepts) if space_loaded else None,
        "model": cfg.model,
        "ollama_up": llm.ping(),
        "models_available": llm.list_local_models(),
    }
