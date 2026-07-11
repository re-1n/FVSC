"""Local API for the FVSC daily-life pilot.

The pilot runs beside the legacy visualization map.  It stores an append-only
JSON evidence ledger in ``<vault>/.fvsc/pilot-state.json`` and exposes a narrow
set of endpoints for rebuild, live note updates, semantic tracing and usefulness
feedback.
"""

from __future__ import annotations

import asyncio
from collections import Counter
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.exocortex_ingest import _clean_for_fvsc
from core.pilot_persistence import load_pilot_state, save_pilot_state
from core.pilot_runtime import PilotRuntime, source_revision
from core.text_parser_agnostic import text_to_semantic_input
from core.vault_ingest import strip_markdown

from . import viz_router as viz_router_module


router = APIRouter(prefix="/pilot", tags=["pilot"])
PILOT_DIRECTORY = ".fvsc"
PILOT_STATE_NAME = "pilot-state.json"
MAX_FILE_SIZE = 5 * 1024 * 1024
EXCLUDED_PARTS = {".obsidian", ".trash", ".fvsc", "_fvsc_concepts"}

_runtime: PilotRuntime | None = None
_feedback: list[dict[str, Any]] = []
_loaded_vault: Path | None = None
_lock = asyncio.Lock()


class PilotFileIngestRequest(BaseModel):
    path: str
    action: str
    text: Optional[str] = None
    old_path: Optional[str] = None
    observed_at: Optional[float] = None


class PilotTraceRequest(BaseModel):
    source: str
    target: str


class PilotFeedbackRequest(BaseModel):
    query_id: str
    query_type: str
    rating: int
    useful: bool
    notes: str = ""
    snapshot_id: Optional[str] = None


def _vault_path() -> Path:
    return Path(viz_router_module._state["vault_path"]).resolve()


def _state_path(vault: Path) -> Path:
    return vault / PILOT_DIRECTORY / PILOT_STATE_NAME


def _ensure_loaded() -> tuple[PilotRuntime, list[dict[str, Any]], Path]:
    global _runtime, _feedback, _loaded_vault
    vault = _vault_path()
    if _runtime is None or _loaded_vault != vault:
        _runtime, _feedback = load_pilot_state(_state_path(vault))
        _loaded_vault = vault
    return _runtime, _feedback, vault


def _save(runtime: PilotRuntime, feedback: list[dict[str, Any]], vault: Path) -> None:
    save_pilot_state(_state_path(vault), runtime, feedback=feedback)


def _relative_source(path: str) -> str:
    source = str(path).replace("\\", "/").strip().lstrip("/")
    if not source or source == "." or ".." in Path(source).parts:
        raise HTTPException(400, detail="invalid vault-relative path")
    return source


def _parse_text(raw_text: str) -> dict:
    stripped = strip_markdown(raw_text)
    cleaned = _clean_for_fvsc(stripped)
    if len(cleaned) < 20:
        return {}
    return text_to_semantic_input(cleaned, config=viz_router_module._get_parse_config())


def _event_sources(runtime: PilotRuntime, event_ids: tuple[str, ...] | list[str]) -> list[str]:
    return sorted({
        event.source_id
        for event_id in event_ids
        if (event := runtime.ledger.get(event_id)) is not None
    })


def _concept_payload(runtime: PilotRuntime, term: str, *, related_limit: int = 10) -> dict[str, Any]:
    concept = runtime.get(term)
    if concept is None:
        raise HTTPException(404, detail=f"concept not found: {term}")
    eigenvalues = np.linalg.eigvalsh(concept.state.shape)
    eigenvalues = sorted(
        (float(value) for value in eigenvalues if value > 0.02),
        reverse=True,
    )
    entropy = -sum(value * np.log(value) for value in eigenvalues if value > 1e-12)
    return {
        "term": concept.term,
        "snapshot_id": runtime.snapshot.snapshot_id,
        "mass": concept.state.mass,
        "evidence_count": concept.state.evidence_count,
        "uncertainty": concept.state.uncertainty,
        "polysemy_entropy": float(entropy),
        "facet_weights": eigenvalues,
        "sources": _event_sources(runtime, concept.evidence_ids),
        "related": runtime.related(concept.term, top_k=related_limit),
    }


