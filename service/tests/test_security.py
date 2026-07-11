from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from service.security import (
    allowed_hosts,
    allowed_origins,
    configure_security,
    origin_is_allowed,
)


def _client() -> TestClient:
    app = FastAPI()
    configure_security(app)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    @app.post("/mutate")
    async def mutate():
        return {"mutated": True}

    return TestClient(app, base_url="http://127.0.0.1")


def test_obsidian_origin_is_allowed() -> None:
    response = _client().options(
        "/ping",
        headers={
            "Origin": "app://obsidian.md",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "app://obsidian.md"


def test_loopback_origin_with_port_is_allowed() -> None:
    response = _client().options(
        "/ping",
        headers={
            "Origin": "http://127.0.0.1:8765",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:8765"


def test_arbitrary_web_origin_is_rejected() -> None:
    response = _client().options(
        "/ping",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 403
    assert "access-control-allow-origin" not in response.headers


def test_simple_cross_origin_post_never_reaches_endpoint() -> None:
    response = _client().post(
        "/mutate",
        headers={
            "Origin": "https://attacker.example",
            "Content-Type": "text/plain",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Browser origin is not allowed"}


def test_non_browser_local_client_remains_supported() -> None:
    response = _client().post("/mutate")

    assert response.status_code == 200
    assert response.json() == {"mutated": True}


def test_untrusted_host_is_rejected() -> None:
    response = _client().get("/ping", headers={"Host": "attacker.example"})

    assert response.status_code == 400


def test_environment_overrides_are_explicit(monkeypatch) -> None:
    monkeypatch.setenv("FVSC_ALLOWED_ORIGINS", "https://trusted.example")
    monkeypatch.setenv("FVSC_ALLOWED_HOSTS", "fvsc.test")

    assert "https://trusted.example" in allowed_origins()
    assert "fvsc.test" in allowed_hosts()
    assert origin_is_allowed("https://trusted.example")
    assert not origin_is_allowed("https://attacker.example")
