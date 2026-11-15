"""Zones, corridors and the consolidation-partner metric (FEAT-010 FR-7, §6.2, §6.3)."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from routepilot.freight.consolidation import (
    CORRIDORS,
    ZONES,
    consolidation_partners,
    partner_share,
)

ROOT = Path(__file__).resolve().parents[5]


def offer(
    offer_id: str,
    day: str,
    pickup: tuple[float, float] | None,
    delivery: tuple[float, float] | None,
    priced: bool = True,
) -> dict[str, Any]:
    def place(point: tuple[float, float] | None) -> dict[str, Any]:
        coordinate = {"latitude": point[0], "longitude": point[1]} if point else None
        return {"address": {"geoCoordinate": coordinate}, "earliestLoadingDate": day}

    raw: dict[str, Any] = {"id": offer_id, "loadingPlaces": [place(pickup), place(delivery)]}
    if priced:
        raw["price"] = {"amount": 100, "currency": "EUR"}
    return raw


# A and B: pickups 30 km apart on the same day, deliveries 100 km apart. C: another day.
A = offer("A", "2026-11-16", (50.0, 19.0), (51.0, 13.0))
B = offer("B", "2026-11-16", (50.27, 19.0), (51.9, 13.0))
C = offer("C", "2026-11-17", (50.0, 19.0), (51.0, 13.0))


@pytest.mark.ac("AC-FEAT-010-07")
def test_partners_share_the_day_and_have_close_pickups_and_deliveries() -> None:
    assert consolidation_partners([A, B, C]) == {"A": ["B"], "B": ["A"], "C": []}
    assert partner_share([A, B, C]) == Decimal("0.6667")
    # Each radius is a real limit: 30 km between the pickups, 100 km between the deliveries.
    assert consolidation_partners([A, B, C], pickup_km=29) == {"A": [], "B": [], "C": []}
    assert consolidation_partners([A, B, C], delivery_km=99) == {"A": [], "B": [], "C": []}
    assert consolidation_partners([A, B, C], pickup_km=31, delivery_km=101)["A"] == ["B"]


@pytest.mark.ac("AC-FEAT-010-07")
def test_offers_without_coordinates_have_no_partners_and_unpriced_offers_do_not_count() -> None:
    blind = offer("N", "2026-11-16", None, (51.0, 13.0))
    unpriced = offer("U", "2026-11-16", (50.0, 19.0), (51.0, 13.0), priced=False)
    partners = consolidation_partners([A, blind, unpriced])
    assert partners == {"A": ["U"], "N": [], "U": ["A"]}
    assert partner_share([A, blind, unpriced]) == Decimal("1.0000")  # only A is counted
    assert partner_share([blind]) == Decimal(0)


@pytest.mark.ac("AC-FEAT-010-07")
def test_the_committed_offers_reach_the_partner_share_target() -> None:
    offers = json.loads((ROOT / "data/mock/offers.timocom.json").read_text())["payload"]
    partners = consolidation_partners(offers)
    assert set(partners) == {o["id"] for o in offers}
    assert all(a in partners[b] for a, others in partners.items() for b in others)  # symmetric
    assert all(a not in others for a, others in partners.items())
    assert partner_share(offers) >= Decimal("0.50")


@pytest.mark.ac("AC-FEAT-010-06")
def test_every_city_is_in_exactly_one_zone_and_the_corridor_weights_follow_the_spec() -> None:
    cities = json.loads((ROOT / "data/mock/cities.json").read_text())["cities"]
    zoned = [name for members in ZONES.values() for name in members]
    assert len(ZONES) == 22 and sorted(zoned) == sorted(city["name"] for city in cities)
    country = {city["name"]: city["countryCode"] for city in cities}

    def polish(zone: str) -> bool:
        return all(country[name] == "PL" for name in ZONES[zone])

    assert len({(origin, destination) for origin, destination, _ in CORRIDORS}) == 35
    assert all(origin in ZONES and destination in ZONES for origin, destination, _ in CORRIDORS)
    weights = {"domestic": 0, "outbound": 0, "returns": 0}
    for origin, destination, weight in CORRIDORS:
        assert origin != destination and weight >= 1
        assert polish(origin) or polish(destination)  # Poland at one end of every lane
        kind = (
            "returns" if not polish(origin) else "domestic" if polish(destination) else "outbound"
        )
        weights[kind] += weight
    assert weights == {"domestic": 45, "outbound": 30, "returns": 25}
    by_lane = {(origin, destination): weight for origin, destination, weight in CORRIDORS}
    assert by_lane[("PL-SIL", "PL-CEN")] == 8 and by_lane[("PL-SIL", "DE-SAX")] == 6
    assert by_lane[("DE-SAX", "PL-SIL")] == 5 and by_lane[("DK", "PL-ZPM")] == 1
