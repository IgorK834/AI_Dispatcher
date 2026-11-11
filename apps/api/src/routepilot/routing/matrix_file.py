"""Committed matrix adapter and deterministic haversine-file generation."""

import json
from collections.abc import Sequence
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any

from routepilot.routing.domain import (
    GeoPoint,
    RouteResult,
    RouteVariant,
    RoutingFailure,
    TravelMatrix,
)
from routepilot.routing.haversine import HaversineRoutingProvider, haversine_km
from routepilot.shared.rounding import round_half_up


def build_matrix_document(cities: list[dict[str, Any]], *, generated_at: str) -> dict[str, Any]:
    matrix = HaversineRoutingProvider().matrix(
        [GeoPoint(lat=c["lat"], lon=c["lon"]) for c in cities]
    )
    return {
        "version": 1,
        "source": "haversine_v1",
        "profile": "driving-car",
        "generatedAt": generated_at,
        "cities": [c["name"] for c in cities],
        "distanceM": [[int(km * 1000) for km in row] for row in matrix.distance_km],
        "durationS": [[minutes * 60 for minutes in row] for row in matrix.duration_min],
    }


class MatrixFileRoutingProvider:
    provider_id = "matrix_repo_v1"

    def __init__(
        self,
        path: Path,
        *,
        cities: list[dict[str, Any]],
        van_speed_factor: Decimal = Decimal("1.08"),
    ) -> None:
        self.van_speed_factor = van_speed_factor
        try:
            self.data = json.loads(path.read_text())
            if self.data["source"] not in ("haversine_v1", "ors_driving_car_v1"):
                raise ValueError("unknown matrix source")
            names = [c["name"] for c in cities]
            if self.data["cities"] != names:
                raise ValueError("matrix city order differs")
            count = len(cities)
            for field in ("distanceM", "durationS"):
                rows = self.data[field]
                if len(rows) != count or any(len(row) != count for row in rows):
                    raise ValueError("matrix dimensions differ")
                if any(
                    not isinstance(v, int) or isinstance(v, bool) or v < 0
                    for row in rows
                    for v in row
                ):
                    raise ValueError("matrix entries must be non-negative integers")
                if any(rows[i][i] != 0 for i in range(count)):
                    raise ValueError("matrix diagonal must be zero")
            self.points = [GeoPoint(lat=c["lat"], lon=c["lon"]) for c in cities]
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise RoutingFailure("Committed routing matrix is unavailable") from error

    def matrix(self, points: Sequence[GeoPoint]) -> TravelMatrix:
        indices = []
        for point in points:
            match = next(
                (
                    i
                    for i, candidate in enumerate(self.points)
                    if haversine_km(point, candidate) <= 1
                ),
                None,
            )
            if match is None:
                raise RoutingFailure("Point is outside the committed matrix")
            indices.append(match)
        factor = (
            self.van_speed_factor if self.data["source"] == "ors_driving_car_v1" else Decimal(1)
        )
        return TravelMatrix(
            distance_km=[
                [round_half_up(Decimal(self.data["distanceM"][i][j]) / 1000) for j in indices]
                for i in indices
            ],
            duration_min=[
                [
                    int(
                        (Decimal(self.data["durationS"][i][j]) * factor / 60).to_integral_value(
                            rounding=ROUND_CEILING
                        )
                    )
                    for j in indices
                ]
                for i in indices
            ],
            provider_id=self.provider_id,
            fallback=False,
        )

    def route(
        self, waypoints: Sequence[GeoPoint], *, variant: RouteVariant = "FASTEST"
    ) -> RouteResult:
        # The matrix stores no road geometry; the composite's route chain uses ORS first.
        return HaversineRoutingProvider(self.van_speed_factor).route(waypoints, variant=variant)
