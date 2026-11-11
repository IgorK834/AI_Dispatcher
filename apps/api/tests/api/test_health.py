"""AC-FEAT-000-02: readiness reflects the actual migration head."""

from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient

from routepilot.main import create_app
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import migration_config


@pytest.mark.ac("AC-FEAT-000-02")
def test_health_and_readiness(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'health.db'}"
    settings = Settings(database_url=url)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["code"] == "NOT_READY"
        command.upgrade(migration_config(url), "head")
        assert client.get("/ready").json() == {"status": "ready", "migration": "0001_initial"}
        command.downgrade(migration_config(url), "base")
        assert client.get("/ready").status_code == 503


@pytest.mark.ac("AC-FEAT-000-02")
def test_request_id_and_unexpected_errors(tmp_path: Path) -> None:
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'errors.db'}"))

    @app.get("/broken")
    def broken() -> None:
        raise RuntimeError("internal details")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/broken", headers={"X-Request-ID": "test-request"})
        assert response.status_code == 500
        assert response.json()["requestId"] == "test-request"
        assert response.headers["X-Request-ID"] == "test-request"
        assert "internal details" not in response.text


@pytest.mark.ac("AC-FEAT-000-02")
def test_method_not_allowed_preserves_allow_header() -> None:
    with TestClient(create_app(Settings(database_url="sqlite://"))) as client:
        response = client.request("TRACE", "/health")
        assert response.status_code == 405
        assert response.headers["Allow"] == "GET"
        assert response.headers["content-type"] == "application/problem+json"
