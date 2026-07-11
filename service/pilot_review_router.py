"""Parse user-marked daily review notes into pilot feedback records."""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .pilot_router import _ensure_loaded, _lock, _save


router = APIRouter(prefix="/pilot", tags=["pilot-feedback"])
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_SNAPSHOT_RE = re.compile(r"^Snapshot:\s*`([^`]+)`\s*$", re.MULTILINE)
_POSITIVE_RE = re.compile(r"^-\s*\[[xX]\]\s*Полезно\s*/\s*точно\s*$", re.MULTILINE)
_NEGATIVE_RE = re.compile(r"^-\s*\[[xX]\]\s*Неточно\s*/\s*случайно\s*$", re.MULTILINE)
_IGNORED_HEADINGS = {"recently active sources", "notes"}


class PilotReviewFeedbackRequest(BaseModel):
    text: str
    source_path: str = "_fvsc_review/FVSC Daily Review.md"


@dataclass(frozen=True)
class ReviewMark:
    term: str
    useful: bool
    rating: int


def parse_review_marks(text: str) -> tuple[str | None, list[ReviewMark], list[str]]:
    """Extract unambiguous checked concept ratings from a generated review note."""
    snapshot_match = _SNAPSHOT_RE.search(text)
    snapshot_ref = snapshot_match.group(1).strip() if snapshot_match else None
    headings = list(_HEADING_RE.finditer(text))
    marks: list[ReviewMark] = []
    ambiguous: list[str] = []
    for index, heading in enumerate(headings):
        term = heading.group(1).strip()
        if not term or term.casefold() in _IGNORED_HEADINGS:
            continue
        start = heading.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        block = text[start:end]
        positive = _POSITIVE_RE.search(block) is not None
        negative = _NEGATIVE_RE.search(block) is not None
        if positive and negative:
            ambiguous.append(term)
        elif positive:
            marks.append(ReviewMark(term=term, useful=True, rating=5))
        elif negative:
            marks.append(ReviewMark(term=term, useful=False, rating=1))
    return snapshot_ref, marks, ambiguous


def _query_id(snapshot_ref: str, term: str) -> str:
    return hashlib.sha256(
        f"daily-review\0{snapshot_ref}\0{term}".encode("utf-8")
    ).hexdigest()


@router.post("/review-feedback")
async def pilot_review_feedback(req: PilotReviewFeedbackRequest):
    text = str(req.text)
    if len(text.encode("utf-8")) > 2 * 1024 * 1024:
        raise HTTPException(413, detail="review note exceeds size limit")
    snapshot_ref, marks, ambiguous = parse_review_marks(text)
    if snapshot_ref is None:
        raise HTTPException(422, detail="review note is missing Snapshot metadata")

    async with _lock:
        runtime, feedback, vault = _ensure_loaded()
        resolved_snapshot = (
            runtime.snapshot.snapshot_id
            if runtime.snapshot.snapshot_id.startswith(snapshot_ref)
            else snapshot_ref
        )
        existing = {str(record.get("query_id")) for record in feedback}
        submitted: list[dict[str, Any]] = []
        duplicates: list[str] = []
        for mark in marks:
            query_id = _query_id(snapshot_ref, mark.term)
            if query_id in existing:
                duplicates.append(mark.term)
                continue
            record = {
                "feedback_id": uuid.uuid4().hex,
                "recorded_at": time.time(),
                "query_id": query_id,
                "query_type": "daily_review_concept",
                "rating": mark.rating,
                "useful": mark.useful,
                "notes": f"Daily review rating for concept: {mark.term}",
                "snapshot_id": resolved_snapshot,
                "term": mark.term,
                "source_path": str(req.source_path),
            }
            feedback.append(record)
            existing.add(query_id)
            submitted.append(record)
        _save(runtime, feedback, vault)
        return {
            "snapshot_ref": snapshot_ref,
            "submitted": submitted,
            "submitted_count": len(submitted),
            "duplicates": duplicates,
            "ambiguous": ambiguous,
            "feedback_count": len(feedback),
        }
