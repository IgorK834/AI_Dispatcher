"""Drivers over HTTP on the real application (FEAT-001 §6.2)."""

from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.factories import api_client, cost_profile, driver, driver_state, vehicle


class FakeUsage:
    def __init__(self, answer: Literal["none", "historical", "active"]) -> None:
        self.answer = answer

    def assignment_usage(self, driver_id: UUID) -> Literal["none", "historical", "active"]:
        return self.answer


def create_driver(client: TestClient, index: int = 0, **extra: object) -> dict[str, object]:
    response = client.post("/api/v1/drivers", json=driver(index, **extra))
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


@pytest.mark.ac("AC-FEAT-001-04")
def test_create_returns_201_location_and_version_one(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        response = client.post("/api/v1/drivers", json=driver(0))
        body = response.json()
        assert response.status_code == 201
        assert response.headers["Location"] == f"/api/v1/drivers/{body['id']}"
        assert body["version"] == 1
        assert body["defaultRulesProfile"] == "pl_domestic_employee_v1"
        assert body["isSynthetic"] is False
        assert body["vehicle"] is None and body["state"] is None


@pytest.mark.ac("AC-FEAT-001-05")
def test_cursor_pagination_filters_and_tampering(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        for index in range(7):
            create_driver(client, index)
        ids: list[str] = []
        cursor: str | None = None
        for size in (3, 3, 1):
            params: dict[str, object] = {"limit": 3, **({"cursor": cursor} if cursor else {})}
            page = client.get("/api/v1/drivers", params=params).json()
            assert len(page["items"]) == size
            ids += [item["id"] for item in page["items"]]
            cursor = page["nextCursor"]
        assert len(set(ids)) == 7 and cursor is None

        katowice = client.get("/api/v1/drivers?homeCity=Katowice").json()["items"]
        assert katowice and all(item["homeCity"] == "Katowice" for item in katowice)

        first = client.get("/api/v1/drivers?limit=3").json()["nextCursor"]
        other_filter = client.get("/api/v1/drivers", params={"cursor": first, "homeCity": "Opole"})
        assert other_filter.status_code == 422
        tampered = client.get("/api/v1/drivers", params={"cursor": first[:-2] + "AA"})
        assert tampered.status_code == 422


@pytest.mark.ac("AC-FEAT-001-06")
def test_get_embeds_vehicle_and_newest_state_and_unknown_is_404(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        profile = client.post("/api/v1/cost-profiles", json=cost_profile()).json()
        van = client.post("/api/v1/vehicles", json=vehicle(profile["id"])).json()
        created = create_driver(client, 0, vehicleId=van["id"])
        driver_id = created["id"]
        client.post(f"/api/v1/drivers/{driver_id}/state", json=driver_state(50.0))
        newest = client.post(f"/api/v1/drivers/{driver_id}/state", json=driver_state(51.5))
        body = client.get(f"/api/v1/drivers/{driver_id}").json()
        assert body["vehicle"]["id"] == van["id"] and body["vehicle"]["label"] == "FACTORY-BUS"
        assert body["state"]["id"] == newest.json()["id"] and body["state"]["currentLat"] == 51.5

        missing = client.get(f"/api/v1/drivers/{uuid4()}")
        assert missing.status_code == 404 and missing.json()["code"] == "NOT_FOUND"


@pytest.mark.ac("AC-FEAT-001-07")
def test_patch_bumps_version_and_a_stale_patch_changes_nothing(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        before = create_driver(client, 0)
        url = f"/api/v1/drivers/{before['id']}"
        first = client.patch(url, json={"version": 1, "name": "Renamed Fictional"})
        assert first.status_code == 200
        after = first.json()
        changed = {key for key in after if after[key] != before[key]}
        assert changed == {"name", "version", "updatedAt"} or changed == {"name", "version"}
        assert after["name"] == "Renamed Fictional" and after["version"] == 2

        stale = client.patch(url, json={"version": 1, "name": "Stale write"})
        assert stale.status_code == 409 and stale.json()["code"] == "VERSION_CONFLICT"
        assert client.get(url).json() == after

        bare = client.patch(url, json={"version": 2})
        assert bare.status_code == 200 and bare.json()["version"] == 3


@pytest.mark.ac("AC-FEAT-001-08")
@pytest.mark.parametrize("answer", ["none", "historical", "active"])
def test_delete_follows_the_usage_checker(tmp_path: Path, answer: str) -> None:
    with api_client(tmp_path) as client:
        fleet = client.app.state.services.fleet
        fleet.usage_checker = FakeUsage(answer)
        created = create_driver(client, 0)
        url = f"/api/v1/drivers/{created['id']}"
        response = client.delete(url)
        if answer == "active":
            assert response.status_code == 409
            assert response.json()["code"] == "DRIVER_HAS_ACTIVE_ASSIGNMENT"
            assert client.get(url).status_code == 200
            return
        assert response.status_code == 204
        assert client.get(url).status_code == 404
        assert client.get("/api/v1/drivers").json()["items"] == []
        with fleet.engine.connect() as connection:
            deleted_at = connection.execute(
                text("SELECT deleted_at FROM drivers WHERE id = :id"), {"id": created["id"]}
            ).scalar_one_or_none()
        if answer == "historical":
            assert deleted_at is not None  # soft delete keeps the row
            assert client.delete(url).status_code == 404
        else:
            assert deleted_at is None  # hard delete removes it (no row, no value)


@pytest.mark.ac("AC-FEAT-001-09")
def test_validation_errors_are_problem_json_naming_every_field(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        response = client.post("/api/v1/drivers", json={**driver(0), "homeLat": 123, "extra": 1})
        assert response.status_code == 422
        assert response.headers["content-type"] == "application/problem+json"
        body = response.json()
        assert body["code"] == "VALIDATION_ERROR" and body["requestId"]
        fields = " ".join(error["field"] for error in body["errors"])
        assert "homeLat" in fields and "extra" in fields


@pytest.mark.ac("AC-FEAT-001-04", "AC-FEAT-001-06")
def test_vehicle_rules_on_drivers(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        profile = client.post("/api/v1/cost-profiles", json=cost_profile()).json()
        van = client.post("/api/v1/vehicles", json=vehicle(profile["id"])).json()
        create_driver(client, 0, vehicleId=van["id"])
        taken = client.post("/api/v1/drivers", json=driver(1, vehicleId=van["id"]))
        assert taken.status_code == 409 and taken.json()["code"] == "DUPLICATE_RESOURCE"
        unknown = client.post("/api/v1/drivers", json=driver(2, vehicleId=str(uuid4())))
        assert unknown.status_code == 404 and unknown.json()["code"] == "NOT_FOUND"