@router.get("/status")
async def pilot_status():
    runtime, feedback, vault = _ensure_loaded()
    return {
        **runtime.status(),
        "vault_name": vault.name,
        "state_exists": _state_path(vault).exists(),
        "feedback_count": len(feedback),
    }


@router.post("/file_ingest")
async def pilot_file_ingest(req: PilotFileIngestRequest):
    """Apply one create/modify/delete/rename event from the Obsidian watcher."""
    async with _lock:
        runtime, feedback, vault = _ensure_loaded()
        action = str(req.action).casefold().strip()
        path = _relative_source(req.path)
        observed_at = time.time() if req.observed_at is None else float(req.observed_at)
        results = []

        if action == "delete":
            results.append(runtime.delete_source(source_id=path, observed_at=observed_at))
        elif action == "rename":
            if req.old_path:
                results.append(runtime.delete_source(
                    source_id=_relative_source(req.old_path),
                    observed_at=observed_at,
                ))
            if req.text is not None:
                results.append(runtime.replace_source(
                    source_id=path,
                    semantic_input=_parse_text(req.text),
                    source_revision=source_revision(req.text),
                    observed_at=observed_at,
                ))
        elif action in {"create", "modify"}:
            if req.text is None:
                raise HTTPException(400, detail=f"action={action} requires text")
            if len(req.text.encode("utf-8")) > MAX_FILE_SIZE:
                raise HTTPException(413, detail="note exceeds pilot size limit")
            results.append(runtime.replace_source(
                source_id=path,
                semantic_input=_parse_text(req.text),
                source_revision=source_revision(req.text),
                observed_at=observed_at,
            ))
        else:
            raise HTTPException(400, detail=f"unknown action: {action}")

        _save(runtime, feedback, vault)
        return {
            "path": path,
            "action": action,
            "updates": [result.__dict__ for result in results],
            **runtime.status(),
        }


@router.post("/rebuild")
async def pilot_rebuild():
    """Rebuild the pilot ledger from all eligible Markdown files in the vault."""
    global _runtime, _feedback, _loaded_vault
    async with _lock:
        vault = _vault_path()
        if not vault.exists() or not vault.is_dir():
            raise HTTPException(404, detail="configured vault directory does not exist")

        runtime = PilotRuntime()
        files_seen = 0
        files_indexed = 0
        assertions = 0
        errors: list[dict[str, str]] = []
        for path in sorted(vault.rglob("*.md")):
            relative = path.relative_to(vault)
            if any(part in EXCLUDED_PARTS for part in relative.parts):
                continue
            files_seen += 1
            try:
                if path.stat().st_size > MAX_FILE_SIZE:
                    errors.append({"path": relative.as_posix(), "error": "file_too_large"})
                    continue
                text = path.read_text(encoding="utf-8")
                result = runtime.replace_source(
                    source_id=relative.as_posix(),
                    semantic_input=_parse_text(text),
                    source_revision=source_revision(text),
                    observed_at=path.stat().st_mtime,
                )
                if result.asserted_events:
                    files_indexed += 1
                    assertions += result.asserted_events
            except Exception as exc:
                errors.append({"path": relative.as_posix(), "error": str(exc)})

        _runtime = runtime
        _feedback = []
        _loaded_vault = vault
        _save(runtime, _feedback, vault)
        return {
            "rebuilt": True,
            "files_seen": files_seen,
            "files_indexed": files_indexed,
            "assertions": assertions,
            "errors": errors[:50],
            **runtime.status(),
        }


