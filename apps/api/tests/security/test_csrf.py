"""CSRF token and Origin allowlist on every state-changing request (FEAT-001 FR-12, FR-15)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.factories import ORIGIN, api_client, driver, login


def new_driver(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/drivers", json=driver(0))
    assert response.status_code == 201
    body: dict[str, object] = response.json()
    return body


@pytest.mark.ac("AC-FEAT-001-23")
def test_missing_wrong_or_foreign_csrf_token_is_refused_and_nothing_changes(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        created = new_driver(client)
        url = f"/api/v1/drivers/{created['id']}"
        good = client.headers["X-CSRF-Token"]

        # A second login (a client without its own lifespan) is another session.
        foreign = login(TestClient(client.app), "demo")
        assert foreign != good

        for label, headers in (
            ("missing", {"X-CSRF-Token": ""}),
            ("wrong", {"X-CSRF-Token": "0" * 64}),
            ("another session's", {"X-CSRF-Token": foreign}),
        ):
            for method, path, body in (
                ("POST", "/api/v1/drivers", driver(1)),
                ("PATCH", url, {"version": 1, "name": "Changed"}),
                ("DELETE", url, None),
            ):
                response = client.request(method, path, json=body, headers=headers)
                assert response.status_code == 403, (label, method)
                assert response.json()["code"] == "CSRF_FAILED", (label, method)

        # The header matches the cookie but was issued for another session: still refused.
        client.cookies.set("rp_csrf", foreign)
        forged = client.patch(
            url, json={"version": 1, "name": "Changed"}, headers={"X-CSRF-Token": foreign}
        )
        assert forged.status_code == 403 and forged.json()["code"] == "CSRF_FAILED"
        client.cookies.set("rp_csrf", good)

        # Nothing changed, and the correct token succeeds.
        assert client.get(url).json() == created
        assert len(client.get("/api/v1/drivers").json()["items"]) == 1
        ok = client.patch(url, json={"version": 1, "name": "Changed"})
        assert ok.status_code == 200 and ok.json()["name"] == "Changed"
        assert client.delete(url).status_code == 204


@pytest.mark.ac("AC-FEAT-001-23")
def test_logout_needs_the_token_too_but_safe_methods_do_not(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        refused = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": ""})
        assert refused.status_code == 403 and refused.json()["code"] == "CSRF_FAILED"
        assert client.get("/api/v1/auth/me", headers={"X-CSRF-Token": ""}).status_code == 200
        assert client.post("/api/v1/auth/logout").status_code == 204


@pytest.mark.ac("AC-FEAT-001-24")
def test_origin_outside_the_allowlist_or_missing_is_refused(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        created = new_driver(client)
        url = f"/api/v1/drivers/{created['id']}"
        del client.headers["Origin"]
        for origin in (None, "http://evil.example", ORIGIN + ".evil.example", "null"):
            headers = {"Origin": origin} if origin else {}
            for method, path, body in (
                ("POST", "/api/v1/drivers", driver(1)),
                ("PATCH", url, {"version": 1, "name": "Changed"}),
                ("DELETE", url, None),
                ("POST", "/api/v1/auth/logout", None),
            ):
                response = client.request(method, path, json=body, headers=headers)
                assert response.status_code == 403, (origin, method)
                assert response.json()["code"] == "ORIGIN_NOT_ALLOWED", (origin, method)
        assert client.get(url).json() == created
        allowed = client.patch(
            url, json={"version": 1, "name": "Changed"}, headers={"Origin": ORIGIN}
        )
        assert allowed.status_code == 200


@pytest.mark.ac("AC-FEAT-001-24")
def test_login_has_only_the_origin_check_and_preflight_needs_neither(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        settings = client.app.state.services.identity.settings
        body = {
            "email": settings.demo_email,
            "password": settings.demo_password,
            "captchaToken": "x",
        }
        bad_origin = client.post(
            "/api/v1/auth/login", json=body, headers={"Origin": "http://evil.example"}
        )
        assert bad_origin.status_code == 403 and bad_origin.json()["code"] == "ORIGIN_NOT_ALLOWED"
        no_csrf = client.post(
            "/api/v1/auth/login", json=body, headers={"Origin": ORIGIN, "X-CSRF-Token": ""}
        )
        assert no_csrf.status_code == 200
        preflight = client.options(
            "/api/v1/drivers",
            headers={"Origin": ORIGIN, "Access-Control-Request-Method": "PATCH"},
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == ORIGIN
