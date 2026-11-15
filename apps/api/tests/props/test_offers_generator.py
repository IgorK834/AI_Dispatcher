"""Property tests of the offers generator for any seed (AC-FEAT-002-05, AC-FEAT-010-03, 06, 15)."""

import json
import math
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from routepilot.freight.consolidation import CORRIDORS, ZONES
from routepilot.freight.generator import generate_offers

ROOT = Path(__file__).resolve().parents[4]
CITIES = {
    (c["name"], c["countryCode"])
    for c in json.loads((ROOT / "data/mock/cities.json").read_text())["cities"]
}
UNKNOWN_PLACE = "MOCK Unknown Place"  # NO_COORDINATES offers: AC-FEAT-002-06 requires half of them
PALLET_FACTOR = {"EUR_1200x800": 1.0, "IND_1200x1000": 1.5, "HALF_800x600": 0.5}
MASS_OVERRIDE_TAGS = {"TOO_HEAVY_ALL", "HEAVY_FOR_8EP", "MUTUALLY_EXCLUSIVE"}  # FEAT-010 FR-3
DATES = st.dates(min_value=date(2020, 1, 1), max_value=date(2040, 12, 31))


def minutes(value: str) -> int:
    hours, mins = value.rstrip("Z").split(":")[:2]
    return int(hours) * 60 + int(mins)


def mass_for(eq: float, kg_per_ep: int) -> int:
    return min(1085, max(40, math.floor(eq * kg_per_ep + 0.5)))


@pytest.mark.ac("AC-FEAT-002-05")
@pytest.mark.ac("AC-FEAT-010-03")
@settings(deadline=None)
@given(st.integers(), DATES)
def test_every_offer_satisfies_the_ranges_of_fr_9_to_fr_12(seed: int, reference: date) -> None:
    payload, enrichment = generate_offers(seed, reference)
    offers = payload["payload"]
    assert len(offers) == 150 and len({o["id"] for o in offers}) == 150
    domestic = 0
    for offer in offers:
        info = enrichment[offer["id"]]
        assert re.fullmatch(r"MOCK-\d{6}", offer["id"])
        assert offer["vehicleProperties"]["type"] == ["VEHICLE_UP_TO_3_5_T"]
        assert len(offer["loadingPlaces"]) == 2
        first, last = offer["loadingPlaces"]
        assert (first["loadingType"], last["loadingType"]) == ("LOADING", "UNLOADING")

        places = [(p["address"]["city"], p["address"]["country"]) for p in (first, last)]
        if "NO_COORDINATES" in info["tags"]:
            # AC-FEAT-002-06 requires half of these offers to name a place outside cities.json.
            assert all(place in CITIES or place[0] == UNKNOWN_PLACE for place in places)
        else:
            assert all(place in CITIES for place in places) and places[0] != places[1]
        assert "PL" in (places[0][1], places[1][1])
        domestic += places[0][1] == places[1][1] == "PL"

        assert 40 <= round(offer["weight_t"] * 1000) <= 1100
        if "pallet_count" in info:
            assert 1 <= info["pallet_count"] <= 10
            if not MASS_OVERRIDE_TAGS & set(info["tags"]):
                # FEAT-010 FR-3: mass follows the pallet equivalent, 50-200 kg per EP.
                eq = info["pallet_count"] * PALLET_FACTOR[info["pallet_type"]]
                assert mass_for(eq, 50) <= round(offer["weight_t"] * 1000) <= mass_for(eq, 200)

        loading = date.fromisoformat(first["earliestLoadingDate"])
        assert 0 <= (loading - reference).days < 7 and loading.weekday() < 5
        delivery = date.fromisoformat(last["earliestLoadingDate"])
        assert delivery >= loading and delivery.weekday() < 5
        for place in (first, last):
            assert date.fromisoformat(place["latestLoadingDate"]) >= date.fromisoformat(
                place["earliestLoadingDate"]
            )
            if "startTime" in place:
                length = minutes(place["endTime"]) - minutes(place["startTime"])
                assert length >= 0
                assert 120 <= length <= 480 or "TIGHT_WINDOW" in info["tags"]
    assert 0.35 <= domestic / len(offers) <= 0.55


