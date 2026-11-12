"""Audit trail: who did what, without secrets (FEAT-001 FR-18)."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.factories import ORIGIN, api_client, driver


def audit_rows(client: TestClient) -> list[dict[str, Any]]:
    engine = client.app.state.services.fleet.engine
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT at, actor, action, entity_type, entity_id, diff "
                "FROM audit_events ORDER BY at, rowid"
            )
        ).mappings()
        return [dict(row) for row in rows]


@pytest.mark.ac("AC-FEAT-001-30")
def test_login_failed_login_and_driver_changes_leave_five_rows_without_secrets(
    tmp_path: Path,
) -> None:
    with api_client(tmp_path, "admin") as client:
        identity = client.app.state.services.identity
        settings = identity.settings
        engine = identity.engine
        with engine.connect() as connection:
            admin_id = connection.execute(
                text("SELECT id FROM users WHERE email = :e"), {"e": settings.admin_email}
            ).scalar_one()
        # `api_client` already logged in once (the successful login). One failed login:
        wrong = "not-the-password-xyz"
        failed = TestClient(client.app).post(
            "/api/v1/auth/login",
            json={
                "email": settings.admin_email,
                "password": wrong,
                "captchaToken": "captcha-secret",
            },
            headers={"Origin": ORIGIN},
        )
        assert failed.status_code == 401
        created = client.post("/api/v1/drivers", json=driver(0)).json()
        url = f"/api/v1/drivers/{created['id']}"
        assert (
            client.patch(url, json={"version": 1, "name": "Renamed Fictional"}).status_code == 200
        )
        assert client.delete(url).status_code == 204

        rows = audit_rows(client)
        assert [row["action"] for row in rows] == [
            "auth.login",
            "auth.login_failed",
            "driver.created",
            "driver.updated",
            "driver.deleted",
        ]
        login_row, failed_row, created_row, updated_row, deleted_row = rows
        assert (login_row["actor"], login_row["entity_type"]) == (admin_id, "user")
        assert login_row["entity_id"] == admin_id
        assert (failed_row["actor"], failed_row["entity_type"]) == ("anonymous", "user")
        for row, action in (
            (created_row, "created"),
            (updated_row, "updated"),
            (deleted_row, "deleted"),
        ):
            assert row["actor"] == admin_id and row["entity_type"] == "driver"
            assert row["entity_id"] == created["id"], action
            assert row["at"] is not None
        assert "Renamed Fictional" in json.dumps(updated_row["diff"])  # non-secret values kept

        secrets_in_play = [
            wrong,
            "captcha-secret",
            settings.admin_password,
            settings.demo_password,
            settings.secret_key,
            client.cookies["rp_session"],
            client.headers["X-CSRF-Token"],
        ]
        with engine.connect() as connection:
            hashes = [
                value for (value,) in connection.execute(text("SELECT password_hash FROM users"))
            ] + [value for (value,) in connection.execute(text("SELECT token_hash FROM sessions"))]
        blob = json.dumps(rows, default=str).lower()
        for secret in [*secrets_in_play, *hashes]:
            assert secret.lower() not in blob, "a secret value reached audit_events"
        for word in ("password", "argon2", "token", "hash"):
            assert word not in blob.replace("login_failed", ""), word


@pytest.mark.ac("AC-FEAT-001-30")
def test_logout_is_audited_too(tmp_path: Path) -> None:
    with api_client(tmp_path, "admin") as client:
        assert client.post("/api/v1/auth/logout").status_code == 204
        assert [row["action"] for row in audit_rows(client)] == ["auth.login", "auth.logout"]
