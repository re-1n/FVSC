"""FVSC application entry point with the daily pilot API enabled."""

from __future__ import annotations

from .app import app
from .pilot_evaluation_router import router as pilot_evaluation_router
from .pilot_readiness_router import router as pilot_readiness_router
from .pilot_review_router import router as pilot_review_router
from .pilot_router import router as pilot_router


def _has_route(path: str) -> bool:
    """Return whether FastAPI currently exposes ``path``.

    Recent FastAPI versions may include internal router sentinels in
    ``app.routes`` that do not expose a ``path`` attribute.
    """
    return any(getattr(route, "path", None) == path for route in app.routes)


if not _has_route("/pilot/status"):
    app.include_router(pilot_router)
if not _has_route("/pilot/evaluate"):
    app.include_router(pilot_evaluation_router)
if not _has_route("/pilot/review-feedback"):
    app.include_router(pilot_review_router)
if not _has_route("/pilot/readiness"):
    app.include_router(pilot_readiness_router)
