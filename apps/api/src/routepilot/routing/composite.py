"""Offline-first provider chain from FEAT-004 FR-5."""

from collections.abc import Sequence

import structlog

from routepilot.routing.domain import (
    GeoPoint,
    RouteResult,
    RouteVariant,
    RoutingFailure,
    TravelMatrix,
)
from routepilot.routing.haversine import HaversineRoutingProvider
from routepilot.routing.matrix_file import MatrixFileRoutingProvider
from routepilot.routing.ors import OrsRoutingProvider


class CompositeRoutingProvider:
    provider_id = "composite_v1"

    def __init__(
        self,
        matrix_file: MatrixFileRoutingProvider | None = None,
        ors: OrsRoutingProvider | None = None,
        haversine: HaversineRoutingProvider | None = None,
    ) -> None:
        self.matrix_file = matrix_file
        self.ors = ors
        self.haversine = haversine or HaversineRoutingProvider()

    def matrix(self, points: Sequence[GeoPoint]) -> TravelMatrix:
        if self.matrix_file is not None:
            try:
                return self.matrix_file.matrix(points)
            except RoutingFailure:
                structlog.get_logger(__name__).info("routing_fallback", provider="matrix_repo_v1")
        if self.ors is not None and self.ors.enabled:
            try:
                return self.ors.matrix(points)
            except RoutingFailure:
                structlog.get_logger(__name__).info(
                    "routing_fallback", provider="ors_driving_car_v1"
                )
        return self.haversine.matrix(points)

    def route(
        self, waypoints: Sequence[GeoPoint], *, variant: RouteVariant = "FASTEST"
    ) -> RouteResult:
        if self.ors is not None and self.ors.enabled:
            try:
                return self.ors.route(waypoints, variant=variant)
            except RoutingFailure:
                structlog.get_logger(__name__).info(
                    "routing_fallback", provider="ors_driving_car_v1"
                )
        return self.haversine.route(waypoints, variant=variant)
