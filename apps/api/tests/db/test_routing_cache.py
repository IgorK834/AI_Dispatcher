"""ORS response reuse uses canonical coordinates and persistent storage."""

from datetime import UTC, datetime

import httpx
import pytest

from routepilot.routing.cache import RoutingCache, RoutingCacheRow
from routepilot.routing.domain import GeoPoint
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
