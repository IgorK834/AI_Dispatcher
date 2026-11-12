"""Cost profiles over HTTP: integer money, provenance, admin-only writes (FEAT-001 §6.2)."""

from pathlib import Path
from typing import Any

import pytest

from tests.factories import api_client, cost_profile, login, vehicle


@pytest.mark.ac("AC-FEAT-001-11")
def test_cost_profile_lifecycle_and_conflicts(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        response = client.post("/api/v1/cost-profiles", json=cost_profile())
        body = response.json()
        assert response.status_code == 201
        assert response.headers["Location"] == f"/api/v1/cost-profiles/{body['id']}"
        assert body["version"] == 1 and set(body["provenance"].values()) == {"user"}
        url = f"/api/v1/cost-profiles/{body['id']}"
        assert client.get(url).json() == body

        duplicate = client.post("/api/v1/cost-profiles", json=cost_profile())
        assert duplicate.status_code == 409 and duplicate.json()["code"] == "DUPLICATE_RESOURCE"

        updated = client.patch(url, json={"version": 1, "minProfitMinor": 20})
        assert updated.status_code == 200 and updated.json()["version"] == 2
        assert updated.json()["minProfitMinor"] == 20
        assert updated.json()["fuelPriceMinorPerL"] == body["fuelPriceMinorPerL"]
        stale = client.patch(url, json={"version": 1, "minProfitMinor": 30})
        assert stale.status_code == 409 and stale.json()["code"] == "VERSION_CONFLICT"
        assert client.get(url).json()["minProfitMinor"] == 20

        created_vehicle = client.post("/api/v1/vehicles", json=vehicle(body["id"]))
        assert created_vehicle.status_code == 201
        in_use = client.delete(url)
        assert in_use.status_code == 409 and in_use.json()["code"] == "COST_PROFILE_IN_USE"
        assert client.delete(f"/api/v1/vehicles/{created_vehicle.json()['id']}").status_code == 204

        assert client.delete(url).status_code == 204
        assert client.get(url).status_code == 404


@pytest.mark.ac("AC-FEAT-001-11")
@pytest.mark.parametrize(
    "field",
    [
        "fuelPriceMinorPerL",
        "driverCostMinorPerHour",
        "vehicleCostMinorPerKm",
        "accommodationMinor",
        "minProfitMinor",
    ],
)
@pytest.mark.parametrize("value", [12.5, "12", 1e3, True])
def test_money_fields_accept_only_integers(tmp_path: Path, field: str, value: Any) -> None:
    with api_client(tmp_path) as client:
        response = client.post("/api/v1/cost-profiles", json={**cost_profile(), field: value})
        assert response.status_code == 422 and response.json()["code"] == "VALIDATION_ERROR"
        assert client.get("/api/v1/cost-profiles").json()["items"] == []


@pytest.mark.ac("AC-FEAT-001-11")
def test_nested_money_is_integer_and_decimal_parameters_are_strings(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        for change in (
            {"perDiem": {"PL": 10.5}},
            {"tolls": {"perKm": {"DE": 0.25}, "annualVignettes": []}},
            {"minMarginPct": 0.2},
            {"fxRates": {"PLN": 4.25}},
            {"minMarginPct": "NaN"},
            {"fxRates": {"PLN": "0"}},
        ):
            response = client.post("/api/v1/cost-profiles", json={**cost_profile(), **change})
            assert response.status_code == 422, change


@pytest.mark.ac("AC-FEAT-001-11")
def test_patch_marks_only_changed_fields_as_user_provenance(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        created = client.post("/api/v1/cost-profiles", json=cost_profile()).json()
        url = f"/api/v1/cost-profiles/{created['id']}"
        response = client.patch(url, json={"version": 1, "accommodationMinor": 6000})
        # Provenance keys are the stored field names (snake_case), as in the seeded profile.
        assert response.json()["provenance"]["accommodation_minor"] == "user"
        assert client.patch(url, json={"version": 2, "fuelPriceMinorPerL": 1.5}).status_code == 422


@pytest.mark.ac("AC-FEAT-001-11")
def test_writes_are_admin_only_but_reads_are_open_to_any_login(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        created = client.post("/api/v1/cost-profiles", json=cost_profile()).json()
        client.cookies.clear()
        client.headers["X-CSRF-Token"] = login(client, "demo")
        assert client.get("/api/v1/cost-profiles").status_code == 200
        assert client.get(f"/api/v1/cost-profiles/{created['id']}").status_code == 200
        write = client.post("/api/v1/cost-profiles", json=cost_profile("Other"))
        assert write.status_code == 403 and write.json()["code"] == "FORBIDDEN"
        patch = client.patch(f"/api/v1/cost-profiles/{created['id']}", json={"version": 1})
        assert patch.status_code == 403
        assert client.delete(f"/api/v1/cost-profiles/{created['id']}").status_code == 403
