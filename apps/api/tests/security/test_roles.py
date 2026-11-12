"""Permission matrix of FEAT-001 §6.5 over every endpoint, built from the router list."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.factories import ORIGIN, api_client, login

ZERO = "00000000-0000-4000-8000-000000000000"
ROLES = ("admin", "dispatcher", "demo")
LEVEL = {"anonymous": 0, "demo": 1, "dispatcher": 2, "admin": 3}

# (method, path template) -> minimum role, exactly as in FEAT-001 §6.2 ("Auth" column) and §6.5.
# `demo` = any logged-in role; drivers, vehicles and manual offers are writable by every role;
# cost profiles are writable by `admin` only.
MATRIX: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/auth/logout"): "demo",
    ("GET", "/api/v1/auth/me"): "demo",
    ("GET", "/api/v1/drivers"): "demo",
    ("POST", "/api/v1/drivers"): "demo",
    ("GET", "/api/v1/drivers/{driver_id}"): "demo",
    ("PATCH", "/api/v1/drivers/{driver_id}"): "demo",
    ("DELETE", "/api/v1/drivers/{driver_id}"): "demo",
    ("GET", "/api/v1/drivers/{driver_id}/state"): "demo",
    ("POST", "/api/v1/drivers/{driver_id}/state"): "demo",
    ("GET", "/api/v1/vehicles"): "demo",
    ("POST", "/api/v1/vehicles"): "demo",
    ("GET", "/api/v1/vehicles/{vehicle_id}"): "demo",
    ("PATCH", "/api/v1/vehicles/{vehicle_id}"): "demo",
    ("DELETE", "/api/v1/vehicles/{vehicle_id}"): "demo",
    ("GET", "/api/v1/cost-profiles"): "demo",
    ("POST", "/api/v1/cost-profiles"): "admin",
    ("GET", "/api/v1/cost-profiles/{profile_id}"): "demo",
    ("PATCH", "/api/v1/cost-profiles/{profile_id}"): "admin",
    ("DELETE", "/api/v1/cost-profiles/{profile_id}"): "admin",
    ("GET", "/api/v1/freight-offers"): "demo",
    ("POST", "/api/v1/freight-offers"): "demo",
    ("GET", "/api/v1/freight-offers/{offer_id}"): "demo",
    ("PATCH", "/api/v1/freight-offers/{offer_id}"): "demo",
    ("DELETE", "/api/v1/freight-offers/{offer_id}"): "demo",
}
PUBLIC = {("GET", "/api/v1/auth/captcha-config"), ("POST", "/api/v1/auth/login")}
# Endpoints of later features join the full matrix in their own slices. Until then they must at
# least refuse anonymous callers, and `/admin/*` must refuse every non-admin role (§6.5).
LATER = ("/api/v1/admin/", "/api/v1/agent/", "/api/v1/assignments", "/api/v1/optimization-jobs")
LATER_EXACT = ("/api/v1/route-plans/",)


def api_routes(app: Any) -> list[tuple[str, str]]:
    """Every method and path the application serves, read from the generated schema."""
    return sorted(
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/api/v1/")
        for method in operations
    )


def is_later(path: str) -> bool:
    return path.startswith(LATER) or path.startswith(LATER_EXACT)


def fill(path: str) -> str:
    out = path
    while "{" in out:
        start, end = out.index("{"), out.index("}")
        out = out[:start] + ZERO + out[end + 1 :]
    return out


@pytest.fixture(scope="module")
def sessions(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, TestClient]]:
    with api_client(tmp_path_factory.mktemp("roles"), "admin", seeded=True) as admin:
        clients = {"admin": admin}
        for role in ("dispatcher", "demo"):
            client = TestClient(admin.app)
            client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": login(client, role)})
            clients[role] = client
        anonymous = TestClient(admin.app)
        anonymous.headers["Origin"] = ORIGIN
        clients["anonymous"] = anonymous
        yield clients


def call(client: TestClient, method: str, path: str) -> Any:
    body = {} if method in {"POST", "PATCH", "PUT"} else None
    return client.request(method, fill(path), json=body)


@pytest.mark.ac("AC-FEAT-001-27")
def test_every_endpoint_has_an_expectation(sessions: dict[str, TestClient]) -> None:
    unexplained = [
        (method, path)
        for method, path in api_routes(sessions["admin"].app)
        if (method, path) not in MATRIX and (method, path) not in PUBLIC and not is_later(path)
    ]
    assert not unexplained, f"add these endpoints to the permission matrix: {unexplained}"
    stale = [key for key in MATRIX if key not in api_routes(sessions["admin"].app)]
    assert not stale, f"the matrix lists endpoints that no longer exist: {stale}"


@pytest.mark.ac("AC-FEAT-001-27")
@pytest.mark.parametrize(("method", "path"), sorted(MATRIX))
@pytest.mark.parametrize("role", ["anonymous", *ROLES])
def test_role_gets_exactly_the_permissions_of_the_matrix(
    sessions: dict[str, TestClient], role: str, method: str, path: str
) -> None:
    client = sessions[role]
    if path.endswith("/auth/logout") and role != "anonymous":
        client = TestClient(client.app)  # logging out ends a session: use a fresh one
        client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": login(client, role)})
    response = call(client, method, path)
    if role == "anonymous":
        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHENTICATED"
    elif LEVEL[role] < LEVEL[MATRIX[(method, path)]]:
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"
    else:
        # Authorised: the request reaches the handler (an unknown id or an empty body is then
        # answered by the handler itself, never by the permission check).
        assert response.status_code not in (401, 403), response.text


@pytest.mark.ac("AC-FEAT-001-27")
def test_public_endpoints_need_no_session(sessions: dict[str, TestClient]) -> None:
    assert sessions["anonymous"].get("/api/v1/auth/captcha-config").status_code == 200
    login_response = sessions["anonymous"].post("/api/v1/auth/login", json={})
    assert login_response.status_code == 422  # reached validation, not refused for the session


@pytest.mark.ac("AC-FEAT-001-27")
def test_later_feature_endpoints_refuse_anonymous_and_admin_endpoints_refuse_non_admins(
    sessions: dict[str, TestClient],
) -> None:
    later = [(m, p) for m, p in api_routes(sessions["admin"].app) if is_later(p)]
    assert later
    for method, path in later:
        assert call(sessions["anonymous"], method, path).status_code == 401, (method, path)
        if path.startswith("/api/v1/admin/"):
            for role in ("dispatcher", "demo"):
                response = call(sessions[role], method, path)
                assert response.status_code == 403, (role, method, path)
                assert response.json()["code"] == "FORBIDDEN"
            assert call(sessions["admin"], method, path).status_code not in (401, 403)
