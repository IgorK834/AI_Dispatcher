"""Fleet & Compliance driver tools through the real registry: aliases, state, availability."""

import json
from uuid import UUID

import pytest

from routepilot.agents.tools import contracts
from tests.agents.conftest import ToolEnv

FLEET = "fleet_compliance"


@pytest.mark.ac("AC-FEAT-006-29")
def test_list_drivers_returns_stable_aliases_in_creation_order_without_private_data(
    tool_env: ToolEnv,
) -> None:
    drivers = tool_env.fleet.list_active()
    assert len(drivers) == 5
    first = tool_env.call(FLEET, "list_drivers")
    assert [item["driver_ref"] for item in first["drivers"]] == ["D1", "D2", "D3", "D4", "D5"]
    assert first["count"] == 5 and set(first) == set(contracts.ListDriversOutput.model_fields)
    # D1..D5 follow the creation order of the drivers and carry their vehicle capacity.
    created = sorted(drivers, key=lambda driver: (driver.created_at, str(driver.id)))
    assert [UUID(tool_env.state["aliases"]["drivers"][f"D{n}"]) for n in range(1, 6)] == [
        driver.id for driver in created
    ]
    for item, driver in zip(first["drivers"], created, strict=True):
        assert driver.vehicle is not None
        assert item["pallet_places"] == driver.vehicle.pallet_places
        assert item["payload_kg"] == driver.vehicle.payload_kg
        assert item["home_city"] == driver.home_city
    serialized = json.dumps(first)
    for driver in drivers:
        assert driver.name not in serialized and driver.phone not in serialized
        assert str(driver.id) not in serialized
    assert set(first["drivers"][0]) == set(contracts.Driver.model_fields), "no name field"
    # Later calls of the same thread return the same aliases, also after other tools ran.
    tool_env.call(FLEET, "driver_state", driver_ref="D3")
    assert tool_env.call(FLEET, "list_drivers") == first
    assert tool_env.call(FLEET, "list_drivers", extra=True)["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.ac("AC-FEAT-006-29")
def test_aliases_follow_the_thread_state_not_the_call_order(tool_env: ToolEnv) -> None:
    # A driver_state call before any list_drivers already uses the creation-order alias map.
    early = tool_env.call(FLEET, "driver_state", driver_ref="D2")
    listed = tool_env.call(FLEET, "list_drivers")
    second = tool_env.fleet.latest_state(UUID(tool_env.state["aliases"]["drivers"]["D2"]))
    assert early["current_city"] == second.current_city
    assert listed["drivers"][1]["current_city"] == second.current_city


@pytest.mark.ac("AC-FEAT-006-30")
def test_driver_state_returns_the_latest_counters_and_unknown_ref_is_not_found(
    tool_env: ToolEnv,
) -> None:
    tool_env.call(FLEET, "list_drivers")
    driver_id = UUID(tool_env.state["aliases"]["drivers"]["D2"])
    state = tool_env.fleet.latest_state(driver_id)
    result = tool_env.call(FLEET, "driver_state", driver_ref="D2")
    assert set(result) == set(contracts.DriverStateOutput.model_fields)
    assert result["driver_ref"] == "D2" and "driver_id" not in result
    for name in (
        "work_today_min",
        "drive_today_min",
        "work_since_break_min",
        "drive_since_break_min",
        "work_week_min",
        "drive_week_min",
        "drive_prev_week_min",
    ):
        assert result[name] == getattr(state, name), name
    assert result["available_from"] == state.available_from.isoformat()
    assert result["state_source"] == state.source
    # A newer state version is what the tool reports afterwards.
    tool_env.set_driver_state(driver_id, work_today_min=123)
    assert tool_env.call(FLEET, "driver_state", driver_ref="D2")["work_today_min"] == 123
    for reference in ("D9", "D0", "driver-1"):
        assert tool_env.call(FLEET, "driver_state", driver_ref=reference)["error"]["code"] == (
            "NOT_FOUND"
        )
    assert tool_env.call(FLEET, "driver_state", driver_ref="D2", extra=1)["error"]["code"] == (
        "VALIDATION_ERROR"
    )


@pytest.mark.ac("AC-FEAT-006-31")
def test_driver_availability_reports_remaining_work_and_driving_from_the_rules(
    tool_env: ToolEnv,
) -> None:
    tool_env.call(FLEET, "list_drivers")
    driver_id = UUID(tool_env.state["aliases"]["drivers"]["D1"])
    tool_env.set_driver_state(
        driver_id, work_week_min=3000, work_since_break_min=200, drive_since_break_min=200
    )
    result = tool_env.call(FLEET, "driver_availability", driver_ref="D1")
    assert set(result) == set(contracts.DriverAvailabilityOutput.model_fields)
    # Weekly work is limited to 60 h = 3 600 min; 4 h 30 min of driving precede a break.
    assert result["remaining"]["work_week_min"] == 600
    assert result["remaining_561"]["drive_before_break_min"] == 70
    assert result["driver_ref"] == "D1" and "driver_id" not in result
    assert result["has_active_assignment"] is False
    # The same numbers come from the service, not from the tool.
    direct = tool_env.plans.driver_availability(driver_id)
    assert direct.remaining.work_week_min == 600
    assert direct.remaining_561.drive_before_break_min == 70
    assert tool_env.call(FLEET, "driver_availability", driver_ref="D9")["error"]["code"] == (
        "NOT_FOUND"
    )
    for arguments in ({"horizon_days": 0}, {"horizon_days": 8}, {"unknown": 1}):
        error = tool_env.call(FLEET, "driver_availability", driver_ref="D1", **arguments)
        assert error["error"]["code"] == "VALIDATION_ERROR", arguments
