"""FastAPI transport over ``VaultRuntime`` with no ingest logic in routes."""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
import hashlib
from pathlib import Path
import time
import threading
from typing import cast

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from ..retrieval.containers import ContainerStore, concept_name


class ComponentRequest(BaseModel):
    parent: str = Field(min_length=1, max_length=512)
    child: str = Field(min_length=1, max_length=512)
    present: bool = True

from ..integrations import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    OllamaIntegrationError,
    OllamaInterpretationBackend,
)
from ..interpretation import InterpretationBackend
from ..interpretation.clarifications import ClarificationStore, ClarificationTarget
from ..interpretation import (
    DEFAULT_INTERPRETATION_JOURNAL_RELATIVE_PATH,
    InterpretationStore,
)
from .models import (
    ConceptMentionsRequest,
    ClarificationPrepareRequest,
    ClarificationAnswerRequest,
    ClarificationResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    InterpretRequest,
    InterpretationBackendStatusResponse,
    InterpretationProposalResponse,
    ProposalAssessmentRequest,
    ProposalAssessmentResponse,
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
_STORE_UNSET = object()


def _backend_from_environment() -> OllamaInterpretationBackend:
    return OllamaInterpretationBackend(
        model=os.environ.get("FVSC_LLM_MODEL", DEFAULT_OLLAMA_MODEL),
        host=os.environ.get("FVSC_OLLAMA_HOST", DEFAULT_OLLAMA_HOST),
    )


def create_app(
    runtime: VaultRuntime | None | object = _RUNTIME_UNSET,
    *,
    interpretation_backend: InterpretationBackend | None | object = _BACKEND_UNSET,
    interpretation_store: InterpretationStore | None | object = _STORE_UNSET,
    clarification_store: ClarificationStore | None = None,
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
    store_enabled = interpretation_store is not None
    store_state: dict[str, InterpretationStore | None] = {
        "store": (
            None
            if interpretation_store is _STORE_UNSET
            else cast(InterpretationStore | None, interpretation_store)
        )
    }
    startup_state: dict[str, str | None] = {"error": None}
    clarification_state = {"store": clarification_store}
    clarification_lock = threading.RLock()

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
        try:
            yield
        finally:
            # Injected stores are owned by the caller (also useful for in-memory tests).
            if clarification_store is None and clarification_state["store"] is not None:
                clarification_state["store"].close()
                clarification_state["store"] = None

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

    def require_interpretation_store() -> InterpretationStore:
        if not store_enabled:
            raise HTTPException(
                status_code=503,
                detail="interpretation journal is not configured",
            )
        existing = store_state["store"]
        if existing is not None:
            return existing
        runtime_value = require_runtime()
        raw_path = os.environ.get("FVSC_INTERPRETATION_JOURNAL_PATH", "").strip()
        path = (
            Path(raw_path)
            if raw_path
            else runtime_value.vault_dir / DEFAULT_INTERPRETATION_JOURNAL_RELATIVE_PATH
        )
        try:
            created = InterpretationStore(path)
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail="interpretation journal failed validation",
            ) from exc
        store_state["store"] = created
        return created

    def require_clarification_store() -> ClarificationStore:
        with clarification_lock:
            existing = clarification_state["store"]
            if existing is None:
                existing = ClarificationStore(require_runtime().vault_dir / ".fvsc" / "clarifications.sqlite3")
                clarification_state["store"] = existing
            return existing

    @application.post("/v1/clarifications/prepare", response_model=ClarificationResponse)
    def prepare_clarification(request: ClarificationPrepareRequest) -> ClarificationResponse:
        try:
            document = require_runtime().source_document(request.source_id)
            if document.source_revision != request.source_revision:
                raise HTTPException(status_code=409, detail="source changed; search again")
            target = ClarificationTarget.create(document, start=request.start, end=request.end,
                                                question=request.question)
            return ClarificationResponse(**require_clarification_store().prepare(target, document))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="source not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.post("/v1/clarifications/answer", response_model=ClarificationResponse)
    def answer_clarification(request: ClarificationAnswerRequest) -> ClarificationResponse:
        try:
            store = require_clarification_store()
            target = store.target(request.clarification_id)
            document = require_runtime().source_document(target.source_id)
            return ClarificationResponse(**store.answer(
                request.clarification_id, document, action=request.action,
                note=request.note, expected_sequence=request.expected_sequence,
            ))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="clarification or source not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

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
            vault_id=(hashlib.sha256(os.path.normcase(os.path.realpath(str(selected_runtime.vault_dir))).encode("utf-8")).hexdigest()
                      if configured else None),
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

    @application.get("/v1/map")
    def concept_map(focus: str | None = Query(default=None, max_length=512)):
        try:
            return require_runtime().concept_map(focus)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="concept not found in current map") from exc

    @application.post("/v1/map/mentions")
    def concept_mentions(request: ConceptMentionsRequest):
        if sum(len(text) for text in request.texts) > 65536:
            raise HTTPException(status_code=422, detail="text batch is too long")
        return require_runtime().concept_mentions(request.texts)

    @application.get("/v1/map/containers")
    def saved_containers():
        return ContainerStore(require_runtime().vault_dir / ".fvsc" / "containers.sqlite3").terms()

    @application.get("/v1/map/container")
    def concept_container(focus: str = Query(min_length=1, max_length=512)):
        runtime_value = require_runtime()
        try:
            focus = concept_name(focus)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        store = ContainerStore(runtime_value.vault_dir / ".fvsc" / "containers.sqlite3")
        children = store.children(focus)
        try:
            neighborhood = runtime_value.concept_map(focus)
        except KeyError:
            neighborhood = {"nodes": [], "edges": [], "total_neighbors": 0}
        composition = runtime_value.concept_composition(focus, children)
        for node in composition["nodes"]:
            node["component_count"] = len(store.children(node["term"]))
        return {"focus": focus, **composition,
                "components": children, "suggestions": [n for n in neighborhood["nodes"] if n["term"] != focus and n["term"] not in children],
                "total_neighbors": neighborhood["total_neighbors"]}

    @application.post("/v1/map/component")
    def set_component(request: ComponentRequest):
        store = ContainerStore(require_runtime().vault_dir / ".fvsc" / "containers.sqlite3")
        try:
            store.set_component(request.parent, request.child, request.present)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"ok": True}

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
            proposal = VaultInterpreter(
                runtime_value,
                selected_backend,
                store=require_interpretation_store(),
            ).interpret(
                request.question,
                top_k=request.top_k,
                context_depth=request.context_depth,
                conversation_id=request.conversation_id,
                previous_proposal_ids=tuple(request.previous_proposal_ids),
            )
        except OllamaIntegrationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return InterpretationProposalResponse.from_proposal(proposal)

    @application.get("/v1/dialogues")
    def dialogues():
        grouped = {}
        for proposal in require_interpretation_store().journal.proposals:
            identity = proposal.metadata.get("conversation_id") or "legacy"
            if identity not in grouped:
                grouped[identity] = {"conversation_id": identity, "title": "Ранее заданные отдельные вопросы" if identity == "legacy" else proposal.question[:100],
                                     "updated_at": proposal.generated_at, "turns": 0}
            grouped[identity]["turns"] += 1
            grouped[identity]["updated_at"] = max(grouped[identity]["updated_at"], proposal.generated_at)
        return sorted(grouped.values(), key=lambda item: item["updated_at"], reverse=True)[:100]

    @application.get("/v1/dialogues/{conversation_id}", response_model=list[InterpretationProposalResponse])
    def dialogue(conversation_id: str):
        return [InterpretationProposalResponse.from_proposal(p) for p in sorted(
            (p for p in require_interpretation_store().journal.proposals
             if (p.metadata.get("conversation_id") or "legacy") == conversation_id), key=lambda p: p.generated_at
        )][-200:]

    @application.post(
        "/v1/interpret/assess",
        response_model=ProposalAssessmentResponse,
    )
    def assess_proposal(
        request: ProposalAssessmentRequest,
    ) -> ProposalAssessmentResponse:
        recorded_at = time.time() if request.recorded_at is None else request.recorded_at
        try:
            assessment = require_interpretation_store().record_assessment(
                proposal_id=request.proposal_id,
                case_id=request.case_id,
                verdict=request.verdict,
                accepted_claim_ids=tuple(request.accepted_claim_ids),
                rejected_claim_ids=tuple(request.rejected_claim_ids),
                reason_tags=tuple(request.reason_tags),
                recorded_at=recorded_at,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return ProposalAssessmentResponse.from_assessment(assessment)

    @application.get(
        "/v1/interpret/{proposal_id}/assessment",
        response_model=ProposalAssessmentResponse,
    )
    def latest_assessment(proposal_id: str) -> ProposalAssessmentResponse:
        assessment = require_interpretation_store().latest_assessment(proposal_id)
        if assessment is None:
            raise HTTPException(status_code=404, detail="proposal assessment not found")
        return ProposalAssessmentResponse.from_assessment(assessment)

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
