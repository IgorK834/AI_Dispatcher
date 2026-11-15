import json
import math
import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from routepilot.freight.generator import TAG_RANGES, generate_offers, ltl_price, main


@pytest.mark.ac("AC-FEAT-002-04")
@pytest.mark.ac("AC-FEAT-002-06")
@pytest.mark.ac("AC-FEAT-010-04")
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
            assert offer["price"]["amount"] == recomputed_price(formula)
        if "UNPROFITABLE_DETOUR" in tags:
            assert offer["price"]["amount"] == 60 and offer["distance_km"] > 500
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


# --- AC-FEAT-002-04 .. 06 and AC-FEAT-010-02 .. 05 checked against the specifications
# (FEAT-002 §6.3, §6.4; FEAT-010 FR-6, §6.1), not generator constants
ROOT = Path(__file__).resolve().parents[5]
OFFERS_FILE = ROOT / "data/mock/offers.timocom.json"
ENRICHMENT_FILE = ROOT / "data/mock/offers.enrichment.json"
CITY_TABLE = {
    (c["name"], c["countryCode"]): c
    for c in json.loads((ROOT / "data/mock/cities.json").read_text())["cities"]
}
BASES = {"Katowice", "Wrocław", "Poznań", "Łódź", "Kraków"}

# FEAT-002 §6.4: tag -> minimum count in the 150 generated offers.
MINIMUM = {
    "NO_PRICE": 6,
    "NO_PALLETS": 5,
    "NO_COORDINATES": 4,
    "INCOMPATIBLE_BODY": 5,
    "INCOMPATIBLE_EQUIPMENT": 4,
    "TOO_HEAVY_ALL": 4,
    "HEAVY_FOR_8EP": 10,
    "TIGHT_WINDOW": 15,
    "DAY_ONLY_WINDOW": 10,
    "RETURN_TO_BASE": 15,
    "UNPROFITABLE_DETOUR": 5,
    "PROMPT_INJECTION": 3,
    "ALT_TIME_FORMAT": 5,
    "KEY_WITH_SPACE": 2,
}
# FEAT-002 §6.3: rate in EUR per km by destination for PL -> X lanes.
RATE_PL_TO = {"CZ": 0.93, "SK": 0.93, "HU": 0.79, "DE": 0.68, "FR": 0.60, "PL": 0.85}
RATE_PL_TO.update(dict.fromkeys(("AT", "NL", "BE", "DK"), 0.68))
RATE_PL_TO["IT"] = 0.60


def spec_rate(origin_country: str, destination_country: str) -> float:
    if origin_country == "PL":
        return RATE_PL_TO[destination_country]
    return 0.7 * RATE_PL_TO[origin_country]


