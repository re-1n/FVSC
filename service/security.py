"""Security helpers for the local FVSC HTTP service.

Loopback binding is not a browser security boundary: arbitrary web pages can
still send requests to 127.0.0.1. These helpers keep browser access limited to
Obsidian and FVSC pages served from loopback, reject disallowed browser origins
before endpoint execution, and reject unexpected Host headers to reduce
DNS-rebinding exposure.
"""

from __future__ import annotations

import os
import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse, Response

DEFAULT_ALLOWED_ORIGINS = {"app://obsidian.md"}
DEFAULT_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
LOOPBACK_ORIGIN_RE = r"^https?://(?:127\.0\.0\.1|localhost|\[::1\])(?::\d{1,5})?$"


def _csv_env(name: str) -> set[str]:
    return {
        value.strip()
        for value in os.environ.get(name, "").split(",")
        if value.strip()
    }


def allowed_origins() -> list[str]:
    """Return exact browser origins allowed to call the service."""
    return sorted(DEFAULT_ALLOWED_ORIGINS | _csv_env("FVSC_ALLOWED_ORIGINS"))


def allowed_hosts() -> list[str]:
    """Return HTTP Host values accepted by TrustedHostMiddleware."""
    return sorted(DEFAULT_ALLOWED_HOSTS | _csv_env("FVSC_ALLOWED_HOSTS"))


def origin_is_allowed(origin: str | None) -> bool:
    """Return whether a browser Origin may access the loopback service."""
    if not origin:
        return True
    return origin in allowed_origins() or re.fullmatch(LOOPBACK_ORIGIN_RE, origin) is not None


class BrowserOriginGuardMiddleware(BaseHTTPMiddleware):
    """Reject disallowed browser origins before an endpoint can mutate state.

    CORS response headers are not an authorization mechanism: browsers may still
    transmit simple cross-origin requests even when JavaScript cannot read the
    response. This guard turns the origin policy into an actual request check.
    Non-browser local clients commonly omit ``Origin`` and remain supported.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        origin = request.headers.get("origin")
        if not origin_is_allowed(origin):
            return JSONResponse(
                status_code=403,
                content={"detail": "Browser origin is not allowed"},
            )
        return await call_next(request)


def configure_security(app: FastAPI) -> None:
    """Attach restrictive browser, Origin, and Host-header middleware."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_origin_regex=LOOPBACK_ORIGIN_RE,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-FVSC-Token"],
        allow_credentials=False,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts(),
        www_redirect=False,
    )
    app.add_middleware(BrowserOriginGuardMiddleware)
