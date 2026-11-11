"""Structured validation and retry details at the problem+json boundary."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from routepilot.main import create_app
from routepilot.shared.config import Settings
from routepilot.shared.errors import DomainError


@pytest.mark.ac("AC-FEAT-001-16", "AC-FEAT-001-28")
def test_domain_problem_preserves_safe_details_and_retry_header() -> None:
    app = create_app(Settings(app_env="test", database_url="sqlite:///:memory:"))

    @app.get("/rate-probe")
    def limited() -> None:
        raise DomainError(
            "RATE_LIMITED",
            429,
            headers={"Retry-After": "60"},
            errors=[{"field": "email", "message": "Rate limit reached"}],
        )

    response = TestClient(app).get("/rate-probe")
    assert response.status_code == 429
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["Retry-After"] == "60"
    assert response.json()["errors"] == [{"field": "email", "message": "Rate limit reached"}]
    assert response.json()["requestId"] == response.headers["X-Request-ID"]


@pytest.mark.ac("AC-FEAT-001-09", "AC-FEAT-001-16")
def test_validation_details_name_fields_without_echoing_input() -> None:
    class Probe(BaseModel):
        model_config = ConfigDict(extra="forbid")
        homeLat: float = Field(ge=-90, le=90)

    app = create_app(Settings(app_env="test", database_url="sqlite:///:memory:"))

    @app.post("/validation-probe")
    def validate(body: Probe) -> Probe:
        return body

    response = TestClient(app).post(
        "/validation-probe", json={"homeLat": 123, "unknown": "private-input-sentinel"}
    )
    assert response.status_code == 422
    assert {item["field"] for item in response.json()["errors"]} == {"body.homeLat", "body.unknown"}
    assert "private-input-sentinel" not in response.text
