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
from .viz_session import (
    VizConfig,
    stream_response,
    stream_stub,
)


router = APIRouter(prefix="/viz", tags=["viz"])


# ───── lazy-loaded vault space ─────

DEFAULT_VAULT = Path(r"C:\Users\daur1\Desktop\экзокортекс для fvsc map\Rein")
CACHE_NAME = "_fvsc_cache.pkl"

_state = {"space": None, "si": None, "vault_path": DEFAULT_VAULT, "config": VizConfig()}


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
        edge_threshold=0.50,
        max_edges_per_node=6,
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
