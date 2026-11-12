"""CORS behaves exactly as configured; credentials are allowed only for the allowlist."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from routepilot.main import create_app
from routepilot.shared.config import Settings
from tests.factories import ORIGIN, api_client, driver

EVIL = "http://evil.example"
PREFLIGHT = {
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type,x-csrf-token,idempotency-key",
}


def listed(value: str) -> set[str]:
    return {part.strip().lower() for part in value.split(",")}


@pytest.mark.ac("AC-FEAT-001-17")
def test_preflight_from_the_allowed_origin(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        response = client.options("/api/v1/drivers", headers={"Origin": ORIGIN, **PREFLIGHT})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ORIGIN
        assert response.headers["access-control-allow-credentials"] == "true"
        assert "POST" in listed(response.headers["access-control-allow-methods"]) | {
            m.upper() for m in listed(response.headers["access-control-allow-methods"])
        }
        assert {"content-type", "x-csrf-token", "idempotency-key"} <= listed(
            response.headers["access-control-allow-headers"]
        )
        # A preflight needs neither a session nor a CSRF token.
        anonymous = TestClient(client.app).options(
            "/api/v1/drivers", headers={"Origin": ORIGIN, **PREFLIGHT}
        )
        assert anonymous.status_code == 200


@pytest.mark.ac("AC-FEAT-001-18")
def test_foreign_origin_gets_no_cors_header_and_none_ever_gets_a_wildcard(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        created = client.post("/api/v1/drivers", json=driver(0)).json()
        anonymous = TestClient(client.app)
        responses = [
            anonymous.options("/api/v1/drivers", headers={"Origin": EVIL, **PREFLIGHT}),
            anonymous.get("/health", headers={"Origin": EVIL}),
            anonymous.get("/api/v1/drivers", headers={"Origin": EVIL}),
            anonymous.post("/api/v1/drivers", json={}, headers={"Origin": EVIL}),
        ]
        for response in responses:
            assert "access-control-allow-origin" not in response.headers, response.request.url
        every = [
            *responses,
            client.get("/health"),
            client.get("/health", headers={"Origin": ORIGIN}),
            client.get(f"/api/v1/drivers/{created['id']}"),
            client.get("/api/v1/drivers/00000000-0000-4000-8000-000000000000"),
            client.post("/api/v1/drivers", json={}),
            anonymous.get("/api/v1/drivers", headers={"Origin": ORIGIN}),
            anonymous.options("/api/v1/drivers", headers={"Origin": ORIGIN, **PREFLIGHT}),
            client.get("/openapi.json"),
        ]
        for response in every:
            assert response.headers.get("access-control-allow-origin") != "*"
        # The allowed origin is echoed exactly, also on an error response.
        error = anonymous.get("/api/v1/drivers", headers={"Origin": ORIGIN})
        assert error.status_code == 401
        assert error.headers["access-control-allow-origin"] == ORIGIN


@pytest.mark.ac("AC-FEAT-001-19")
@pytest.mark.parametrize("value", ["*", "http://localhost:3000,*", " * ", "https://*.example.com"])
def test_a_wildcard_origin_stops_the_startup(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="wildcard"):
        Settings(_env_file=None, cors_allowed_origins=value)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", value)
    with pytest.raises(ValidationError):
        create_app()


@pytest.mark.ac("AC-FEAT-001-19")
def test_an_empty_allowlist_is_refused_outside_tests() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="local", cors_allowed_origins="")
    assert Settings(_env_file=None, app_env="test", cors_allowed_origins="").origins == []
