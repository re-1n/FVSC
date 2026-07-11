"""FVSC Core Service — FastAPI application."""

from __future__ import annotations

import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import JSONResponse, RedirectResponse

from core.density_core import SemanticSpace, facets, purity, von_neumann_entropy
from core.text_parser_agnostic import ParseConfig
from core.thesaurus_prior import ThesaurusPrior

from .ingest import ingest_text
from .models import (
    ChunkHit,
    CompareResponse,
    ConceptReport,
    CreateSpaceRequest,
    DeepenRequest,
    ErrorResponse,
    FacetInfo,
    IngestRequest,
    IngestResponse,
    RetrieveRequest,
    RetrieveResponse,
    SpaceMeta,
)
from .retrieval import retrieve_by_query
from .security import configure_security
from .store import SpaceStore
from . import viz_router as viz_router_module
from .viz_router import router as viz_router
from .viz_session import VizConfig

# ── Globals ───────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "spaces"
CONCEPTNET_PATH = PROJECT_ROOT / "data" / "conceptnet_ru.json"

AUTOSAVE_THRESHOLD = int(os.environ.get("FVSC_AUTOSAVE_THRESHOLD", "10"))

store: SpaceStore
shared_config: ParseConfig


# ── Lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global store, shared_config
    # Startup
    store = SpaceStore(DATA_DIR, autosave_threshold=AUTOSAVE_THRESHOLD)
    # Build default ParseConfig
    prior = None
    if CONCEPTNET_PATH.exists():
        prior = ThesaurusPrior.from_conceptnet(str(CONCEPTNET_PATH))
    shared_config = ParseConfig(
        window=4,
        min_freq=1,     # service handles small inputs — one paragraph at a time
        max_concepts=800,
        min_token_len=3,
        thesaurus_prior=prior,
        prior_known_bonus=1.2,
    )
    # Plugin-injected overrides (kept backwards compatible — both vars optional).
    env_vault = os.environ.get("FVSC_VAULT_PATH")
    env_model = os.environ.get("FVSC_LLM_MODEL")
    if env_vault or env_model:
        viz_router_module.configure(
            vault_path=Path(env_vault) if env_vault else None,
            config=VizConfig(model=env_model) if env_model else None,
        )
    yield
    # Shutdown
    store.save_all()


app = FastAPI(
    title="FVSC Core Service",
    version="0.1.0",
    lifespan=lifespan,
)
configure_security(app)
app.include_router(viz_router)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/viz")

# ── Error handler ─────────────────────────────────────────────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


# ── Helpers ───────────────────────────────────────────────────────

def _require_space(name: str):
    bundle = store.get(name)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"Space '{name}' not found")
    return bundle


def _build_report(space: SemanticSpace, term: str) -> ConceptReport:
    concept = space.concepts.get(term)
    if concept is None:
        return ConceptReport(term=term, found=False)

    rho_n = concept.rho_deep_norm
    if rho_n is None:
        return ConceptReport(term=term, found=True, component_count=len(concept.components))

    f = facets(rho_n, threshold=0.02)
    contains = space.query_contains(term, top_k=10)
    contained_in = space.query_contained_in(term, top_k=10)

    return ConceptReport(
        term=term,
        found=True,
        component_count=len(concept.components),
        mass=round(float(rho_n.trace()), 4),
        polysemy=round(float(von_neumann_entropy(rho_n)), 4),
        purity=round(float(purity(rho_n)), 4),
        facets=[FacetInfo(weight=round(float(w), 4), strength=round(float(sum(v**2)), 4)) for w, v in f],
        contains=[{"term": t, "weight": round(float(w), 4)} for t, w in contains],
        contained_in=[{"term": t, "weight": round(float(w), 4)} for t, w in contained_in],
    )


# ── Space lifecycle ───────────────────────────────────────────────

@app.get("/spaces")
async def list_spaces():
    return store.list_spaces()


@app.post("/spaces", status_code=201)
async def create_space(req: CreateSpaceRequest):
    if req.name in store._bundles:
        raise HTTPException(status_code=409, detail=f"Space '{req.name}' already exists")
    bundle = store.get_or_create(req.name, dim=req.dim)
    # Ensure dirty flag is initialized
    if not bundle.meta:
        bundle.meta = bundle._default_meta()
    bundle.meta["dim"] = req.dim
    return {"name": req.name, "dim": req.dim, "created": True}


