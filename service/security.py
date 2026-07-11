"""Security helpers for the local FVSC HTTP service."""

from __future__ import annotations

import os
from urllib.parse import urlparse


DEFAULT_ALLOWED_ORIGINS = {
    "app://obsidian.md",
    "http://127.0.0.1",
    "http://localhost",
}


def allowed_origins() -> list[str]:
    extra = os.environ.get("FVSC_ALLOWED_ORIGINS", "")
    values = set(DEFAULT_ALLOWED_ORIGINS)
    values.update(x.strip() for x in extra.split(",") if x.strip())
    return sorted(values)


def allowed_hosts() -> set[str]:
    return {
        "127.0.0.1",
        "localhost",
        "[::1]",
    }


def origin_is_allowed(origin: str | None) -> bool:
    if not origin:
        return True
    parsed = urlparse(origin)
    normalized = f"{parsed.scheme}://{parsed.netloc}"
    return normalized in allowed_origins()
