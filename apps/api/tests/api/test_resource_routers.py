"""HTTP contract coverage for the fleet and manual-freight routes."""

import secrets
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from routepilot.fleet.api.routes import create_fleet_router
from routepilot.fleet.service import FleetService
from routepilot.freight.api.routes import create_freight_router
from routepilot.freight.service import FreightService
from routepilot.identity.api.routes import create_identity_router, require_role, require_user
from routepilot.identity.ports import CaptchaResult
from routepilot.identity.service import IdentityService
from routepilot.shared.clock import FixedClock
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import make_engine, migration_config
from routepilot.shared.errors import DomainError
from routepilot.shared.problem import problem


class Captcha:
    def verify(self, token: str, remote_ip: str | None) -> CaptchaResult:
        return CaptchaResult(True, [])


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    url = f"sqlite:///{tmp_path}/routers.db"
    command.upgrade(migration_config(url), "head")
    engine = make_engine(url)
    clock = FixedClock(datetime(2026, 11, 16, tzinfo=UTC))
    settings = Settings(_env_file=None, app_env="test", secret_key=secrets.token_hex(32))
    identity = IdentityService(engine, settings, clock, Captcha())
    identity.seed_accounts()
    fleet, freight = (
        FleetService(engine, clock, identity.audit),
        FreightService(engine, clock, identity.audit),
    )
    app = FastAPI()

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return problem(request, exc.status, exc.code, headers=exc.headers)

    app.include_router(create_identity_router(identity, settings))
    app.include_router(
        create_fleet_router(fleet, require_user(identity), require_role(identity, "admin"))
    )
    app.include_router(create_freight_router(freight, require_user(identity)))
    app.state.identity, app.state.fleet, app.state.freight = identity, fleet, freight
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/auth/login",
            json={
                "email": settings.admin_email,
                "password": settings.admin_password,
                "captchaToken": "pass",
            },
            headers={"Origin": settings.origins[0]},
        )
        assert response.status_code == 200
        yield test_client
    engine.dispose()


def cost() -> dict[str, object]:
    return {
        "name": "HTTP costs",
        "currency": "EUR",
        "fuelPriceMinorPerL": 181,
        "driverCostMinorPerHour": 1400,
        "vehicleCostMinorPerKm": 12,
        "accommodationMinor": 5500,
        "perDiem": {"PL": 1059},
        "tolls": {"perKm": {"DE": 0}, "annualVignettes": []},
        "fxRates": {"PLN": "4.25"},
        "minProfitMinor": 0,
        "minMarginPct": "0",
    }


def vehicle(profile_id: str) -> dict[str, object]:
    return {
        "label": "HTTP-BUS",
        "vehicleType": "VEHICLE_UP_TO_3_5_T",
        "bodyType": "CURTAIN_SIDER",
        "innerLengthM": "4.85",
        "innerWidthM": "2.10",
        "innerHeightM": "2.10",
        "palletPlaces": 10,
        "layoutTemplate": "EUR_MIXED_6X4",
        "sideAccess": "BOTH",
        "payloadKg": 1085,
        "gvwKg": 3500,
        "sleeperCab": False,
        "fuel": {
            "lPer100kmEmptyAt90": "11",
            "lPer100kmFullAt90": "13",
            "speedCurve": "VAN_DEFAULT_V1",
        },
        "costProfileId": profile_id,
    }


def driver(index: int = 0) -> dict[str, object]:
    return {
        "name": f"Fictional HTTP {index}",
        "homeCity": "Katowice" if index % 2 else "Wrocław",
        "homeCountry": "PL",
        "homeLat": 50.2649,
        "homeLon": 19.0238,
    }


def state(position: float = 50) -> dict[str, object]:
    return {
        "currentCity": "Katowice",
        "currentLat": position,
        "currentLon": 19,
        "availableFrom": "2026-11-16T08:00:00Z",
        **dict.fromkeys(
            (
                "workTodayMin",
                "driveTodayMin",
                "workSinceBreakMin",
                "driveSinceBreakMin",
                "workWeekMin",
                "driveWeekMin",
                "drivePrevWeekMin",
            ),
            0,
        ),
    }


def offer() -> dict[str, object]:
    return {
        "description": "HTTP synthetic load",
        "revenue": {"amountMinor": 15000, "currency": "EUR"},
        "weightKg": 500,
        "palletCount": 3,
        "palletType": "EUR_1200x800",
        "requiredBodyTypes": ["CURTAIN_SIDER"],
        "stops": [
            {
                "stopType": "LOADING",
                "city": "Katowice",
                "countryCode": "PL",
                "windowStart": "2026-11-16T08:00Z",
                "windowEnd": "2026-11-16T12:00Z",
            },
            {
                "stopType": "UNLOADING",
                "city": "Berlin",
                "countryCode": "DE",
                "windowStart": "2026-11-17T08:00Z",
                "windowEnd": "2026-11-17T12:00Z",
            },
        ],
    }


