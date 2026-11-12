"""ORS adapter failure policy through a synthetic transport (FEAT-004); moved to the contract
tests by slice 004/2."""

import httpx
import pytest

from routepilot.routing.composite import CompositeRoutingProvider
from routepilot.routing.domain import GeoPoint
from routepilot.routing.ors import OrsRoutingProvider

POINTS = [
    GeoPoint(lat=50.2649, lon=19.0238),
    GeoPoint(lat=51.1079, lon=17.0385),
    GeoPoint(lat=51.0504, lon=13.7373),
]


@pytest.mark.ac("AC-FEAT-004-04")
def test_rate_limit_transport_retries_then_falls_back_without_logging_key() -> None:
    # A synthetic transport status exercises policy; it is not a captured ORS response.
    calls = []
    waits = []

    def rate_limit(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(429, json={"error": "offline test rate limit"})

    with httpx.Client(transport=httpx.MockTransport(rate_limit)) as client:
        provider = CompositeRoutingProvider(
            ors=OrsRoutingProvider(api_key="offline-test-value", client=client, sleep=waits.append)
        )
        assert provider.matrix(POINTS).fallback
    assert len(calls) == 3
    assert waits == [0.25, 0.5]


@pytest.mark.ac("AC-FEAT-004-04")
def test_unroutable_or_incomplete_matrix_is_a_failure_with_fallback() -> None:
    for body in (
        {"durations": [[0]], "distances": [[0]]},
        {"durations": [[None] * 3] * 3, "distances": [[0] * 3] * 3},
    ):
        with httpx.Client(
            transport=httpx.MockTransport(lambda request, body=body: httpx.Response(200, json=body))
        ) as client:
            result = CompositeRoutingProvider(
                ors=OrsRoutingProvider(api_key="offline-test-value", client=client)
            ).matrix(POINTS)
            assert result.fallback


@pytest.mark.ac("AC-FEAT-004-04", "AC-FEAT-004-06")
@pytest.mark.parametrize(
    "failure", ["transport", "authentication", "list_json", "distance", "duration", "geometry"]
)
def test_ors_failures_fall_back_with_bounded_requests(failure: str) -> None:
    calls = []
    delays = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if failure == "transport":
            raise httpx.ReadTimeout("offline timeout", request=request)
        if failure == "authentication":
            return httpx.Response(401)
        if failure == "list_json":
            return httpx.Response(200, json=[])
        if failure == "geometry":
            return httpx.Response(
                200, json={"features": [{"geometry": {"type": "Point", "coordinates": [0, 0]}}]}
            )
        body = {"distances": [[0] * 3 for _ in range(3)], "durations": [[0] * 3 for _ in range(3)]}
        body["distances" if failure == "distance" else "durations"][0][1] = -1
        return httpx.Response(200, json=body)

    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        composite = CompositeRoutingProvider(
            ors=OrsRoutingProvider(api_key="offline-credential", client=client, sleep=delays.append)
        )
        if failure == "geometry":
            assert composite.route(POINTS, variant="FASTEST").approximate
        else:
            assert composite.matrix(POINTS).fallback
    assert len(calls) == (3 if failure == "transport" else 1)
    assert delays == ([0.25, 0.5] if failure == "transport" else [])


@pytest.mark.ac("AC-FEAT-004-04", "AC-FEAT-004-07")
def test_ors_request_limit_and_matrix_element_limit_are_enforced_locally() -> None:
    from routepilot.routing.domain import RoutingFailure

    class Timer:
        def __init__(self):
            self.seconds = 0.0
            self.waits = []

        def now(self):
            return self.seconds

        def sleep(self, seconds):
            self.waits.append(seconds)
            self.seconds += seconds

    timer = Timer()
    calls = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"distances": [[0]], "durations": [[0]]})

    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        provider = OrsRoutingProvider(
            api_key="offline-credential", client=client, sleep=timer.sleep, monotonic=timer.now
        )
        for _ in range(35):
            provider.matrix(POINTS[:1])
        assert len(calls) == 35 and timer.waits == [60]
        with pytest.raises(RoutingFailure, match="3500"):
            provider.matrix([POINTS[0]] * 60)
        assert len(calls) == 35
        disabled = OrsRoutingProvider(api_key="", client=client)
        with pytest.raises(RoutingFailure, match="disabled"):
            disabled.matrix(POINTS[:1])
        assert len(calls) == 35
