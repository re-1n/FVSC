"""FVSC application entry point with the daily pilot API enabled."""

from __future__ import annotations

from .app import app
from .pilot_router import router as pilot_router


if not any(route.path.startswith("/pilot") for route in app.routes):
    app.include_router(pilot_router)
