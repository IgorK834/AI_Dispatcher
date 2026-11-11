"""Synthetic golden routing and compact snapshots for engine tests."""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from math import asin, cos, radians, sin, sqrt

from routepilot.compliance.models import DriverState
from routepilot.optimization.engine.costs import rounded
from routepilot.optimization.engine.models import (
    CostProfile,
    DriverSnapshot,
    EngineSnapshot,
    OfferSnapshot,
    Point,
    Stop,
    TravelMatrix,
    VehicleSnapshot,
)

T = datetime(2026, 11, 16, 5, tzinfo=UTC)


def point(key: str, lat: float = 51.7592, lon: float = 19.4560, country: str = "PL") -> Point:
    return Point(key=key, city=key, country=country, lat=lat, lon=lon)


def matrix(points: list[Point]) -> TravelMatrix:
    distances = []
    durations = []
    for start in points:
        row = []
        minutes = []
        for end in points:
            a, b = radians(start.lat or 0), radians(end.lat or 0)
            dlat, dlon = b - a, radians((end.lon or 0) - (start.lon or 0))
            great_circle = (
                2
                * 6371.0088
                * asin(sqrt(sin(dlat / 2) ** 2 + cos(a) * cos(b) * sin(dlon / 2) ** 2))
            )
            distance = rounded(Decimal(str(great_circle)) * Decimal("1.25"), 2)
            row.append(distance)
            minutes.append(
                int(
                    (distance * 60 * Decimal("1.08") / 65).to_integral_value(rounding=ROUND_CEILING)
                )
            )
        distances.append(row)
        durations.append(minutes)
    return TravelMatrix(points=points, distance_km=distances, duration_min=durations)


def driver(
    home: Point,
    *,
    identifier: str = "D",
    available: datetime = T,
    payload: int = 1085,
    pallets: int = 10,
    home_by: datetime | None = None,
) -> DriverSnapshot:
    return DriverSnapshot(
        id=identifier,
        home=home,
        position=home,
        available_from=available,
        home_by=home_by,
        vehicle=VehicleSnapshot(payload_kg=payload, pallet_places=pallets),
        cost_profile=CostProfile(),
        rules_state=DriverState(t=available),
    )


def offer(
    identifier: str,
    start: Point,
    end: Point,
    *,
    weight: int = 200,
    pallets: int = 2,
    revenue: int = 30000,
    pickup: tuple[datetime, datetime] = (T, T + timedelta(hours=1)),
    delivery: tuple[datetime, datetime] = (T + timedelta(hours=2), T + timedelta(hours=8)),
    pallet_type: str = "EUR_1200x800",
) -> OfferSnapshot:
    return OfferSnapshot(
        id=identifier,
        weight_kg=weight,
        pallet_count=pallets,
        revenue_minor=revenue,
        pallet_type=pallet_type,
        stops=(
            Stop(point=start, window_start=pickup[0], window_end=pickup[1]),
            Stop(point=end, window_start=delivery[0], window_end=delivery[1]),
        ),
    )


def snapshot(drivers: list[DriverSnapshot], offers: list[OfferSnapshot]) -> EngineSnapshot:
    points = {p.key: p for d in drivers for p in (d.home, d.position)}
    points.update({s.point.key: s.point for o in offers for s in o.stops})
    return EngineSnapshot(
        reference_time=T, drivers=drivers, offers=offers, matrix=matrix(list(points.values()))
    )
