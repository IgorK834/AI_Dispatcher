"""Vehicles over HTTP: ranges, units, uniqueness and delete conflicts (FEAT-001 §6.1, §6.2)."""

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.factories import api_client, cost_profile, driver, vehicle


@pytest.mark.ac("AC-FEAT-001-10")
def test_vehicle_lifecycle_and_conflicts(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        profile_id = client.post("/api/v1/cost-profiles", json=cost_profile()).json()["id"]
        response = client.post("/api/v1/vehicles", json=vehicle(profile_id))
        body = response.json()
        assert response.status_code == 201
        assert response.headers["Location"] == f"/api/v1/vehicles/{body['id']}"
        assert body["version"] == 1 and body["fuel"]["provenance"] == "user"
        url = f"/api/v1/vehicles/{body['id']}"
        assert client.get(url).json() == body

        duplicate = client.post("/api/v1/vehicles", json=vehicle(profile_id))
        assert duplicate.status_code == 409 and duplicate.json()["code"] == "DUPLICATE_RESOURCE"

        updated = client.patch(url, json={"version": 1, "payloadKg": 1000})
        assert updated.status_code == 200 and updated.json()["version"] == 2
        assert updated.json()["payloadKg"] == 1000 and updated.json()["label"] == body["label"]
        stale = client.patch(url, json={"version": 1, "payloadKg": 900})
        assert stale.status_code == 409 and stale.json()["code"] == "VERSION_CONFLICT"
        assert client.get(url).json()["payloadKg"] == 1000

        linked = client.post("/api/v1/drivers", json=driver(0, vehicleId=body["id"])).json()
        blocked = client.delete(url)
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "VEHICLE_ASSIGNED_TO_DRIVER"
        assert client.delete(f"/api/v1/drivers/{linked['id']}").status_code == 204

        assert client.delete(url).status_code == 204
        missing = client.get(url)
        assert missing.status_code == 404 and missing.json()["code"] == "NOT_FOUND"
        assert client.get(f"/api/v1/vehicles/{uuid4()}").status_code == 404


@pytest.mark.ac("AC-FEAT-001-10")
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("gvwKg", 3600),
        ("payloadKg", 99),
        ("payloadKg", 2001),
        ("palletPlaces", 0),
        ("palletPlaces", 13),
        ("innerLengthM", "4.855"),
        ("vehicleType", "TRUCK"),
        ("bodyType", "TANKER"),
    ],
)
def test_out_of_range_values_are_422(tmp_path: Path, field: str, value: object) -> None:
    with api_client(tmp_path) as client:
        profile_id = client.post("/api/v1/cost-profiles", json=cost_profile()).json()["id"]
        response = client.post("/api/v1/vehicles", json={**vehicle(profile_id), field: value})
        assert response.status_code == 422 and response.json()["code"] == "VALIDATION_ERROR"
        assert client.get("/api/v1/vehicles").json()["items"] == []


@pytest.mark.ac("AC-FEAT-001-10")
def test_patch_is_validated_like_create(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        profile_id = client.post("/api/v1/cost-profiles", json=cost_profile()).json()["id"]
        created = client.post("/api/v1/vehicles", json=vehicle(profile_id)).json()
        url = f"/api/v1/vehicles/{created['id']}"
        assert client.patch(url, json={"version": 1, "gvwKg": 3600}).status_code == 422
        unknown_profile = client.patch(url, json={"version": 1, "costProfileId": str(uuid4())})
        assert unknown_profile.status_code == 404
        assert client.get(url).json()["version"] == 1


@pytest.mark.ac("AC-FEAT-001-10")
def test_unknown_cost_profile_on_create_is_404(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        response = client.post("/api/v1/vehicles", json=vehicle(str(uuid4())))
        assert response.status_code == 404 and response.json()["code"] == "NOT_FOUND"


@pytest.mark.ac("AC-FEAT-001-10")
def test_units_are_stored_as_millimetres_and_tenths_of_a_litre(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        profile_id = client.post("/api/v1/cost-profiles", json=cost_profile()).json()["id"]
        created = client.post("/api/v1/vehicles", json=vehicle(profile_id)).json()
        assert created["innerLengthM"] == "4.85" and created["fuel"]["lPer100kmFullAt90"] == "13.5"
        engine = client.app.state.services.fleet.engine
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT inner_length_mm, inner_width_mm, fuel_l_per_100km_empty_x10, "
                    "fuel_l_per_100km_full_x10 FROM vehicles WHERE id = :id"
                ),
                {"id": created["id"]},
            ).one()
        assert tuple(row) == (4850, 2100, 110, 135)


@pytest.mark.ac("AC-FEAT-001-10")
def test_fuel_with_more_precision_than_stored_is_rejected_not_truncated(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        profile_id = client.post("/api/v1/cost-profiles", json=cost_profile()).json()["id"]
        payload = vehicle(profile_id)
        payload["fuel"] = {**payload["fuel"], "lPer100kmFullAt90": "13.25"}
        response = client.post("/api/v1/vehicles", json=payload)
        assert response.status_code == 422 and response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.ac("AC-FEAT-001-10")
def test_filters(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        profile_id = client.post("/api/v1/cost-profiles", json=cost_profile()).json()["id"]
        ten = client.post("/api/v1/vehicles", json=vehicle(profile_id, "BUS-10")).json()
        six = client.post(
            "/api/v1/vehicles", json={**vehicle(profile_id, "BUS-6"), "palletPlaces": 6}
        ).json()
        client.post("/api/v1/drivers", json=driver(0, vehicleId=six["id"]))
        by_places = client.get("/api/v1/vehicles?palletPlaces=10").json()["items"]
        assert [item["id"] for item in by_places] == [ten["id"]]
        free = client.get("/api/v1/vehicles?unassigned=true").json()["items"]
        assert [item["id"] for item in free] == [ten["id"]]
        assert client.get("/api/v1/vehicles?unknown=1").status_code == 422
