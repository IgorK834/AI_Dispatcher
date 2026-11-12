"""Every error of the API is one problem+json shape with a traceable requestId (FR-11)."""

import json
import secrets
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from fastapi.testclient import TestClient

from routepilot.main import create_app
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import migration_config
from tests.factories import ORIGIN, api_client, cost_profile, driver, login

SHAPE = {"type", "title", "status", "code", "requestId"}


def log_lines(captured: str) -> list[dict[str, Any]]:
    lines = []
    for line in captured.splitlines():
        try:
            lines.append(json.loads(line))
        except ValueError:
            continue
    return lines


def assert_problem(response: Any, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert SHAPE <= set(body), body
    assert body["status"] == status and body["code"] == code
    assert body["requestId"] and body["requestId"] == response.headers["X-Request-ID"]


@pytest.mark.ac("AC-FEAT-001-16")
def test_every_error_family_is_problem_json_with_a_log_correlated_request_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with api_client(tmp_path, "admin") as client:
        app = client.app

        @app.get("/boom")
        def boom() -> None:
            raise RuntimeError("secret internal detail")

        created = client.post("/api/v1/drivers", json=driver(0)).json()
        url = f"/api/v1/drivers/{created['id']}"
        no_session = TestClient(app)
        crashing = TestClient(app, raise_server_exceptions=False)

        demo = TestClient(app)
        demo.headers.update({"Origin": ORIGIN, "X-CSRF-Token": login(demo, "demo")})

        cases = [
            (no_session.get("/api/v1/drivers"), 401, "UNAUTHENTICATED"),
            (demo.post("/api/v1/cost-profiles", json=cost_profile()), 403, "FORBIDDEN"),
            (client.get("/api/v1/drivers/00000000-0000-4000-8000-000000000000"), 404, "NOT_FOUND"),
            (
                client.patch(url, json={"version": 99, "name": "x"}),
                409,
                "VERSION_CONFLICT",
            ),
            (client.post("/api/v1/drivers", json={"nope": 1}), 422, "VALIDATION_ERROR"),
            (crashing.get("/boom"), 500, "INTERNAL_ERROR"),
        ]
        settings = app.state.services.identity.settings
        body = {"email": settings.demo_email, "password": "wrong-password", "captchaToken": "x"}
        limited = None
        for _ in range(7):
            limited = TestClient(app).post(
                "/api/v1/auth/login", json=body, headers={"Origin": ORIGIN}
            )
            if limited.status_code == 429:
                break
        assert limited is not None
        cases.append((limited, 429, "RATE_LIMITED"))
        assert limited.headers["Retry-After"]

        captured = log_lines(capsys.readouterr().out)
        logged = {
            (line["request_id"], line["status"])
            for line in captured
            if line.get("event") == "request_finished"
        }
        for response, status, code in cases:
            assert_problem(response, status, code)
            assert (response.json()["requestId"], status) in logged, (code, "not in the log")
        assert "secret internal detail" not in cases[-2][0].text


@pytest.mark.ac("AC-FEAT-001-16")
def test_a_forced_500_has_no_stack_trace_in_demo(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'demo.db'}"
    command.upgrade(migration_config(url), "head")
    settings = Settings(
        _env_file=None,
        app_env="demo",
        database_url=url,
        agents_db_path=str(tmp_path / "agents.db"),
        secret_key=secrets.token_hex(32),
        admin_password=secrets.token_hex(16),
        demo_password=secrets.token_hex(16),
        turnstile_site_key="prod-site-key",
        turnstile_secret_key=secrets.token_hex(16),
    )
    app = create_app(settings)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")
    assert_problem(response, 500, "INTERNAL_ERROR")
    for leaked in ("Traceback", "RuntimeError", "secret internal detail", ".py", 'File "'):
        assert leaked not in response.text, leaked


@pytest.mark.ac("AC-FEAT-001-16")
def test_login_failures_share_the_problem_shape(tmp_path: Path) -> None:
    with api_client(tmp_path, "admin") as client:
        anonymous = TestClient(client.app)
        settings = client.app.state.services.identity.settings
        wrong = anonymous.post(
            "/api/v1/auth/login",
            json={"email": settings.demo_email, "password": "wrong-password", "captchaToken": "x"},
            headers={"Origin": ORIGIN},
        )
        assert_problem(wrong, 401, "INVALID_CREDENTIALS")
        origin = anonymous.post("/api/v1/auth/login", json={}, headers={"Origin": "http://evil"})
        assert_problem(origin, 403, "ORIGIN_NOT_ALLOWED")
