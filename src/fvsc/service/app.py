"""FastAPI transport over ``VaultRuntime`` with no ingest logic in routes."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
import time
from typing import cast

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ..integrations import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    OllamaIntegrationError,
    OllamaInterpretationBackend,
)
from ..interpretation import InterpretationBackend
from .models import (
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    InterpretRequest,
    InterpretationBackendStatusResponse,
    InterpretationProposalResponse,
    SearchHitResponse,
    SearchRequest,
    SearchResponse,
    SourceResponse,
    StatusResponse,
)
from .interpret import VaultInterpreter
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
_BACKEND_UNSET = object()


def _backend_from_environment() -> OllamaInterpretationBackend:
    return OllamaInterpretationBackend(
        model=os.environ.get("FVSC_LLM_MODEL", DEFAULT_OLLAMA_MODEL),
        host=os.environ.get("FVSC_OLLAMA_HOST", DEFAULT_OLLAMA_HOST),
    )


def create_app(
    runtime: VaultRuntime | None | object = _RUNTIME_UNSET,
    *,
    interpretation_backend: InterpretationBackend | None | object = _BACKEND_UNSET,
    auto_load: bool = True,
) -> FastAPI:
    selected_runtime = (
        _runtime_from_environment()
        if runtime is _RUNTIME_UNSET
        else cast(VaultRuntime | None, runtime)
    )
    selected_backend = (
        _backend_from_environment()
        if interpretation_backend is _BACKEND_UNSET
        else cast(InterpretationBackend | None, interpretation_backend)
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
            interpretation_configured=selected_backend is not None,
            startup_error=startup_state["error"],
        )

    @application.get(
        "/v1/interpretation/status",
        response_model=InterpretationBackendStatusResponse,
    )
    def interpretation_status() -> InterpretationBackendStatusResponse:
        if selected_backend is None:
            return InterpretationBackendStatusResponse(
                configured=False,
                backend_id=None,
                model=None,
                reachable=None,
                local_models=[],
            )
        ping = getattr(selected_backend, "ping", None)
        list_models = getattr(selected_backend, "list_local_models", None)
        reachable = bool(ping()) if callable(ping) else None
        models = list(list_models()) if callable(list_models) and reachable else []
        return InterpretationBackendStatusResponse(
            configured=True,
            backend_id=selected_backend.backend_id,
            model=selected_backend.model,
            reachable=reachable,
            local_models=models,
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

    @application.post(
        "/v1/interpret",
        response_model=InterpretationProposalResponse,
    )
    def interpret(request: InterpretRequest) -> InterpretationProposalResponse:
        runtime_value = require_runtime()
        if selected_backend is None:
            raise HTTPException(
                status_code=503,
                detail="interpretation backend is not configured",
            )
        try:
            proposal = VaultInterpreter(runtime_value, selected_backend).interpret(
                request.question,
                top_k=request.top_k,
                context_depth=request.context_depth,
            )
        except OllamaIntegrationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return InterpretationProposalResponse.from_proposal(proposal)

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
