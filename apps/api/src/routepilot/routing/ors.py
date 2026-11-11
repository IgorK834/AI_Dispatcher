"""ORS v2 driving-car adapter; only recorded transports are used in tests."""

import time
from collections import deque
from collections.abc import Callable, Sequence
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from typing import Any

import httpx

from routepilot.routing.cache import RoutingCache, request_key
from routepilot.routing.domain import (
    GeoPoint,
    RouteResult,
    RouteVariant,
    RoutingFailure,
    TravelMatrix,
)
from routepilot.shared.rounding import round_half_up


class OrsRoutingProvider:
    provider_id = "ors_driving_car_v1"

    def __init__(
        self,
        *,
        api_key: str,
        client: httpx.Client | None = None,
        cache: RoutingCache | None = None,
        base_url: str = "https://api.openrouteservice.org",
        van_speed_factor: Decimal = Decimal("1.08"),
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._api_key = api_key
        self._client = client
        self.cache = cache
        self.base_url = base_url.rstrip("/")
        self.van_speed_factor = van_speed_factor
        self._sleep = sleep
        self._monotonic = monotonic
        self._recent: deque[float] = deque()

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    def _request(
        self, kind: str, points: Sequence[GeoPoint], options: dict[str, Any]
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RoutingFailure("ORS is disabled")
        key = request_key(kind, points, options)
        cached = self.cache.get(key) if self.cache is not None else None
        if cached is not None:
            return cached
        endpoint = (
            "/v2/matrix/driving-car" if kind == "matrix" else "/v2/directions/driving-car/geojson"
        )
        body = {
            **options,
            "locations" if kind == "matrix" else "coordinates": [[p.lon, p.lat] for p in points],
        }
        client = self._client or httpx.Client(timeout=30, follow_redirects=False, trust_env=False)
        try:
            for attempt in range(3):
                now = self._monotonic()
                while self._recent and now - self._recent[0] >= 60:
                    self._recent.popleft()
                if len(self._recent) >= 30:
                    self._sleep(max(0, 60 - (now - self._recent[0])))
                    self._recent.popleft()
                self._recent.append(self._monotonic())
                try:
                    response = client.post(
                        self.base_url + endpoint,
                        json=body,
                        headers={"Authorization": self._api_key},
                    )
                except httpx.HTTPError:
                    if attempt == 2:
                        raise RoutingFailure("ORS transport failed") from None
                else:
                    if response.status_code == 200:
                        try:
                            payload = response.json()
                            if not isinstance(payload, dict):
                                raise ValueError("object required")
                            self._parse(kind, points, payload)
                        except (ValueError, KeyError, TypeError, IndexError, InvalidOperation):
                            raise RoutingFailure("ORS returned incomplete routing data") from None
                        if self.cache is not None:
                            self.cache.put(key, kind, payload)
                        return payload
                    if response.status_code != 429 and response.status_code < 500:
                        raise RoutingFailure("ORS request was rejected")
                    if attempt == 2:
                        raise RoutingFailure("ORS remained unavailable")
                self._sleep((0.25, 0.5)[attempt])
        finally:
            if self._client is None:
                client.close()
        raise RoutingFailure("ORS remained unavailable")

    def _parse(
        self, kind: str, points: Sequence[GeoPoint], payload: dict[str, Any]
    ) -> TravelMatrix | RouteResult:
        def duration(seconds: Any) -> int:
            value = Decimal(str(seconds))
            if not value.is_finite() or value < 0:
                raise ValueError("invalid duration")
            return int(
                (value * self.van_speed_factor / 60).to_integral_value(rounding=ROUND_CEILING)
            )

        def distance(metres: Any) -> Decimal:
            value = Decimal(str(metres))
            if not value.is_finite() or value < 0:
                raise ValueError("invalid distance")
            return round_half_up(value / 1000)

        if kind == "matrix":
            distances, durations = payload["distances"], payload["durations"]
            if any(
                len(rows) != len(points) or any(len(row) != len(points) for row in rows)
                for rows in (distances, durations)
            ):
                raise ValueError("matrix dimensions differ")
            return TravelMatrix(
                distance_km=[[distance(v) for v in row] for row in distances],
                duration_min=[[duration(v) for v in row] for row in durations],
                provider_id=self.provider_id,
                fallback=False,
            )
        feature = payload["features"][0]
        geometry = feature["geometry"]
        if geometry["type"] != "LineString" or len(geometry["coordinates"]) < 2:
            raise ValueError("invalid geometry")
        for coordinate in geometry["coordinates"]:
            GeoPoint(lon=coordinate[0], lat=coordinate[1])
        summary = feature["properties"]["summary"]
        return RouteResult(
            distance_km=distance(summary["distance"]),
            duration_min=duration(summary["duration"]),
            geometry={"type": "LineString", "coordinates": geometry["coordinates"]},
            approximate=False,
        )

    def matrix(self, points: Sequence[GeoPoint]) -> TravelMatrix:
        if len(points) ** 2 > 3500:
            raise RoutingFailure("ORS matrix exceeds 3500 elements")
        payload = self._request(
            "matrix", points, {"metrics": ["distance", "duration"], "units": "m"}
        )
        result = self._parse("matrix", points, payload)
        if not isinstance(result, TravelMatrix):
            raise RoutingFailure("ORS returned the wrong routing kind")
        return result

    def route(
        self, waypoints: Sequence[GeoPoint], *, variant: RouteVariant = "FASTEST"
    ) -> RouteResult:
        payload = self._request(
            "route", waypoints, {"preference": "fastest", "instructions": False, "units": "m"}
        )
        result = self._parse("route", waypoints, payload)
        if not isinstance(result, RouteResult):
            raise RoutingFailure("ORS returned the wrong routing kind")
        return result
