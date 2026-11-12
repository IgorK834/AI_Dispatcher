"""The documented API contract matches the behaviour the contract gate observes."""

import json
from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient

from routepilot.main import create_app
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import migration_config

ORIGIN = {"Origin": "http://localhost:3000"}


def client(tmp_path: Path) -> TestClient:
    url = f"sqlite:///{tmp_path / 'contract.db'}"
    command.upgrade(migration_config(url), "head")
    return TestClient(create_app(Settings(app_env="test", database_url=url, _env_file=None)))


@pytest.mark.ac("AC-FEAT-001-23")
def test_unsupported_method_is_405_with_every_supported_method_in_allow(tmp_path: Path) -> None:
    with client(tmp_path) as http:
        # No Origin header: the origin check must not mask the routing answer.
        response = http.put("/api/v1/agent/threads")
        assert response.status_code == 405
        assert response.headers["allow"] == "GET, POST"
        assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.ac("AC-FEAT-001-24")
def test_supported_state_changing_method_still_needs_an_allowed_origin(tmp_path: Path) -> None:
    with client(tmp_path) as http:
        refused = http.post("/api/v1/agent/threads", json={})
        assert refused.status_code == 403 and refused.json()["code"] == "ORIGIN_NOT_ALLOWED"
        # With an allowed Origin the next check (session) answers instead.
        unauthenticated = http.post("/api/v1/agent/threads", json={}, headers=ORIGIN)
        assert unauthenticated.status_code == 401
        assert unauthenticated.json()["code"] == "UNAUTHENTICATED"


@pytest.mark.ac("AC-FEAT-001-33")
@pytest.mark.parametrize(
    "path",
    ["/api/v1/auth/register", "/api/v1/auth/signup", "/api/v1/register", "/api/v1/users"],
)
def test_no_endpoint_registers_a_user(tmp_path: Path, path: str) -> None:
    with client(tmp_path) as http:
        paths = http.get("/openapi.json").json()["paths"]
        assert path not in paths
        assert not [p for p in paths if "regist" in p or "signup" in p]
        # An unknown path is answered by routing (404), with or without an Origin or session.
        for headers in ({}, ORIGIN):
            response = http.post(path, json={}, headers=headers)
            assert response.status_code == 404
            assert response.json()["code"] == "NOT_FOUND"


@pytest.mark.ac("AC-FEAT-000-07")
def test_contract_documents_problem_responses_without_defs(tmp_path: Path) -> None:
    with client(tmp_path) as http:
        schema = http.get("/openapi.json").json()
    assert "$defs" not in json.dumps(schema)  # oasdiff cannot load an inline $defs
    post = schema["paths"]["/api/v1/drivers"]["post"]["responses"]
    assert {"401", "403"} <= set(post)
    assert set(post["403"]["content"]) == {"application/problem+json"}
    assert set(schema["paths"]["/api/v1/auth/login"]["post"]["responses"]) >= {"401", "403", "429"}
