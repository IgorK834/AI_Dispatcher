"""Property tests of the seeded fleet generator for any seed and reference date (AC-FEAT-002-03)."""

import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given
from hypothesis import strategies as st

from routepilot.fleet.generator import generate_fleet

CITIES = json.loads((Path(__file__).resolve().parents[4] / "data/mock/cities.json").read_text())[
    "cities"
]
BY_NAME = {(c["name"], c["countryCode"]): c for c in CITIES}
POLISH = {c["name"]: c for c in CITIES if c["countryCode"] == "PL"}
DATES = st.dates(min_value=date(2020, 1, 1), max_value=date(2040, 12, 31))


def expected_home_by_date(reference: date) -> date:
    """Friday of the reference week; the following Friday from Friday to Sunday."""
    days = 4 - reference.weekday()
    return reference + timedelta(days=days if reference.weekday() < 4 else days + 7)


@pytest.mark.ac("AC-FEAT-002-03")
@given(st.integers(), DATES)
def test_every_driver_state_satisfies_the_ranges_of_fr_6(seed: int, reference: date) -> None:
    fleet = generate_fleet(seed, reference)
    midnight = datetime.combine(reference, time(), UTC)
    homes = {d["id"]: d for d in fleet["drivers"]}
    assert len(fleet["driver_states"]) == len(homes) == 5
    assert len({s["driver_id"] for s in fleet["driver_states"]}) == 5  # one state per driver
    for state in fleet["driver_states"]:
        assert state["is_synthetic"] is True and state["source"] == "generated_mock"

        available = datetime.fromisoformat(state["available_from"])
        assert available.utcoffset() == timedelta(0)
        assert timedelta(0) <= available - midnight <= timedelta(hours=24)
        assert available.second == 0 and available.minute % 15 == 0

        position = POLISH[state["current_city"]]  # a Polish city of cities.json
        assert (state["current_lat"], state["current_lon"]) == (position["lat"], position["lon"])

        assert 0 <= state["work_week_min"] <= 0.6 * 3600
        assert 0 <= state["drive_week_min"] <= min(state["work_week_min"], 0.6 * 3360)
        assert 0 <= state["drive_prev_week_min"] <= 2700
        for counter in ("work_today", "drive_today", "work_since_break", "drive_since_break"):
            assert state[f"{counter}_min"] == 0
        assert state["last_daily_rest_end"] == state["available_from"]

        base = BY_NAME[(homes[state["driver_id"]]["home_city"], "PL")]
        local = datetime.fromisoformat(state["home_by"]).astimezone(ZoneInfo(base["timezone"]))
        assert (local.weekday(), local.hour, local.minute, local.second) == (4, 18, 0, 0)
        assert local.date() == expected_home_by_date(reference)
        assert local > available


@pytest.mark.ac("AC-FEAT-002-03")
@pytest.mark.parametrize(
    ("reference", "expected_friday"),
    [
        (date(2026, 11, 16), date(2026, 11, 20)),  # Monday
        (date(2026, 11, 19), date(2026, 11, 20)),  # Thursday
        (date(2026, 11, 20), date(2026, 11, 27)),  # Friday: the following week
        (date(2026, 11, 21), date(2026, 11, 27)),  # Saturday
        (date(2026, 11, 22), date(2026, 11, 27)),  # Sunday
        (date(2026, 7, 6), date(2026, 7, 10)),  # summer time: 18:00 CEST is 16:00Z
    ],
)
def test_home_by_week_rule_and_daylight_saving(reference: date, expected_friday: date) -> None:
    for state in generate_fleet(20261109, reference)["driver_states"]:
        local = datetime.fromisoformat(state["home_by"]).astimezone(ZoneInfo("Europe/Warsaw"))
        assert local.date() == expected_friday and local.hour == 18
    summer = datetime.fromisoformat(
        generate_fleet(1, date(2026, 7, 6))["driver_states"][0]["home_by"]
    )
    assert summer.hour == 16 and summer.utcoffset() == timedelta(0)


@pytest.mark.ac("AC-FEAT-002-03")
@given(st.integers(), DATES)
def test_the_fleet_itself_does_not_depend_on_the_seed(seed: int, reference: date) -> None:
    fleet = generate_fleet(seed, reference)
    baseline = generate_fleet(0, date(2026, 11, 16))
    assert fleet["drivers"] == baseline["drivers"]
    assert fleet["vehicles"] == baseline["vehicles"]
    assert generate_fleet(seed, reference) == fleet  # pure: same inputs, same output