@app.get("/spaces/{name}")
async def get_space(name: str):
    bundle = _require_space(name)
    return {
        "name": name,
        "dim": bundle.space.dim,
        "concept_count": len(bundle.space.concepts),
        "chunk_count": len(bundle.chunks),
        "ingest_count": bundle.meta.get("ingest_count", 0),
        "ingests_since_save": bundle.meta.get("ingests_since_save", 0),
        "last_modified": bundle.meta.get("last_modified"),
    }


@app.delete("/spaces/{name}")
async def delete_space(name: str):
    if store.delete(name):
        return {"deleted": True, "name": name}
    raise HTTPException(status_code=404, detail=f"Space '{name}' not found")


@app.post("/spaces/{name}/save")
async def save_space(name: str):
    bundle = _require_space(name)
    store.save(name)
    return {"saved": True, "name": name, "concept_count": len(bundle.space.concepts)}


@app.post("/spaces/{name}/deepen")
async def deepen_space(name: str, req: DeepenRequest):
    bundle = _require_space(name)
    space = bundle.space
    concepts_before = len(space.concepts)
    space.recursive_deepen(iterations=req.iterations, alpha=req.alpha)
    store.mark_dirty(name)
    return {
        "deepened": True,
        "concepts_before": concepts_before,
        "concepts_after": len(space.concepts),
    }


# ── Ingest ────────────────────────────────────────────────────────

@app.post("/spaces/{name}/ingest")
async def ingest(name: str, req: IngestRequest):
    bundle = store.get_or_create(name)
    bundle, chunks_added, concepts_before = ingest_text(
        bundle, req.text, req.source_id, fmt=req.format, config=shared_config,
    )
    store.mark_dirty(name)
    return IngestResponse(
        chunks_added=chunks_added,
        concepts_total=len(bundle.space.concepts),
        source_id=req.source_id,
    )


# ── Concept queries ───────────────────────────────────────────────

@app.get("/spaces/{name}/concepts/{term}/contains")
async def concept_contains(name: str, term: str, top_k: int = 10):
    bundle = _require_space(name)
    return bundle.space.query_contains(term, top_k=top_k)


@app.get("/spaces/{name}/concepts/{term}/contained-in")
async def concept_contained_in(name: str, term: str, top_k: int = 10):
    bundle = _require_space(name)
    return bundle.space.query_contained_in(term, top_k=top_k)


@app.get("/spaces/{name}/concepts/{term}/facets")
async def concept_facets(name: str, term: str):
    bundle = _require_space(name)
    return bundle.space.query_facets(term)


@app.get("/spaces/{name}/concepts/{term}/polysemy")
async def concept_polysemy(name: str, term: str):
    bundle = _require_space(name)
    polysemy = bundle.space.query_polysemy(term)
    if polysemy is None:
        raise HTTPException(status_code=404, detail=f"Concept '{term}' not found")
    return {"term": term, "polysemy": round(float(polysemy), 4)}


@app.get("/spaces/{name}/concepts/{term}/report")
async def concept_report(name: str, term: str):
    bundle = _require_space(name)
    report = _build_report(bundle.space, term)
    if not report.found:
        raise HTTPException(status_code=404, detail=f"Concept '{term}' not found")
    return report


@app.get("/spaces/{name}/concepts/{term}/sources")
async def concept_sources(name: str, term: str, top_k: int = 10):
    """Reflection endpoint: which vault notes formed this concept's meaning.

    Aggregates Judgment.source_text across the concept's components,
    weighted by component mass. Skips placeholder sources ([vault], [agnostic],
    [thesaurus:*]) and `[self]`. Returns top_k real notes, normalized to 1.0.
    """
    bundle = _require_space(name)
    concept = bundle.space.concepts.get(term)
    if concept is None:
        raise HTTPException(status_code=404, detail=f"Concept '{term}' not found")

    from collections import Counter
    agg: "Counter[str]" = Counter()
    for c in concept.components:
        if c.archived:
            continue
        src = c.judgment.source_text or ""
        if not src or src.startswith("[") and src.endswith("]"):
            continue   # skip placeholder / synthetic sources
        agg[src] += float(c.weight)

    total = sum(agg.values())
    sources = [
        {"path": s, "weight": round(w / total, 4) if total else 0.0}
        for s, w in agg.most_common(top_k)
    ]
    return {"term": term, "total_components": len(concept.components), "sources": sources}


