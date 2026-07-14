"""FastAPI transport over ``VaultRuntime`` with no ingest logic in routes."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
import time
from typing import cast

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    SearchHitResponse,
    SearchRequest,
    SearchResponse,
    SourceResponse,
    StatusResponse,
)
from .runtime import (
    RuntimeNotLoadedError,
    StaleSourceStateError,
    VaultRuntime,
)


def _runtime_from_environment() -> VaultRuntime | None:
    raw_vault = os.environ.get("FVSC_VAULT_PATH", "").strip()
    if not raw_vault:
        return None
    raw_cache = os.environ.get("FVSC_CACHE_PATH", "").strip()
    return VaultRuntime(
        Path(raw_vault),
        cache_path=Path(raw_cache) if raw_cache else None,
    )


_RUNTIME_UNSET = object()


def create_app(
    runtime: VaultRuntime | None | object = _RUNTIME_UNSET,
    *,
    auto_load: bool = True,
) -> FastAPI:
    selected_runtime = (
        _runtime_from_environment()
        if runtime is _RUNTIME_UNSET
        else cast(VaultRuntime | None, runtime)
    )
    startup_state: dict[str, str | None] = {"error": None}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if (
            auto_load
            and selected_runtime is not None
            and selected_runtime.cache_path.exists()
        ):
            try:
                selected_runtime.load()
            except StaleSourceStateError:
                startup_state["error"] = "cache_stale"
            except ValueError:
                startup_state["error"] = "cache_invalid"
        yield

    application = FastAPI(
        title="FVSC Local Service",
        version="1.0.0",
        lifespan=lifespan,
    )
    # This transport is intended to bind to 127.0.0.1. Obsidian's app origin
    # varies across desktop versions, so local clients need a permissive CORS
    # header while the host binding remains the actual security boundary.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def require_runtime() -> VaultRuntime:
        if selected_runtime is None:
            raise HTTPException(
                status_code=503,
                detail="FVSC_VAULT_PATH is not configured",
            )
        return selected_runtime

    @application.exception_handler(RuntimeNotLoadedError)
    async def runtime_not_loaded_handler(_, exc: RuntimeNotLoadedError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(StaleSourceStateError)
    async def stale_state_handler(_, exc: StaleSourceStateError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        configured = selected_runtime is not None
        loaded = configured and selected_runtime.status().loaded
        return HealthResponse(
            status="ok" if configured else "unconfigured",
            configured=configured,
            loaded=loaded,
            startup_error=startup_state["error"],
        )

    @application.get("/v1/status", response_model=StatusResponse)
    def status() -> StatusResponse:
        return StatusResponse.from_runtime(require_runtime().status())

    @application.post("/v1/vault/sync", response_model=StatusResponse)
    def synchronize() -> StatusResponse:
        startup_state["error"] = None
        return StatusResponse.from_runtime(require_runtime().sync())

    @application.post("/v1/search", response_model=SearchResponse)
    def search(request: SearchRequest) -> SearchResponse:
        hits = require_runtime().search(
            request.query,
            top_k=request.top_k,
            context_depth=request.context_depth,
        )
        return SearchResponse(
            hits=[SearchHitResponse.from_runtime(hit) for hit in hits]
        )

    @application.get("/v1/source", response_model=SourceResponse)
    def source(
        source_id: str = Query(min_length=1, max_length=8_192),
        source_revision: str | None = Query(default=None, min_length=64, max_length=64),
    ) -> SourceResponse:
        try:
            document = require_runtime().source_document(source_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="source not found") from exc
        if source_revision is not None and source_revision != document.source_revision:
            raise HTTPException(status_code=409, detail="source revision changed")
        return SourceResponse(
            source_id=document.source_id,
            source_revision=document.source_revision,
            observed_at=document.observed_at,
            source_kind=document.source_kind,
            text=document.text,
        )

    @application.post("/v1/feedback", response_model=FeedbackResponse)
    def feedback(request: FeedbackRequest) -> FeedbackResponse:
        runtime_value = require_runtime()
        observed_at = time.time() if request.observed_at is None else request.observed_at
        try:
            event = runtime_value.record_feedback(
                target_event_id=request.target_event_id,
                action=request.action,
                context_tags=tuple(request.context_tags),
                observed_at=observed_at,
                recorded_at=observed_at,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return FeedbackResponse(
            event_id=event.event_id,
            target_event_id=request.target_event_id,
            action=request.action,
            ledger_digest=runtime_value.ledger.digest,
        )

    return application


app = create_app()


__all__ = ["app", "create_app"]
