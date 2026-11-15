"""Zones, corridors and the consolidation-partner metric of the demo offers (FEAT-010)."""

import math
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from routepilot.freight.places import ZONES

__all__ = ["CORRIDORS", "ZONES", "consolidation_partners", "partner_share"]

# FEAT-010 section 6.3: (origin zone, destination zone, weight); the weights total 100 (assumption).
CORRIDORS: tuple[tuple[str, str, int], ...] = (
    # domestic (45)
    ("PL-SIL", "PL-CEN", 8),
    ("PL-CEN", "PL-SIL", 6),
    ("PL-SIL", "PL-OPW", 5),
    ("PL-OPW", "PL-SIL", 5),
    ("PL-WLK", "PL-CEN", 4),
    ("PL-CEN", "PL-WLK", 3),
    ("PL-CEN", "PL-POM", 4),
    ("PL-POM", "PL-CEN", 3),
    ("PL-OPW", "PL-WLK", 3),
    ("PL-WLK", "PL-OPW", 2),
    ("PL-SIL", "PL-PDK", 1),
    ("PL-ZPM", "PL-WLK", 1),
    # outbound (30)
    ("PL-SIL", "DE-SAX", 6),
    ("PL-OPW", "DE-SAX", 4),
    ("PL-SIL", "CZ-BOH", 3),
    ("PL-SIL", "MOR-SIL", 2),
    ("PL-SIL", "DANUBE", 3),
    ("PL-SIL", "HU-BUD", 2),
    ("PL-WLK", "DE-BER", 3),
    ("PL-WLK", "DE-NOR", 3),
    ("PL-CEN", "BENELUX", 2),
    ("PL-OPW", "DE-SOU", 1),
    ("PL-SIL", "IT-NOR", 1),
    # returns (25)
    ("DE-SAX", "PL-SIL", 5),
    ("DE-SAX", "PL-OPW", 3),
    ("CZ-BOH", "PL-SIL", 2),
    ("MOR-SIL", "PL-SIL", 2),
    ("DANUBE", "PL-SIL", 2),
    ("HU-BUD", "PL-SIL", 1),
    ("DE-BER", "PL-WLK", 3),
    ("DE-NOR", "PL-WLK", 2),
    ("BENELUX", "PL-CEN", 2),
    ("DE-RHM", "PL-OPW", 1),
    ("UPPER-RHINE", "PL-SIL", 1),
    ("DK", "PL-ZPM", 1),
)

Offer = Mapping[str, Any]  # a raw offer in the TIMOCOM v3 shape of the generator


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    value = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371 * 2 * math.asin(min(1, math.sqrt(value)))


def _points(offer: Offer) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Pickup and delivery coordinates, or None when a stop has none."""
    coordinates = [place["address"].get("geoCoordinate") for place in offer["loadingPlaces"]]
    if len(coordinates) != 2 or not all(coordinates):
        return None
    first, last = ((point["latitude"], point["longitude"]) for point in coordinates)
    return first, last


def consolidation_partners(
    offers: Sequence[Offer], pickup_km: float = 80, delivery_km: float = 150
) -> dict[str, list[str]]:
    """Offers loaded on the same day with pickups and deliveries close together (FR-7)."""
    partners: dict[str, list[str]] = {offer["id"]: [] for offer in offers}
    located = [(offer, points) for offer in offers if (points := _points(offer)) is not None]
    for index, (a, (a_pickup, a_delivery)) in enumerate(located):
        for b, (b_pickup, b_delivery) in located[index + 1 :]:
            if (
                a["loadingPlaces"][0]["earliestLoadingDate"]
                == b["loadingPlaces"][0]["earliestLoadingDate"]
                and _haversine_km(a_pickup, b_pickup) <= pickup_km
                and _haversine_km(a_delivery, b_delivery) <= delivery_km
            ):
                partners[a["id"]].append(b["id"])
                partners[b["id"]].append(a["id"])
    return partners


def partner_share(
    offers: Sequence[Offer], pickup_km: float = 80, delivery_km: float = 150
) -> Decimal:
    """Share of the priced offers with coordinates that have at least one partner (FR-7)."""
    partners = consolidation_partners(offers, pickup_km, delivery_km)
    eligible = [o["id"] for o in offers if "price" in o and _points(o) is not None]
    if not eligible:
        return Decimal(0)
    with_partner = sum(1 for offer_id in eligible if partners[offer_id])
    return (Decimal(with_partner) / Decimal(len(eligible))).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
