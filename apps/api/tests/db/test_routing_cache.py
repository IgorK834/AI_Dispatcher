"""ORS response reuse uses canonical coordinates and persistent storage."""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from routepilot.routing.cache import RoutingCache, RoutingCacheRow, request_key
from routepilot.routing.domain import GeoPoint, RoutingFailure
from routepilot.routing.ors import OrsRoutingProvider
from routepilot.shared.clock import FixedClock
from routepilot.shared.db.engine import make_engine


@pytest.mark.ac("AC-FEAT-004-05")
def test_cached_response_survives_provider_recreation_and_precision_noise() -> None:
    engine = make_engine("sqlite:///:memory:")
    RoutingCacheRow.__table__.create(engine)
    cache = RoutingCache(engine, FixedClock(datetime(2026, 11, 16, tzinfo=UTC)))
    points = [GeoPoint(lat=50.2649, lon=19.0238), GeoPoint(lat=51.1079, lon=17.0385)]
    calls = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200, json={"distances": [[0, 10000], [10000, 0]], "durations": [[0, 6000], [6000, 0]]}
        )

    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        first = OrsRoutingProvider(api_key="offline-test-value", cache=cache, client=client).matrix(
            points
        )
    noisy = [p.model_copy(update={"lat": p.lat + 0.0000001}) for p in points]

    def reject(request: httpx.Request) -> httpx.Response:
        pytest.fail("A persisted cache hit must not call HTTP")

    with httpx.Client(transport=httpx.MockTransport(reject)) as client:
        second = OrsRoutingProvider(
            api_key="offline-test-value", cache=cache, client=client
        ).matrix(noisy)
    assert len(calls) == 1
    assert first == second
    assert second.duration_min[0][1] == 108
    engine.dispose()


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ors"
RECORDED_MATRIX = json.loads((FIXTURES / "matrix.json").read_text())["response"]
RECORDED_ROUTE = json.loads((FIXTURES / "directions.json").read_text())["response"]
CITIES = [
    GeoPoint(lat=50.2649, lon=19.0238),
    GeoPoint(lat=51.1079, lon=17.0385),
    GeoPoint(lat=51.0504, lon=13.7373),
]


def cache_with_table() -> tuple[Engine, RoutingCache]:
    engine = make_engine("sqlite:///:memory:")
    RoutingCacheRow.__table__.create(engine)
    return engine, RoutingCache(engine, FixedClock(datetime(2026, 11, 16, tzinfo=UTC)))


def recorded_transport(calls: list[httpx.Request]) -> httpx.MockTransport:
    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        body = RECORDED_MATRIX if "/matrix/" in request.url.path else RECORDED_ROUTE
        return httpx.Response(200, json=body)

    return httpx.MockTransport(reply)


@pytest.mark.ac("AC-FEAT-004-05")
def test_a_recorded_route_response_is_stored_and_served_without_http() -> None:
    engine, cache = cache_with_table()
    calls: list[httpx.Request] = []
    with httpx.Client(transport=recorded_transport(calls)) as client:
        provider = OrsRoutingProvider(api_key="offline-test-value", cache=cache, client=client)
        first = provider.route(CITIES, variant="FASTEST")
        second = provider.route(CITIES, variant="FASTEST")
    assert len(calls) == 1, "the second route request is served from routing_cache"
    assert first == second
    assert first.approximate is False
    with Session(engine) as session:
        rows = session.scalars(select(RoutingCacheRow)).all()
    assert [(row.kind, row.provider_version) for row in rows] == [("route", "ors_driving_car_v1")]
    engine.dispose()


@pytest.mark.ac("AC-FEAT-004-05")
def test_coordinates_equal_at_five_decimals_share_an_entry_and_a_fifth_decimal_does_not() -> None:
    engine, cache = cache_with_table()
    calls: list[httpx.Request] = []
    with httpx.Client(transport=recorded_transport(calls)) as client:
        provider = OrsRoutingProvider(api_key="offline-test-value", cache=cache, client=client)
        provider.matrix(CITIES)
        same_at_five = [p.model_copy(update={"lon": p.lon + 0.000004}) for p in CITIES]
        provider.matrix(same_at_five)
        assert len(calls) == 1, "a change beyond the fifth decimal is the same cache key"
        different = [p.model_copy(update={"lon": p.lon + 0.0001}) for p in CITIES]
        provider.matrix(different)
        assert len(calls) == 2, "a change in the fifth decimal is a different cache key"
    engine.dispose()


@pytest.mark.ac("AC-FEAT-004-05")
def test_failed_or_invalid_responses_are_never_stored() -> None:
    engine, cache = cache_with_table()
    statuses = iter([429, 429, 429])
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(next(statuses)))
    ) as client:
        provider = OrsRoutingProvider(
            api_key="offline-test-value", cache=cache, client=client, sleep=lambda seconds: None
        )
        with pytest.raises(RoutingFailure):
            provider.matrix(CITIES)
    bad = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"durations": [[None] * 3] * 3, "distances": [[0]]}
        )
    )
    with httpx.Client(transport=bad) as client:
        provider = OrsRoutingProvider(api_key="offline-test-value", cache=cache, client=client)
        with pytest.raises(RoutingFailure):
            provider.matrix(CITIES)
    with Session(engine) as session:
        assert session.scalars(select(RoutingCacheRow)).all() == []
    engine.dispose()


@pytest.mark.ac("AC-FEAT-004-05")
def test_the_key_depends_on_kind_options_and_points() -> None:
    base = request_key("matrix", CITIES, {"units": "m"})
    assert base == request_key("matrix", CITIES, {"units": "m"})
    assert base != request_key("route", CITIES, {"units": "m"})
    assert base != request_key("matrix", CITIES, {"units": "km"})
    assert base != request_key("matrix", CITIES[:2], {"units": "m"})
    assert len(base) == 64 and all(character in "0123456789abcdef" for character in base)
