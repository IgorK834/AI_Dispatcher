import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given
from hypothesis import strategies as st

from routepilot.fleet.generator import generate_fleet


@pytest.mark.ac("AC-FEAT-002-01")
@pytest.mark.ac("AC-FEAT-002-02")
def test_fleet_snapshot_and_approved_parameters() -> None:
    result = generate_fleet(20261109, date(2026, 11, 16))
    committed = Path(__file__).resolve().parents[5] / "data/mock/fleet.json"
    assert result == json.loads(committed.read_text())
    assert len(result["drivers"]) == len(result["vehicles"]) == 5
    assert [v["payload_kg"] for v in result["vehicles"]] == [1085, 1050, 1000, 880, 765]
    assert [v["pallet_places"] for v in result["vehicles"]] == [10, 10, 9, 8, 8]
    assert all(
        v["gvw_kg"] == 3500 and v["fuel"]["provenance"] == "assumption" for v in result["vehicles"]
    )
    assert result["vehicles"][2]["inner_length_m"] is None
    assert json.dumps(result, sort_keys=True) == json.dumps(
        generate_fleet(20261109, date(2026, 11, 16)), sort_keys=True
    )


@pytest.mark.ac("AC-FEAT-002-03")
@given(st.integers(), st.dates(min_value=date(2020, 1, 1), max_value=date(2040, 12, 31)))
def test_driver_state_ranges(seed: int, reference: date) -> None:
    result = generate_fleet(seed, reference)
    for state in result["driver_states"]:
        available = datetime.fromisoformat(state["available_from"])
        home = datetime.fromisoformat(state["home_by"]).astimezone(ZoneInfo("Europe/Warsaw"))
        assert home.weekday() == 4 and home.hour == 18 and home > available
        assert available.minute % 15 == 0
        assert 0 <= state["work_week_min"] <= 2160
        assert 0 <= state["drive_week_min"] <= min(state["work_week_min"], 2016)
        assert 0 <= state["drive_prev_week_min"] <= 2700
        assert state["source"] == "generated_mock" and state["is_synthetic"]
