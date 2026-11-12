"""Driver state history over HTTP: append-only rows, newest first, embedded in the driver."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from routepilot.shared.clock import FixedClock
from tests.factories import api_client, driver, driver_state


@pytest.mark.ac("AC-FEAT-001-15")
def test_states_are_appended_listed_newest_first_and_embedded(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        driver_id = client.post("/api/v1/drivers", json=driver(0)).json()["id"]
        url = f"/api/v1/drivers/{driver_id}/state"
        fleet = client.app.state.services.fleet

        fleet.clock = FixedClock(datetime(2026, 11, 16, 8, 0, tzinfo=UTC))
        first = client.post(url, json=driver_state(50.0))
        fleet.clock = FixedClock(datetime(2026, 11, 16, 9, 0, tzinfo=UTC))
        second = client.post(url, json=driver_state(51.0))

        assert first.status_code == 201 and second.status_code == 201
        assert second.headers["Location"].endswith(f"/drivers/{driver_id}/state")
        assert second.json()["source"] == "user" and second.json()["driverId"] == driver_id
        assert second.json()["validFrom"].startswith("2026-11-16T09:00:00")

        rows = client.get(url).json()["items"]
        assert [row["id"] for row in rows] == [second.json()["id"], first.json()["id"]]
        assert {row["source"] for row in rows} == {"user"}
        assert (
            client.get(f"/api/v1/drivers/{driver_id}").json()["state"]["id"] == second.json()["id"]
        )

        # Rows are immutable history: the first row is unchanged by the second post.
        assert rows[1]["currentLat"] == 50.0


@pytest.mark.ac("AC-FEAT-001-15")
@pytest.mark.parametrize(
    "counter",
    [
        "workTodayMin",
        "driveTodayMin",
        "workSinceBreakMin",
        "driveSinceBreakMin",
        "workWeekMin",
        "driveWeekMin",
        "drivePrevWeekMin",
    ],
)
def test_negative_counter_is_rejected(tmp_path: Path, counter: str) -> None:
    with api_client(tmp_path) as client:
        driver_id = client.post("/api/v1/drivers", json=driver(0)).json()["id"]
        url = f"/api/v1/drivers/{driver_id}/state"
        response = client.post(url, json=driver_state(**{counter: -1}))
        assert response.status_code == 422 and response.json()["code"] == "VALIDATION_ERROR"
        assert client.get(url).json()["items"] == []


@pytest.mark.ac("AC-FEAT-001-15")
def test_state_needs_an_existing_driver_and_a_timezone_aware_time(tmp_path: Path) -> None:
    with api_client(tmp_path) as client:
        driver_id = client.post("/api/v1/drivers", json=driver(0)).json()["id"]
        naive = driver_state(availableFrom="2026-11-16T08:00:00")
        assert client.post(f"/api/v1/drivers/{driver_id}/state", json=naive).status_code == 422
        missing = "00000000-0000-4000-8000-000000000000"
        assert (
            client.post(f"/api/v1/drivers/{missing}/state", json=driver_state()).status_code == 404
        )
