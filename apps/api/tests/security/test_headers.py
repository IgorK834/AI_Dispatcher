"""Security headers on every JSON response (FEAT-001 FR-19)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.factories import ORIGIN, api_client, driver

STRICT_CSP = "default-src 'none'; frame-ancestors 'none'"


def assert_secured(response, *, csp: str = STRICT_CSP) -> None:
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Content-Security-Policy"] == csp


@pytest.mark.ac("AC-FEAT-001-34")
def test_success_and_error_json_responses_carry_the_headers(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        created = client.post("/api/v1/drivers", json=driver(0))
        responses = [
            client.get("/health"),
            client.get("/ready"),
            client.get("/api/v1/auth/me"),
            created,
            client.get(f"/api/v1/drivers/{created.json()['id']}"),
            client.get("/openapi.json"),
            # problem+json answers of every family
            client.get("/api/v1/drivers/00000000-0000-4000-8000-000000000000"),  # 404
            client.post("/api/v1/drivers", json={"unknown": 1}),  # 422
            client.patch(f"/api/v1/drivers/{created.json()['id']}", json={"version": 9}),  # 409
            client.post("/api/v1/drivers", json=driver(1), headers={"X-CSRF-Token": ""}),  # 403
            client.put("/api/v1/drivers"),  # 405
        ]
        client.cookies.clear()
        responses += [client.get("/api/v1/drivers"), client.post("/api/v1/nothing")]  # 401, 404
        assert {r.status_code for r in responses} >= {200, 201, 401, 403, 404, 405, 409, 422}
        for response in responses:
            assert_secured(response)


@pytest.mark.ac("AC-FEAT-001-34")
def test_an_unexpected_error_response_carries_the_headers(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        app = client.app

        @app.get("/boom")
        def boom() -> None:
            raise RuntimeError("internal details")

        response = TestClient(app, raise_server_exceptions=False).get("/boom")
        assert response.status_code == 500 and response.json()["code"] == "INTERNAL_ERROR"
        assert_secured(response)


@pytest.mark.ac("AC-FEAT-001-34")
def test_login_response_carries_the_headers_and_docs_are_the_only_relaxed_page(
    tmp_path: Path,
) -> None:
    with api_client(tmp_path) as client:
        rejected = client.post(
            "/api/v1/auth/login", json={}, headers={"Origin": "http://evil.example"}
        )
        assert_secured(rejected)
        docs = client.get("/docs", headers={"Origin": ORIGIN})
        assert docs.headers["X-Content-Type-Options"] == "nosniff"
        assert docs.headers["Referrer-Policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in docs.headers["Content-Security-Policy"]
        assert docs.headers["Content-Security-Policy"] != STRICT_CSP
