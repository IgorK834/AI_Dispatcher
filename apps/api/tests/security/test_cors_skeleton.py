"""AC-FEAT-000-03: explicit credentialed CORS."""

import pytest
from fastapi.testclient import TestClient

from routepilot.main import create_app
from routepilot.shared.config import Settings


@pytest.mark.ac("AC-FEAT-000-03")
@pytest.mark.parametrize(
    "origin, allowed", [("http://localhost:3000", True), ("http://evil.example", False)]
)
def test_preflight(origin: str, allowed: bool) -> None:
    with TestClient(create_app(Settings(database_url="sqlite://"))) as client:
        response = client.options(
            "/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
        )
        if allowed:
            assert response.headers["access-control-allow-origin"] == origin
            assert response.headers["access-control-allow-credentials"] == "true"
        else:
            assert "access-control-allow-origin" not in response.headers
