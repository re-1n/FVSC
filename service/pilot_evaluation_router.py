"""Vault-level chronological held-out evaluation API for the FVSC pilot."""

from __future__ import annotations

import asyncio
from pathlib import Path
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.pilot_evaluation import HeldoutDocument, run_heldout_evaluation
from core.pilot_runtime import source_revision

from .pilot_report_store import load_evaluation_report, save_evaluation_report
from .pilot_router import (
    EXCLUDED_PARTS,
    MAX_FILE_SIZE,
    _parse_text,
    _vault_path,
)


router = APIRouter(prefix="/pilot", tags=["pilot-evaluation"])


class PilotEvaluationRequest(BaseModel):
    train_fraction: float = 0.8
    bootstrap_samples: int = 1000
    max_files: int = 5000


def _load_documents(vault: Path, *, max_files: int) -> tuple[list[HeldoutDocument], list[dict[str, str]]]:
    documents: list[HeldoutDocument] = []
    errors: list[dict[str, str]] = []
    for path in sorted(vault.rglob("*.md")):
        relative = path.relative_to(vault)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if len(documents) >= max_files:
            break
        try:
            stat = path.stat()
            if stat.st_size > MAX_FILE_SIZE:
                errors.append({"path": relative.as_posix(), "error": "file_too_large"})
                continue
            text = path.read_text(encoding="utf-8")
            semantic_input = _parse_text(text)
            if not semantic_input:
                continue
            documents.append(HeldoutDocument(
                source_id=relative.as_posix(),
                observed_at=stat.st_mtime,
                semantic_input=semantic_input,
                source_revision=source_revision(text),
            ))
        except Exception as exc:
            errors.append({"path": relative.as_posix(), "error": str(exc)})
    return documents, errors


@router.post("/evaluate")
async def pilot_evaluate(req: PilotEvaluationRequest):
    if not 0.5 <= req.train_fraction < 1.0:
        raise HTTPException(422, detail="train_fraction must be in [0.5, 1.0)")
    if not 100 <= req.bootstrap_samples <= 10000:
        raise HTTPException(422, detail="bootstrap_samples must be in [100, 10000]")
    if not 2 <= req.max_files <= 50000:
        raise HTTPException(422, detail="max_files must be in [2, 50000]")

    vault = _vault_path()
    if not vault.exists() or not vault.is_dir():
        raise HTTPException(404, detail="configured vault directory does not exist")
    documents, errors = await asyncio.to_thread(_load_documents, vault, max_files=req.max_files)
    if len(documents) < 2:
        raise HTTPException(422, detail="at least two parseable dated notes are required")

    report = await asyncio.to_thread(
        run_heldout_evaluation,
        documents,
        train_fraction=req.train_fraction,
        bootstrap_samples=req.bootstrap_samples,
    )
    payload = {
        "generated_at": time.time(),
        "vault_name": vault.name,
        "documents_loaded": len(documents),
        "parse_errors": errors[:100],
        **report,
    }
    json_path, markdown_path = await asyncio.to_thread(
        save_evaluation_report, vault, payload
    )
    return {
        **payload,
        "report_path": str(json_path),
        "review_path": str(markdown_path),
    }


@router.get("/evaluate/latest")
async def pilot_evaluate_latest():
    vault = _vault_path()
    payload = await asyncio.to_thread(load_evaluation_report, vault)
    if payload is None:
        raise HTTPException(404, detail="no held-out evaluation report exists")
    json_path, markdown_path = save_evaluation_report(vault, payload)
    return {
        **payload,
        "report_path": str(json_path),
        "review_path": str(markdown_path),
    }
