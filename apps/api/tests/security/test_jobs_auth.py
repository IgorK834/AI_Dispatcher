"""Authentication, CSRF and the per-user job limit on every FEAT-004 endpoint (section 6.1)."""

import re
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.factories import ORIGIN, api_client, login

ZERO = "00000000-0000-4000-8000-000000000000"
# (method, path, JSON body): every endpoint of FEAT-004 section 6.1.
ENDPOINTS = [
    ("POST", "/api/v1/optimization-jobs", {"scope": "fleet", "driverIds": []}),
    ("GET", f"/api/v1/optimization-jobs/{ZERO}", None),
    ("GET", f"/api/v1/optimization-jobs/{ZERO}/result", None),
    ("GET", f"/api/v1/route-plans/{ZERO}", None),
    ("GET", "/api/v1/assignments", None),
    ("POST", "/api/v1/assignments", {"routePlanId": ZERO}),
    ("GET", f"/api/v1/assignments/{ZERO}", None),
    ("DELETE", f"/api/v1/assignments/{ZERO}", None),
]
STATE_CHANGING = [e for e in ENDPOINTS if e[0] != "GET"]
# The worker would otherwise start the engine on the seeded fleet; queued jobs stay queued.
IDLE_WORKER = {"worker_poll_interval_ms": 3_600_000}


def job_count(client: TestClient) -> int:
    jobs = client.app.state.services.jobs
    with jobs.repository.session() as session:
        return len(session.scalars(select(jobs.repository.Job)).all())


@pytest.mark.ac("AC-FEAT-004-20")
def test_the_endpoint_list_is_the_one_the_application_serves(tmp_path: Path) -> None:
    with api_client(tmp_path, "dispatcher", settings_overrides=IDLE_WORKER) as client:
        served = {
            (method.upper(), path)
            for path, operations in client.app.openapi()["paths"].items()
            for method in operations
            if path.startswith(("/api/v1/optimization-jobs", "/api/v1/route-plans"))
            or path.startswith("/api/v1/assignments")
            if not path.endswith("/explanations")  # FEAT-006, not section 6.1 of FEAT-004
        }
    listed = {(method, path.replace(ZERO, "{id}")) for method, path, _body in ENDPOINTS}
    normalised = {(method, re.sub(r"\{[^}]+\}", "{id}", path)) for method, path in served}
    assert normalised == listed, "update ENDPOINTS when section 6.1 changes"


@pytest.mark.ac("AC-FEAT-004-20")
def test_anonymous_calls_are_refused_with_401(tmp_path: Path) -> None:
    with api_client(tmp_path, "dispatcher", settings_overrides=IDLE_WORKER) as client:
        anonymous = TestClient(client.app)
        anonymous.headers["Origin"] = ORIGIN
        for method, path, body in ENDPOINTS:
            response = anonymous.request(method, path, json=body)
            assert response.status_code == 401, (method, path)
            assert response.json()["code"] == "UNAUTHENTICATED", (method, path)
        assert job_count(client) == 0, "an anonymous request creates nothing"


@pytest.mark.ac("AC-FEAT-004-20")
def test_state_changing_calls_without_a_csrf_token_are_refused_with_403(tmp_path: Path) -> None:
    with api_client(tmp_path, "dispatcher", seeded=True, settings_overrides=IDLE_WORKER) as client:
        for method, path, body in STATE_CHANGING:
            for label, headers in (
                ("missing", {"X-CSRF-Token": ""}),
                ("wrong", {"X-CSRF-Token": "0" * 64}),
            ):
                response = client.request(method, path, json=body, headers=headers)
                assert response.status_code == 403, (label, method, path)
                assert response.json()["code"] == "CSRF_FAILED", (label, method, path)
        assert job_count(client) == 0, "a refused request creates nothing"
        for method, path, body in ENDPOINTS:
            if method == "GET":
                response = client.request(method, path, json=body)
                assert response.status_code in (200, 404), (method, path)


@pytest.mark.ac("AC-FEAT-004-20")
def test_the_fourth_simultaneous_job_of_one_user_is_limited_but_another_user_is_not(
    tmp_path: Path,
) -> None:
    with api_client(tmp_path, "dispatcher", seeded=True, settings_overrides=IDLE_WORKER) as client:
        body = {"scope": "fleet", "driverIds": []}
        for _ in range(3):
            created = client.post("/api/v1/optimization-jobs", json=body)
            assert created.status_code == 202
            assert client.get(created.headers["Location"]).json()["status"] == "queued"
        fourth = client.post("/api/v1/optimization-jobs", json=body)
        assert fourth.status_code == 429 and fourth.json()["code"] == "RATE_LIMITED"
        assert job_count(client) == 3, "the refused job is not stored"

        other = TestClient(client.app)
        other.headers.update({"Origin": ORIGIN, "X-CSRF-Token": login(other, "demo")})
        assert other.post("/api/v1/optimization-jobs", json=body).status_code == 202
        assert other.get(f"/api/v1/optimization-jobs/{uuid4()}").status_code == 404