@pytest.mark.ac(
    "AC-FEAT-001-04",
    "AC-FEAT-001-05",
    "AC-FEAT-001-06",
    "AC-FEAT-001-07",
    "AC-FEAT-001-09",
    "AC-FEAT-001-15",
)
def test_driver_http_crud_pagination_and_state(client: TestClient) -> None:
    created = []
    for index in range(7):
        response = client.post("/api/v1/drivers", json=driver(index))
        assert response.status_code == 201 and response.headers["Location"].endswith(
            response.json()["id"]
        )
        created.append(response.json())
    ids, cursor = [], None
    for size in (3, 3, 1):
        response = client.get(
            "/api/v1/drivers", params={"limit": 3, **({"cursor": cursor} if cursor else {})}
        )
        assert response.status_code == 200 and len(response.json()["items"]) == size
        ids += [item["id"] for item in response.json()["items"]]
        cursor = response.json()["nextCursor"]
    assert len(set(ids)) == 7 and cursor is None
    assert all(
        item["homeCity"] == "Katowice"
        for item in client.get("/api/v1/drivers?homeCity=Katowice").json()["items"]
    )
    target = created[0]["id"]
    response = client.patch(
        f"/api/v1/drivers/{target}", json={"version": 1, "name": "Updated fictional name"}
    )
    assert response.status_code == 200 and response.json()["version"] == 2
    assert (
        client.patch(f"/api/v1/drivers/{target}", json={"version": 1, "name": "stale"}).status_code
        == 409
    )
    assert (
        client.post("/api/v1/drivers", json={**driver(), "homeLat": 123, "unknown": 1}).status_code
        == 422
    )
    assert client.get("/api/v1/drivers?unknown=1").status_code == 422
    assert client.post(f"/api/v1/drivers/{target}/state", json=state()).status_code == 201
    # Equal injected timestamps require a deterministic latest-state tie breaker.
    client.app.state.fleet.clock = FixedClock(datetime(2026, 11, 16, 0, 1, tzinfo=UTC))
    second = client.post(f"/api/v1/drivers/{target}/state", json=state(51))
    assert second.status_code == 201 and second.headers["Location"].endswith("/state")
    states = client.get(f"/api/v1/drivers/{target}/state").json()["items"]
    assert len(states) == 2 and states[0]["id"] == second.json()["id"]
    assert client.get(f"/api/v1/drivers/{target}").json()["state"]["currentLat"] == 51
    assert (
        client.post(
            f"/api/v1/drivers/{target}/state", json={**state(), "driveWeekMin": -1}
        ).status_code
        == 422
    )
    assert client.delete(f"/api/v1/drivers/{target}").status_code == 204
    assert client.get(f"/api/v1/drivers/{target}").status_code == 404
    assert client.get(f"/api/v1/drivers/{uuid4()}").status_code == 404


