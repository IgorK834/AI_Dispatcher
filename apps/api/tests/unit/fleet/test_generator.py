import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given
from hypothesis import strategies as st

from routepilot.fleet.generator import generate_fleet, main


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


FLEET_FILE = Path(__file__).resolve().parents[5] / "data/mock/fleet.json"

# FEAT-002 §6.2 (report §17.2): base, label, pallet places, layout, interior L x W x H, payload,
# sleeper cab. D3's interior is unknown (None).
SECTION_6_2 = [
    ("Katowice", "BUS-01", 10, "EUR_MIXED_6X4", (4.85, 2.10, 2.10), 1085, False),
    ("Wrocław", "BUS-02", 10, "EUR_MIXED_6X4", (4.85, 2.10, 2.10), 1050, True),
    ("Poznań", "BUS-03", 9, "DECLARED_ONLY", (None, None, None), 1000, False),
    ("Łódź", "BUS-04", 8, "EUR_MIXED_5X3", (4.20, 2.10, 2.30), 880, False),
    ("Kraków", "BUS-05", 8, "EUR_MIXED_5X3", (4.20, 2.10, 2.15), 765, False),
]


@pytest.mark.ac("AC-FEAT-002-01")
def test_the_cli_writes_byte_identical_files_equal_to_the_committed_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = []
    for run in ("first", "second"):
        out = tmp_path / run / "fleet.json"
        monkeypatch.setattr(
            "sys.argv",
            [
                "generator",
                "--seed",
                "20261109",
                "--reference-date",
                "2026-11-16",
                "--out",
                str(out),
            ],
        )
        main()
        outputs.append(out.read_bytes())
    assert outputs[0] == outputs[1] == FLEET_FILE.read_bytes()
    text = outputs[0].decode("utf-8")
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert "Wrocław" in text and "\\u" not in text  # UTF-8, not escaped
    assert unicodedata.is_normalized("NFC", text)


@pytest.mark.ac("AC-FEAT-002-01")
def test_other_seeds_and_dates_give_other_but_reproducible_files() -> None:
    base = generate_fleet(20261109, date(2026, 11, 16))
    assert generate_fleet(20261110, date(2026, 11, 16)) != base
    assert generate_fleet(20261109, date(2026, 11, 17)) != base
    assert generate_fleet(20261110, date(2026, 11, 16)) == generate_fleet(
        20261110, date(2026, 11, 16)
    )


@pytest.mark.ac("AC-FEAT-002-02")
def test_the_five_drivers_and_vans_match_section_6_2_exactly() -> None:
    fleet = generate_fleet(20261109, date(2026, 11, 16))
    assert len(fleet["drivers"]) == len(fleet["vehicles"]) == len(fleet["driver_states"]) == 5
    cities = {
        c["name"]: c
        for c in json.loads(FLEET_FILE.parent.joinpath("cities.json").read_text())["cities"]
    }
    for index, (driver, vehicle) in enumerate(
        zip(fleet["drivers"], fleet["vehicles"], strict=True)
    ):
        base, label, places, layout, interior, payload, sleeper = SECTION_6_2[index]
        assert driver["home_city"] == base and driver["home_country"] == "PL"
        assert (driver["home_lat"], driver["home_lon"]) == (
            cities[base]["lat"],
            cities[base]["lon"],
        )
        assert driver["vehicle_id"] == vehicle["id"] and driver["is_synthetic"] is True
        assert driver["default_rules_profile"] == "pl_domestic_employee_v1"
        assert vehicle["label"] == label and vehicle["pallet_places"] == places
        assert vehicle["layout_template"] == layout and vehicle["payload_kg"] == payload
        assert vehicle["sleeper_cab"] is sleeper
        assert (
            vehicle["inner_length_m"],
            vehicle["inner_width_m"],
            vehicle["inner_height_m"],
        ) == interior
        assert vehicle["vehicle_type"] == "VEHICLE_UP_TO_3_5_T"
        assert vehicle["body_type"] == "CURTAIN_SIDER" and vehicle["side_access"] == "BOTH"
        assert vehicle["gvw_kg"] == 3500 and vehicle["is_synthetic"] is True
        assert vehicle["fuel"] == {
            "l_per_100km_empty_at90": "11.0",
            "l_per_100km_full_at90": "13.0",
            "speed_curve": "VAN_DEFAULT_V1",
            "provenance": "assumption",
        }
        assert vehicle["cost_profile"] == "DEMO-DEFAULT"


@pytest.mark.ac("AC-FEAT-002-02")
def test_names_and_phone_numbers_are_obviously_fictional() -> None:
    drivers = generate_fleet(20261109, date(2026, 11, 16))["drivers"]
    assert len({d["name"] for d in drivers}) == 5
    for driver in drivers:
        assert re.fullmatch(r"\+00-000-000-00[1-5]", driver["phone"])  # not a dialable number
        assert driver["id"].startswith("MOCK-D")