def haversine_125(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return round(6371 * 2 * math.asin(min(1, math.sqrt(h))) * 1.25, 2)


# FEAT-010 FR-2: the offers-generator v2 index ranges (0-based, end exclusive) stay where they were.
V2_TAG_INDICES = {
    "NO_PRICE": (0, 6),
    "NO_PALLETS": (6, 11),
    "NO_COORDINATES": (11, 15),
    "INCOMPATIBLE_BODY": (15, 20),
    "INCOMPATIBLE_EQUIPMENT": (20, 24),
    "TOO_HEAVY_ALL": (24, 28),
    "HEAVY_FOR_8EP": (28, 38),
    "TIGHT_WINDOW": (38, 53),
    "DAY_ONLY_WINDOW": (53, 63),
    "RETURN_TO_BASE": (63, 78),
    "UNPROFITABLE_DETOUR": (78, 83),
    "MUTUALLY_EXCLUSIVE": (83, 91),
    "PROMPT_INJECTION": (91, 94),
    "ALT_TIME_FORMAT": (94, 99),
    "KEY_WITH_SPACE": (99, 101),
}
PALLET_FACTOR = {"EUR_1200x800": 1.0, "IND_1200x1000": 1.5, "HALF_800x600": 0.5}


def half_up(value: float) -> int:
    return math.floor(value + 0.5)


def recomputed_price(formula: dict[str, Any]) -> int:
    product = formula["rate"] * formula["distance_km"] * formula["share"]
    return max(60, half_up(product * formula["premium"] * formula["noise"]))


def committed() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    offers = json.loads(OFFERS_FILE.read_text())["payload"]
    return offers, json.loads(ENRICHMENT_FILE.read_text())


def minutes(value: str) -> int:
    hours, mins = value.rstrip("Z").split(":")[:2]
    return int(hours) * 60 + int(mins)


@pytest.mark.ac("AC-FEAT-002-04")
def test_files_are_byte_identical_on_every_run_and_ids_follow_the_pattern(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    written = []
    for run in ("first", "second"):
        out, enriched = tmp_path / run / "offers.json", tmp_path / run / "enrichment.json"
        monkeypatch.setattr(
            "sys.argv",
            [
                "generator",
                "--seed", "20261109",
                "--reference-date", "2026-11-16",
                "--out", str(out),
                "--enrichment-out", str(enriched),
            ],
        )  # fmt: skip
        main()
        written.append((out.read_bytes(), enriched.read_bytes()))
    assert written[0] == written[1] == (OFFERS_FILE.read_bytes(), ENRICHMENT_FILE.read_bytes())
    offers, enrichment = committed()
    ids = [offer["id"] for offer in offers]
    assert len(ids) == len(set(ids)) == 150 and set(ids) == set(enrichment)
    assert all(re.fullmatch(r"MOCK-\d{6}", offer_id) for offer_id in ids)


@pytest.mark.ac("AC-FEAT-002-06")
def test_every_tag_of_section_6_4_reaches_its_minimum_in_the_enrichment_file() -> None:
    _, enrichment = committed()
    counts = Counter(tag for info in enrichment.values() for tag in info["tags"])
    for tag, minimum in MINIMUM.items():
        assert counts[tag] >= minimum, f"{tag}: {counts[tag]} < {minimum}"
    pairs = Counter(info["pair_id"] for info in enrichment.values() if "pair_id" in info)
    assert len(pairs) >= 4 and set(pairs.values()) == {2}  # MUTUALLY_EXCLUSIVE: 4 pairs
    assert counts["PROMPT_INJECTION"] == 3  # exactly 3 (2 %)
    assert all(info["provenance"] == "generated_mock" for info in enrichment.values())


@pytest.mark.ac("AC-FEAT-002-06")
def test_each_tagged_offer_really_has_the_property_and_only_tagged_ones_do() -> None:
    offers, enrichment = committed()
    known_cities = {name for name, _ in CITY_TABLE}
    for offer in offers:
        info = enrichment[offer["id"]]
        tags = set(info["tags"])
        first, last = offer["loadingPlaces"]
        timed = [p for p in offer["loadingPlaces"] if "startTime" in p]
        weight = round(offer["weight_t"] * 1000)

        assert ("price" not in offer) == ("NO_PRICE" in tags)
        assert ("pallet_count" not in info) == ("NO_PALLETS" in tags)
        if "NO_PALLETS" in tags:
            assert "length_m" in offer
        assert (offer["vehicleProperties"]["body"] == ["REFRIGERATOR"]) == (
            "INCOMPATIBLE_BODY" in tags
        )
        assert ("TAIL_LIFT" in offer["vehicleProperties"]["equipment"]) == (
            "INCOMPATIBLE_EQUIPMENT" in tags
        )
        assert (weight > 1085) == ("TOO_HEAVY_ALL" in tags)
        if "HEAVY_FOR_8EP" in tags:
            assert 766 <= weight <= 1050
        assert (not timed) == ("DAY_ONLY_WINDOW" in tags)
        if "TIGHT_WINDOW" in tags:
            assert all(minutes(p["endTime"]) - minutes(p["startTime"]) == 120 for p in timed)
        assert any(re.fullmatch(r"\d\d:\d\d:\d\dZ", p.get("startTime", "")) for p in timed) == (
            "ALT_TIME_FORMAT" in tags
        )
        assert ("creationDateTime " in offer) == ("KEY_WITH_SPACE" in tags)
        assert ("creationDateTime" in offer) == ("KEY_WITH_SPACE" not in tags)
        if "RETURN_TO_BASE" in tags:
            assert last["address"]["city"] in BASES and last["address"]["country"] == "PL"
            assert date.fromisoformat(last["earliestLoadingDate"]).weekday() in (3, 4)
        if "NO_COORDINATES" in tags:
            for place in (first, last):
                assert place["address"]["geoCoordinate"] is None
                assert place["address"]["geocoded"] is False
        else:
            for place in (first, last):
                assert place["address"]["geoCoordinate"] is not None
                assert place["address"]["city"] in known_cities
        if "UNPROFITABLE_DETOUR" in tags:
            assert offer["price"]["amount"] == 60 and offer["distance_km"] > 500
            assert info["price_formula"]["noise_provenance"] == "assumption"
            assert info["price_formula"]["override"] == "minimum_fare_detour"
        injected = bool(
            re.search(r"ignore previous|system:|assign this|you must", offer["publicRemark"], re.I)
        )
        assert injected == ("PROMPT_INJECTION" in tags)
        if injected:  # fictional text: no links, no code
            assert not re.search(r"https?:|www\.|[<>{}`]", offer["publicRemark"])


@pytest.mark.ac("AC-FEAT-002-06")
def test_no_coordinates_offers_are_half_known_cities_and_half_unknown_places() -> None:
    offers, enrichment = committed()
    known = {name for name, _ in CITY_TABLE}
    tagged = [o for o in offers if "NO_COORDINATES" in enrichment[o["id"]]["tags"]]
    in_table = [o for o in tagged if o["loadingPlaces"][0]["address"]["city"] in known]
    assert len(tagged) >= 4 and len(in_table) * 2 == len(tagged)


@pytest.mark.ac("AC-FEAT-002-06")
def test_mutually_exclusive_pairs_overlap_in_time_and_exceed_capacity_together() -> None:
    offers, enrichment = committed()
    by_pair: dict[str, list[dict[str, Any]]] = {}
    for offer in offers:
        if "pair_id" in enrichment[offer["id"]]:
            by_pair.setdefault(enrichment[offer["id"]]["pair_id"], []).append(offer)
    assert len(by_pair) >= 4
    for members in by_pair.values():
        a, b = members
        for place_a, place_b in zip(a["loadingPlaces"], b["loadingPlaces"], strict=True):
            assert place_a["earliestLoadingDate"] == place_b["earliestLoadingDate"]
            assert minutes(place_a["startTime"]) < minutes(place_b["endTime"])
            assert minutes(place_b["startTime"]) < minutes(place_a["endTime"])
        weight = sum(round(o["weight_t"] * 1000) for o in members)
        pallets = sum(enrichment[o["id"]]["pallet_count"] for o in members)
        assert weight > 1085 or pallets > 10  # more than the largest demo van carries


@pytest.mark.ac("AC-FEAT-010-02")
def test_every_tag_sits_on_the_offer_ids_of_its_v2_index_range() -> None:
    _, enrichment = committed()
    for tag, (start, stop) in V2_TAG_INDICES.items():
        tagged = {offer_id for offer_id, info in enrichment.items() if tag in info["tags"]}
        assert tagged == {f"MOCK-{index + 1:06}" for index in range(start, stop)}, tag
        assert len(tagged) >= (8 if tag == "MUTUALLY_EXCLUSIVE" else MINIMUM[tag])
    known = set(V2_TAG_INDICES)
    assert all(set(info["tags"]) <= known for info in enrichment.values())


@pytest.mark.ac("AC-FEAT-010-04")
def test_prices_recompute_from_the_recorded_tariff_values() -> None:
    offers, enrichment = committed()
    priced = [o for o in offers if "NO_PRICE" not in enrichment[o["id"]]["tags"]]
    assert len(priced) >= 144
    log_noise = []
    for offer in priced:
        info = enrichment[offer["id"]]
        formula = info["price_formula"]
        amount = offer["price"]["amount"]
        assert isinstance(amount, int) and not isinstance(amount, bool) and amount >= 60
        assert offer["price"]["currency"] == "EUR"
        assert amount == recomputed_price(formula)
        assert formula["min_fare"] == 60 and formula["tariff_provenance"] == "assumption"
        # share and premium follow FR-6 for the offer's pallets (or its length) and mass.
        weight = round(offer["weight_t"] * 1000)
        if "pallet_count" in info:
            eq = info["pallet_count"] * PALLET_FACTOR[info["pallet_type"]]
        else:  # NO_PALLETS: derived from the length
            eq = math.ceil(Decimal(str(offer["length_m"])) * Decimal("2.4"))
        share = min(1, max(eq / 10, weight / 1000))
        assert formula["share"] == pytest.approx(share) and 0 < formula["share"] <= 1
        assert formula["premium"] == pytest.approx(1 + 0.6 * (1 - share))
        assert info["billableShare"] == formula["share"]
        assert info["ltlPremium"] == formula["premium"]
        # The recorded inputs themselves follow §6.3 and the haversine x 1.25 distance.
        first, last = offer["loadingPlaces"]
        a = CITY_TABLE.get((first["address"]["city"], first["address"]["country"]))
        b = CITY_TABLE.get((last["address"]["city"], last["address"]["country"]))
        if a and b:
            assert formula["distance_km"] == haversine_125(
                (a["lat"], a["lon"]), (b["lat"], b["lon"])
            )
            assert formula["rate"] == pytest.approx(
                spec_rate(first["address"]["country"], last["address"]["country"])
            )
            assert formula["lane"] == f"{first['address']['country']}->{last['address']['country']}"
        if "UNPROFITABLE_DETOUR" not in info["tags"]:
            log_noise.append(math.log(formula["noise"]))
    mean = sum(log_noise) / len(log_noise)
    deviation = (sum((x - mean) ** 2 for x in log_noise) / len(log_noise)) ** 0.5
    assert abs(mean) < 0.05 and 0.11 < deviation < 0.19  # log-normal, sigma = 0.15


@pytest.mark.ac("AC-FEAT-010-05")
@pytest.mark.parametrize(
    ("pallets", "weight_kg", "price"),
    [
        (1, 100, 60),  # 52.36 -> minimum fare
        (4, 400, 185),  # 340 x 0.4 x 1.36 = 184.96
        (10, 900, 340),  # full van
        (2, 1000, 340),  # weight-bound: share 1
    ],
)
def test_ltl_tariff_examples(pallets: int, weight_kg: int, price: int) -> None:
    assert ltl_price(0.85, 400.0, Decimal(pallets), weight_kg, 1.0) == price


@pytest.mark.ac("AC-FEAT-010-04")
def test_enrichment_records_the_generator_version() -> None:
    _, enrichment = committed()
    assert {info["generatorVersion"] for info in enrichment.values()} == {"offers-generator v3"}