@router.get("/concepts/{term}")
async def pilot_concept(term: str, related_limit: int = 10):
    runtime, _feedback_records, _vault = _ensure_loaded()
    if not 1 <= related_limit <= 50:
        raise HTTPException(422, detail="related_limit must be in [1, 50]")
    return _concept_payload(runtime, term, related_limit=related_limit)


@router.post("/trace")
async def pilot_trace(req: PilotTraceRequest):
    runtime, _feedback_records, _vault = _ensure_loaded()
    result = runtime.trace(req.source, req.target)
    if not result.get("found"):
        raise HTTPException(404, detail={"missing": result.get("missing", [])})
    result["shared_sources"] = _event_sources(runtime, result["shared_evidence_ids"])
    result["query_id"] = uuid.uuid4().hex
    return result


@router.get("/daily-review")
async def pilot_daily_review(limit: int = 10):
    """Return recently evidenced concepts for a lightweight daily review."""
    if not 1 <= limit <= 50:
        raise HTTPException(422, detail="limit must be in [1, 50]")
    runtime, _feedback_records, _vault = _ensure_loaded()
    recent = sorted(
        runtime.ledger.active_events,
        key=lambda event: (-event.observed_at, event.event_id),
    )
    terms: list[str] = []
    source_counts: Counter[str] = Counter()
    for event in recent:
        source_counts[event.source_id] += 1
        for term in (event.subject, event.object, event.relation):
            if term and term not in terms and runtime.get(term) is not None:
                terms.append(term)
            if len(terms) >= limit:
                break
        if len(terms) >= limit:
            break
    return {
        "snapshot_id": runtime.snapshot.snapshot_id,
        "concepts": [_concept_payload(runtime, term, related_limit=3) for term in terms],
        "recent_sources": [
            {"path": path, "active_assertions": count}
            for path, count in source_counts.most_common(limit)
        ],
    }


@router.post("/feedback", status_code=201)
async def pilot_feedback(req: PilotFeedbackRequest):
    async with _lock:
        runtime, feedback, vault = _ensure_loaded()
        query_id = str(req.query_id).strip()
        query_type = str(req.query_type).strip()
        notes = str(req.notes).strip()
        if not query_id or not query_type:
            raise HTTPException(422, detail="query_id and query_type are required")
        if not 1 <= req.rating <= 5:
            raise HTTPException(422, detail="rating must be in [1, 5]")
        if len(notes) > 2000:
            raise HTTPException(422, detail="notes must be at most 2000 characters")
        record = {
            "feedback_id": uuid.uuid4().hex,
            "recorded_at": time.time(),
            "query_id": query_id,
            "query_type": query_type,
            "rating": int(req.rating),
            "useful": bool(req.useful),
            "notes": notes,
            "snapshot_id": req.snapshot_id or runtime.snapshot.snapshot_id,
        }
        feedback.append(record)
        _save(runtime, feedback, vault)
        return record


@router.get("/feedback/summary")
async def pilot_feedback_summary():
    runtime, feedback, _vault = _ensure_loaded()
    if not feedback:
        return {
            "snapshot_id": runtime.snapshot.snapshot_id,
            "count": 0,
            "mean_rating": None,
            "useful_rate": None,
            "by_query_type": {},
        }
    by_type: dict[str, list[dict[str, Any]]] = {}
    for record in feedback:
        by_type.setdefault(str(record.get("query_type", "unknown")), []).append(record)
    return {
        "snapshot_id": runtime.snapshot.snapshot_id,
        "count": len(feedback),
        "mean_rating": sum(int(item["rating"]) for item in feedback) / len(feedback),
        "useful_rate": sum(bool(item["useful"]) for item in feedback) / len(feedback),
        "by_query_type": {
            query_type: {
                "count": len(records),
                "mean_rating": sum(int(item["rating"]) for item in records) / len(records),
                "useful_rate": sum(bool(item["useful"]) for item in records) / len(records),
            }
            for query_type, records in sorted(by_type.items())
        },
    }