# ── Similarity & retrieval ────────────────────────────────────────

@app.get("/spaces/{name}/similarity")
async def similarity(name: str, a: str, b: str):
    bundle = _require_space(name)
    score = bundle.space.query_similarity(a, b)
    if score is None:
        raise HTTPException(status_code=404, detail="One or both concepts not found")
    return {"a": a, "b": b, "similarity": round(float(score), 4)}


@app.post("/spaces/{name}/retrieve")
async def retrieve(name: str, req: RetrieveRequest):
    bundle = _require_space(name)
    hits = retrieve_by_query(bundle, req.query, top_k=req.top_k, config=shared_config)
    return RetrieveResponse(
        hits=[ChunkHit(**h) for h in hits]
    )


# ── Feedback (third cascade layer) ────────────────────────────────
#
# Wires core/feedback.py FeedbackEngine into the service. Engines are
# per-space and per-process: history/_asked_keys are session state, the
# actual map updates (confirm/reject/promote/...) mutate the space and
# are persisted through the normal dirty-flag autosave path.

_feedback_engines: dict = {}          # space name -> FeedbackEngine
_pending_questions: dict = {}         # space name -> {question_id: FeedbackQuestion}


class FeedbackAnswerRequest(BaseModel):
    question_id: str
    answer_index: int


def _get_engine(name: str):
    from core.feedback import FeedbackEngine
    bundle = _require_space(name)
    engine = _feedback_engines.get(name)
    if engine is None or engine.space is not bundle.space:
        # New engine if space was (re)loaded — engine must track the live object
        engine = FeedbackEngine(bundle.space)
        _feedback_engines[name] = engine
        _pending_questions[name] = {}
    return engine


@app.get("/spaces/{name}/feedback/questions")
async def feedback_questions(name: str, max_count: int = 5):
    """Generate calibration questions from the current map state."""
    engine = _get_engine(name)
    pending = _pending_questions.setdefault(name, {})
    questions = engine.generate_questions(max_count=max_count)

    out = []
    for q in questions:
        qid = uuid.uuid4().hex[:12]
        pending[qid] = q
        out.append({
            "question_id": qid,
            "question_type": q.question_type,
            "priority": q.priority,
            "prompt_text": q.prompt_text,
            "options": q.options,
            "related_concepts": q.related_concepts,
        })
    return {"questions": out}


@app.post("/spaces/{name}/feedback/answer")
async def feedback_answer(name: str, req: FeedbackAnswerRequest):
    """Apply the user's answer to the map (confirm/reject/promote/...)."""
    engine = _get_engine(name)
    pending = _pending_questions.setdefault(name, {})
    question = pending.pop(req.question_id, None)
    if question is None:
        raise HTTPException(
            status_code=404,
            detail=f"Question '{req.question_id}' not found or already answered",
        )
    if not (0 <= req.answer_index < len(question.options)):
        raise HTTPException(status_code=422, detail="answer_index out of range")

    engine.process_answer(question, req.answer_index)
    store.mark_dirty(name)
    return {"processed": True, "stats": engine.stats()}


@app.get("/spaces/{name}/feedback/stats")
async def feedback_stats(name: str):
    """Review progress: how much of the map has been calibrated."""
    engine = _get_engine(name)
    return engine.stats()


# ── Cross-space compare ───────────────────────────────────────────

@app.get("/compare")
async def compare_spaces(a: str, b: str, top_k: int = 20):
    bundle_a = store.get(a)
    bundle_b = store.get(b)
    if bundle_a is None:
        raise HTTPException(status_code=404, detail=f"Space '{a}' not found")
    if bundle_b is None:
        raise HTTPException(status_code=404, detail=f"Space '{b}' not found")
    result = SemanticSpace.compare_maps(bundle_a.space, bundle_b.space, top_k=top_k)
    return CompareResponse(
        shared_concepts=[{"term": t, "similarity": round(float(s), 4)} for t, s in result.get("shared_concepts", [])],
        divergent=[{"term": t, "similarity": round(float(s), 4)} for t, s in result.get("divergent", [])],
        aligned=[{"term": t, "similarity": round(float(s), 4)} for t, s in result.get("aligned", [])],
        global_similarity=round(float(result.get("global_similarity", 0)), 4),
    )
