"""Provider port from FEAT-004 FR-1."""

from collections.abc import Sequence
from typing import Protocol

from routepilot.routing.domain import GeoPoint, RouteResult, RouteVariant, TravelMatrix


class RoutingProvider(Protocol):
    provider_id: str

    def matrix(self, points: Sequence[GeoPoint]) -> TravelMatrix: ...

    def route(self, waypoints: Sequence[GeoPoint], *, variant: RouteVariant) -> RouteResult: ...
