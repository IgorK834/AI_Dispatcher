import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from routepilot.freight.generator import TAG_RANGES, generate_offers


@pytest.mark.ac("AC-FEAT-002-04")
@pytest.mark.ac("AC-FEAT-002-06")
@pytest.mark.ac("AC-FEAT-002-07")
def test_committed_offers_snapshot_price_and_tags() -> None:
    payload, enrichment = generate_offers(20261109, date(2026, 11, 16))
    root = Path(__file__).resolve().parents[5]
    assert payload == json.loads((root / "data/mock/offers.timocom.json").read_text())
    assert enrichment == json.loads((root / "data/mock/offers.enrichment.json").read_text())
    assert len(payload["payload"]) == len({o["id"] for o in payload["payload"]}) == 150
    tags = Counter(tag for info in enrichment.values() for tag in info["tags"])
    assert all(tags[tag] >= len(indices) for tag, indices in TAG_RANGES.items())
    for offer in payload["payload"]:
        info = enrichment[offer["id"]]
        tags = info["tags"]
        if "NO_PRICE" in tags:
            assert "price" not in offer
        else:
            formula = info["price_formula"]
            assert offer["price"]["amount"] == max(
                120, round(formula["rate_eur_per_km"] * formula["distance_km"] * formula["noise"])
            )
        if "UNPROFITABLE_DETOUR" in tags:
            assert offer["price"]["amount"] == 120 and offer["distance_km"] > 500
            assert info["price_formula"]["noise_provenance"] == "assumption"
        if "INCOMPATIBLE_BODY" in tags:
            assert offer["vehicleProperties"]["body"] == ["REFRIGERATOR"]
        if "INCOMPATIBLE_EQUIPMENT" in tags:
            assert offer["vehicleProperties"]["equipment"] == ["TAIL_LIFT"]
        if "NO_PALLETS" in tags:
            assert "pallet_count" not in info and "length_m" in offer
        if "TOO_HEAVY_ALL" in tags:
            assert offer["weight_t"] > 1.085
        if "HEAVY_FOR_8EP" in tags:
            assert 0.766 <= offer["weight_t"] <= 1.05
        if "DAY_ONLY_WINDOW" in tags:
            assert all(
                "startTime" not in stop and "endTime" not in stop for stop in offer["loadingPlaces"]
            )
        if "RETURN_TO_BASE" in tags:
            assert date.fromisoformat(
                offer["loadingPlaces"][-1]["earliestLoadingDate"]
            ).weekday() in (3, 4)
        if "PROMPT_INJECTION" in tags:
            assert any(
                word in offer["publicRemark"].lower() for word in ("ignore previous", "you must")
            )


@pytest.mark.ac("AC-FEAT-002-05")
@given(st.integers(), st.dates(min_value=date(2020, 1, 1), max_value=date(2040, 12, 31)))
def test_generated_offer_ranges(seed: int, reference: date) -> None:
    payload, enrichment = generate_offers(seed, reference)
    domestic = 0
    for offer in payload["payload"]:
        first, last = offer["loadingPlaces"]
        assert first["loadingType"] == "LOADING" and last["loadingType"] == "UNLOADING"
        assert (
            first["address"]["city"] != last["address"]["city"]
            or "NO_COORDINATES" in enrichment[offer["id"]]["tags"]
        )
        assert "PL" in (first["address"]["country"], last["address"]["country"])
        domestic += first["address"]["country"] == last["address"]["country"] == "PL"
        assert offer["vehicleProperties"]["type"] == ["VEHICLE_UP_TO_3_5_T"]
        assert 0.04 <= offer["weight_t"] <= 1.1
        load = date.fromisoformat(first["earliestLoadingDate"])
        assert 0 <= (load - reference).days < 7 and load.weekday() < 5
        assert date.fromisoformat(last["earliestLoadingDate"]) >= load
        for stop in offer["loadingPlaces"]:
            assert date.fromisoformat(stop["earliestLoadingDate"]).weekday() < 5
            if "startTime" in stop:
                assert datetime.fromisoformat(
                    "2000-01-01T" + stop["startTime"].rstrip("Z")
                ) <= datetime.fromisoformat("2000-01-01T" + stop["endTime"].rstrip("Z"))
    assert 0.35 <= domestic / 150 <= 0.55