@pytest.mark.ac("AC-FEAT-001-10", "AC-FEAT-001-11", "AC-FEAT-001-27")
def test_vehicle_profile_crud_and_permission_matrix(client: TestClient) -> None:
    response = client.post("/api/v1/cost-profiles", json=cost())
    assert response.status_code == 201 and response.headers["Location"].endswith(
        response.json()["id"]
    )
    profile_id = response.json()["id"]
    assert client.post("/api/v1/cost-profiles", json=cost()).status_code == 409
    assert (
        client.post("/api/v1/cost-profiles", json={**cost(), "fuelPriceMinorPerL": 1.2}).status_code
        == 422
    )
    assert client.get("/api/v1/cost-profiles").json()["items"]
    assert client.get(f"/api/v1/cost-profiles/{profile_id}").status_code == 200
    response = client.post("/api/v1/vehicles", json=vehicle(profile_id))
    assert response.status_code == 201 and response.headers["Location"].endswith(
        response.json()["id"]
    )
    vehicle_id = response.json()["id"]
    assert (
        response.json()["innerLengthM"] == "4.85"
        and response.json()["fuel"]["provenance"] == "user"
    )
    assert client.post("/api/v1/vehicles", json=vehicle(profile_id)).status_code == 409
    assert (
        client.post("/api/v1/vehicles", json={**vehicle(profile_id), "gvwKg": 3600}).status_code
        == 422
    )
    assert (
        client.get("/api/v1/vehicles?palletPlaces=10&unassigned=true").json()["items"][0]["id"]
        == vehicle_id
    )
    assert client.get(f"/api/v1/vehicles/{vehicle_id}").status_code == 200
    updated = client.patch(f"/api/v1/vehicles/{vehicle_id}", json={"version": 1, "payloadKg": 1000})
    assert updated.status_code == 200 and updated.json()["version"] == 2
    assert (
        client.patch(
            f"/api/v1/vehicles/{vehicle_id}", json={"version": 1, "payloadKg": 1000}
        ).status_code
        == 409
    )
    assert client.delete(f"/api/v1/cost-profiles/{profile_id}").status_code == 409
    linked = client.post("/api/v1/drivers", json={**driver(), "vehicleId": vehicle_id}).json()["id"]
    assert client.delete(f"/api/v1/vehicles/{vehicle_id}").status_code == 409
    assert not client.get("/api/v1/vehicles?unassigned=true").json()["items"]
    assert client.delete(f"/api/v1/drivers/{linked}").status_code == 204
    assert client.delete(f"/api/v1/vehicles/{vehicle_id}").status_code == 204
    assert client.get(f"/api/v1/vehicles/{vehicle_id}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/cost-profiles/{profile_id}", json={"version": 1, "minProfitMinor": 20}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/cost-profiles/{profile_id}", json={"version": 1, "minProfitMinor": 30}
        ).status_code
        == 409
    )
    assert client.delete(f"/api/v1/cost-profiles/{profile_id}").status_code == 204
    identity = client.app.state.identity
    settings = identity.settings
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.demo_email,
            "password": settings.demo_password,
            "captchaToken": "pass",
        },
        headers={"Origin": settings.origins[0]},
    )
    assert response.status_code == 200
    assert client.post("/api/v1/cost-profiles", json=cost()).status_code == 403
    assert client.post("/api/v1/drivers", json=driver()).status_code == 201
    client.cookies.clear()
    assert client.get("/api/v1/drivers").status_code == 401


@pytest.mark.ac("AC-FEAT-001-12", "AC-FEAT-001-13", "AC-FEAT-001-14")
def test_manual_offer_http_contract(client: TestClient) -> None:
    response = client.post("/api/v1/freight-offers", json=offer())
    assert response.status_code == 201 and response.headers["Location"].endswith(
        response.json()["id"]
    )
    data = response.json()
    assert data["source"] == "manual" and not data["isSynthetic"] and data["completenessScore"] == 1
    assert "requiredEquipment" not in data
    offer_id = data["id"]
    assert client.get(f"/api/v1/freight-offers/{offer_id}").status_code == 200
    assert (
        client.get(
            "/api/v1/freight-offers?originCountry=PL&hasPrice=true&minCompleteness=1"
        ).json()["items"][0]["id"]
        == offer_id
    )
    assert not client.get("/api/v1/freight-offers?destinationCountry=FR").json()["items"]
    assert client.get("/api/v1/freight-offers?unknown=1").status_code == 422
    assert (
        client.post("/api/v1/freight-offers", json={**offer(), "source": "mock"}).status_code == 422
    )
    response = client.patch(
        f"/api/v1/freight-offers/{offer_id}", json={"version": 1, "weightKg": 450}
    )
    assert response.status_code == 200 and response.json()["version"] == 2
    assert (
        client.patch(
            f"/api/v1/freight-offers/{offer_id}", json={"version": 1, "weightKg": 550}
        ).status_code
        == 409
    )
    assert client.delete(f"/api/v1/freight-offers/{offer_id}").status_code == 204
    assert client.get(f"/api/v1/freight-offers/{offer_id}").json()["status"] == "withdrawn"
    assert client.get(f"/api/v1/freight-offers/{uuid4()}").status_code == 404


@pytest.mark.ac("AC-FEAT-001-09", "AC-FEAT-001-14")
def test_datetime_filters_and_decimal_values_reject_invalid_input(client: TestClient) -> None:
    assert client.get("/api/v1/drivers?availableBefore=2026-11-16T10:00:00").status_code == 422
    assert client.get("/api/v1/freight-offers?pickupFrom=2026-11-16T10:00:00").status_code == 422
    assert (
        client.post(
            "/api/v1/cost-profiles", json={**cost(), "fxRates": {"PLN": "not-a-number"}}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/v1/cost-profiles", json={**cost(), "minMarginPct": "NaN"}).status_code
        == 422
    )
