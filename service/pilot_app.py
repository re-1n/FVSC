"""FVSC application entry point with the daily pilot API enabled."""

from __future__ import annotations

from .app import app
from .pilot_evaluation_router import router as pilot_evaluation_router
from .pilot_router import router as pilot_router


if not any(route.path == "/pilot/status" for route in app.routes):
    app.include_router(pilot_router)
if not any(route.path == "/pilot/evaluate" for route in app.routes):
    app.include_router(pilot_evaluation_router)