@pytest.mark.ac("AC-FEAT-002-05")
@settings(deadline=None, max_examples=25)
@given(st.integers(), DATES)
def test_generation_is_pure_and_loading_stays_within_seven_days_of_the_reference(
    seed: int, reference: date
) -> None:
    first = generate_offers(seed, reference)
    assert generate_offers(seed, reference) == first
    window = [reference + timedelta(days=n) for n in range(7)]
    for offer in first[0]["payload"]:
        assert date.fromisoformat(offer["loadingPlaces"][0]["earliestLoadingDate"]) in window


@pytest.mark.ac("AC-FEAT-010-06")
@settings(deadline=None)
@given(st.integers(), DATES)
def test_offers_come_in_groups_of_one_corridor_date_and_overlapping_windows(
    seed: int, reference: date
) -> None:
    payload, enrichment = generate_offers(seed, reference)
    lanes = {(origin, destination) for origin, destination, _ in CORRIDORS}
    groups: dict[str, list[dict[str, Any]]] = {}
    for offer in payload["payload"]:
        info = enrichment[offer["id"]]
        assert re.fullmatch(r"G-\d{3}", info["groupId"])
        groups.setdefault(info["groupId"], []).append(offer)
        if "NO_COORDINATES" not in info["tags"]:
            first, last = offer["loadingPlaces"]
            assert first["address"]["city"] in ZONES[info["zoneFrom"]]
            assert last["address"]["city"] in ZONES[info["zoneTo"]]
    assert sorted(groups) == [f"G-{number:03}" for number in range(1, len(groups) + 1)]
    for members in groups.values():
        infos = [enrichment[offer["id"]] for offer in members]
        tags = set().union(*(info["tags"] for info in infos))
        assert 1 <= len(members) <= 4
        assert len({offer["loadingPlaces"][0]["earliestLoadingDate"] for offer in members}) == 1
        assert len({(info["zoneFrom"], info["zoneTo"]) for info in infos}) == 1
        if tags & {"RETURN_TO_BASE", "UNPROFITABLE_DETOUR"}:
            assert len(members) == 1  # the lane of the FR-2 tag
        else:
            assert (infos[0]["zoneFrom"], infos[0]["zoneTo"]) in lanes
        if "MUTUALLY_EXCLUSIVE" in tags:
            assert len(members) == 2 and len({info["pair_id"] for info in infos}) == 1
        timed = [o["loadingPlaces"][0] for o in members if "startTime" in o["loadingPlaces"][0]]
        for index, a in enumerate(timed):  # a whole-day window overlaps every window
            for b in timed[index + 1 :]:
                overlap = min(minutes(a["endTime"]), minutes(b["endTime"])) - max(
                    minutes(a["startTime"]), minutes(b["startTime"])
                )
                assert overlap >= 60


@pytest.mark.ac("AC-FEAT-010-15")
@settings(deadline=None)
@given(st.integers(), DATES)
def test_every_delivery_window_can_be_reached_from_the_offers_own_pickup(
    seed: int, reference: date
) -> None:
    payload, _ = generate_offers(seed, reference)
    for offer in payload["payload"]:
        first, last = offer["loadingPlaces"]
        loading = date.fromisoformat(first["earliestLoadingDate"])
        delivery = date.fromisoformat(last["earliestLoadingDate"])
        assert delivery >= loading and loading.weekday() < 5 and delivery.weekday() < 5
        if "startTime" not in first:
            continue
        drive_min = math.ceil(offer["distance_km"] * 60 * 1.08 / 65)
        ready = minutes(first["startTime"]) + 30 + drive_min
        assert (delivery - loading).days * 1440 + minutes(last["endTime"]) >= ready, offer["id"]
