"""Deterministic road-distance estimate, FEAT-004 FR-4."""

from collections.abc import Sequence
from decimal import ROUND_CEILING, Decimal
from math import asin, cos, radians, sin, sqrt

from routepilot.routing.domain import GeoPoint, RouteResult, RouteVariant, TravelMatrix
from routepilot.shared.rounding import round_half_up


def haversine_km(first: GeoPoint, second: GeoPoint) -> Decimal:
    latitude = radians(second.lat - first.lat)
    longitude = radians(second.lon - first.lon)
    a = (
        sin(latitude / 2) ** 2
        + cos(radians(first.lat)) * cos(radians(second.lat)) * sin(longitude / 2) ** 2
    )
    # Mean Earth radius fixed by approved golden convention G1.
    return Decimal(str(6371.0088 * 2 * asin(min(1, sqrt(a)))))


class HaversineRoutingProvider:
    provider_id = "haversine_v1"

    def __init__(self, van_speed_factor: Decimal = Decimal("1.08")) -> None:
        self.van_speed_factor = van_speed_factor

    def matrix(self, points: Sequence[GeoPoint]) -> TravelMatrix:
        distances = [
            [round_half_up(haversine_km(a, b) * Decimal("1.25")) for b in points] for a in points
        ]
        durations = [
            [
                int(
                    (km * 60 * self.van_speed_factor / 65).to_integral_value(rounding=ROUND_CEILING)
                )
                for km in row
            ]
            for row in distances
        ]
        return TravelMatrix(
            distance_km=distances,
            duration_min=durations,
            provider_id=self.provider_id,
            fallback=True,
        )

    def route(
        self, waypoints: Sequence[GeoPoint], *, variant: RouteVariant = "FASTEST"
    ) -> RouteResult:
        matrix = self.matrix(waypoints)
        return RouteResult(
            distance_km=sum(
                (matrix.distance_km[i][i + 1] for i in range(len(waypoints) - 1)), Decimal(0)
            ),
            duration_min=sum(matrix.duration_min[i][i + 1] for i in range(len(waypoints) - 1)),
            geometry={"type": "LineString", "coordinates": [[p.lon, p.lat] for p in waypoints]},
            approximate=True,
        )
