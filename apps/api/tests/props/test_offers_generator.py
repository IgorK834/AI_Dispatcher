"""Property tests of the offers generator for any seed (AC-FEAT-002-05)."""

import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from routepilot.freight.generator import generate_offers

ROOT = Path(__file__).resolve().parents[4]
CITIES = {
    (c["name"], c["countryCode"])
    for c in json.loads((ROOT / "data/mock/cities.json").read_text())["cities"]
}
UNKNOWN_PLACE = "MOCK Unknown Place"  # NO_COORDINATES offers: AC-FEAT-002-06 requires half of them
DATES = st.dates(min_value=date(2020, 1, 1), max_value=date(2040, 12, 31))


def minutes(value: str) -> int:
    hours, mins = value.rstrip("Z").split(":")[:2]
    return int(hours) * 60 + int(mins)


@pytest.mark.ac("AC-FEAT-002-05")
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
