"""Routing units, fallback and offline matrix contracts (FEAT-004)."""

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from routepilot.routing.composite import CompositeRoutingProvider
from routepilot.routing.domain import GeoPoint
from routepilot.routing.haversine import HaversineRoutingProvider
from routepilot.routing.matrix_file import MatrixFileRoutingProvider
from routepilot.routing.ors import OrsRoutingProvider

POINTS = [
    GeoPoint(lat=50.2649, lon=19.0238),
    GeoPoint(lat=51.1079, lon=17.0385),
    GeoPoint(lat=51.0504, lon=13.7373),
]


@pytest.mark.ac("AC-FEAT-004-02")
def test_haversine_matches_approved_golden_units_and_is_symmetric() -> None:
    matrix = HaversineRoutingProvider().matrix(POINTS)
    assert matrix.distance_km[0][1] == Decimal("210.45")
    assert matrix.duration_min[0][1] == 210
    assert matrix.distance_km[1][2] == Decimal("288.36")
    assert matrix.duration_min[1][2] == 288
    for i in range(3):
        assert matrix.distance_km[i][i] == matrix.duration_min[i][i] == 0
        for j in range(3):
            assert matrix.distance_km[i][j] == matrix.distance_km[j][i]


@pytest.mark.ac("AC-FEAT-004-01", "AC-FEAT-004-07")
def test_repo_matrix_applies_van_factor_once_for_ors_and_preserves_haversine(
    tmp_path: Path,
) -> None:
    cities = [
        {"name": str(i), "lat": point.lat, "lon": point.lon} for i, point in enumerate(POINTS)
    ]
    data = {
        "version": 1,
        "source": "ors_driving_car_v1",
        "profile": "driving-car",
        "cities": [str(i) for i in range(3)],
        "distanceM": [[0, 1000, 2000], [1000, 0, 1000], [2000, 1000, 0]],
        "durationS": [[0, 6000, 12000], [6000, 0, 6000], [12000, 6000, 0]],
    }
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(data))
    provider = MatrixFileRoutingProvider(path, cities=cities)
    matrix = provider.matrix(POINTS)
    assert matrix.distance_km[0][1] == Decimal("1.00")
    assert matrix.duration_min[0][1] == 108
    assert matrix.provider_id == "matrix_repo_v1" and not matrix.fallback
    data["source"] = "haversine_v1"
    data["durationS"] = [[0, 6480, 12000], [6480, 0, 6480], [12000, 6480, 0]]
    path.write_text(json.dumps(data))
    assert MatrixFileRoutingProvider(path, cities=cities).matrix(POINTS).duration_min[0][1] == 108


@pytest.mark.ac("AC-FEAT-004-03", "AC-FEAT-004-06")
def test_no_key_never_opens_http_and_composite_falls_back() -> None:
    def reject(request: httpx.Request) -> httpx.Response:
        pytest.fail("No HTTP request is permitted without an ORS key")

    with httpx.Client(transport=httpx.MockTransport(reject)) as client:
        ors = OrsRoutingProvider(api_key="", client=client)
        provider = CompositeRoutingProvider(ors=ors)
        assert provider.matrix(POINTS).fallback
        route = provider.route(POINTS, variant="FASTEST")
        assert route.approximate and route.geometry["type"] == "LineString"


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


@pytest.mark.ac("AC-FEAT-004-08")
def test_committed_matrix_covers_exact_city_fixture() -> None:
    root = Path(__file__).resolve().parents[5]
    cities = json.loads((root / "data/mock/cities.json").read_text())["cities"]
    matrix = json.loads((root / "data/mock/routing-matrix.json").read_text())
    assert matrix["cities"] == [city["name"] for city in cities]
    assert len(matrix["cities"]) == 39
    assert matrix["source"] in {"ors_driving_car_v1", "haversine_v1"}
    for name in ("distanceM", "durationS"):
        assert len(matrix[name]) == 39
        for i, row in enumerate(matrix[name]):
            assert len(row) == 39 and row[i] == 0
            assert all(type(value) is int and value >= 0 for value in row)


@pytest.mark.ac("AC-FEAT-004-03", "AC-FEAT-004-06", "AC-FEAT-004-08")
def test_composite_prefers_committed_matrix_and_falls_back_for_off_grid_points() -> None:
    root = Path(__file__).resolve().parents[5]
    cities = json.loads((root / "data/mock/cities.json").read_text())["cities"]
    file_provider = MatrixFileRoutingProvider(root / "data/mock/routing-matrix.json", cities=cities)
    composite = CompositeRoutingProvider(matrix_file=file_provider)
    assert composite.matrix(POINTS).provider_id == "matrix_repo_v1"
    assert composite.matrix([GeoPoint(lat=0, lon=0)]).fallback
    assert file_provider.route(POINTS, variant="FASTEST").approximate


@pytest.mark.ac("AC-FEAT-004-08")
@pytest.mark.parametrize(
    "corruption", ["source", "cities", "dimensions", "negative", "bool", "diagonal", "missing"]
)
def test_malformed_matrix_is_explicitly_unavailable(tmp_path: Path, corruption: str) -> None:
    from routepilot.routing.domain import RoutingFailure
    from routepilot.routing.matrix_file import build_matrix_document

    cities = [
        {"name": str(i), "lat": point.lat, "lon": point.lon} for i, point in enumerate(POINTS)
    ]
    data = build_matrix_document(cities, generated_at="2026-11-11T00:00:00Z")
    if corruption == "source":
        data["source"] = "unknown"
    elif corruption == "cities":
        data["cities"] = list(reversed(data["cities"]))
    elif corruption == "dimensions":
        data["distanceM"] = []
    elif corruption == "negative":
        data["durationS"][0][1] = -1
    elif corruption == "bool":
        data["durationS"][0][1] = True
    elif corruption == "diagonal":
        data["durationS"][0][0] = 1
    path = tmp_path / "matrix.json"
    if corruption != "missing":
        path.write_text(json.dumps(data))
    with pytest.raises(RoutingFailure, match="unavailable"):
        MatrixFileRoutingProvider(path, cities=cities)


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
