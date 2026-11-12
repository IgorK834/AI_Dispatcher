"""CompositeRoutingProvider: repo matrix, then ORS, then haversine with fallback (FR-5)."""

import json
from pathlib import Path

import httpx
import pytest

from routepilot.optimization.engine import optimize
from routepilot.optimization.engine.models import EngineSnapshot
from routepilot.optimization.engine.models import TravelMatrix as EngineMatrix
from routepilot.routing.composite import CompositeRoutingProvider
from routepilot.routing.domain import GeoPoint
from routepilot.routing.matrix_file import MatrixFileRoutingProvider
from routepilot.routing.ors import OrsRoutingProvider
from tests.unit.optimization.factories import T, driver, offer, point

ROOT = Path(__file__).resolve().parents[5]
CITIES = json.loads((ROOT / "data/mock/cities.json").read_text())["cities"]
KATOWICE = GeoPoint(lat=50.2649, lon=19.0238)
WROCLAW = GeoPoint(lat=51.1079, lon=17.0385)
DRESDEN = GeoPoint(lat=51.0504, lon=13.7373)
CITY_POINTS = [KATOWICE, WROCLAW, DRESDEN]
# Two villages: more than 1 km from every one of the 39 cities.
OFF_GRID = [GeoPoint(lat=51.20, lon=18.00), GeoPoint(lat=51.45, lon=18.45)]
ORS_MATRIX = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures/ors/matrix.json").read_text()
)["response"]


def repo_matrix() -> MatrixFileRoutingProvider:
    return MatrixFileRoutingProvider(ROOT / "data/mock/routing-matrix.json", cities=CITIES)


class RecordingTransport:
    """An httpx transport that fails on any request and remembers that it was asked."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        raise httpx.ConnectError("offline test: no request is permitted", request=request)


@pytest.mark.ac("AC-FEAT-004-03")
def test_off_grid_point_without_a_key_comes_from_haversine_with_fallback() -> None:
    composite = CompositeRoutingProvider(matrix_file=repo_matrix())
    matrix = composite.matrix(OFF_GRID)
    assert matrix.fallback is True
    assert matrix.provider_id == "haversine_v1"
    assert matrix.distance_km[0][1] > 0


@pytest.mark.ac("AC-FEAT-004-03")
def test_a_plan_computed_on_a_fallback_matrix_carries_routing_fallback() -> None:
    routing = CompositeRoutingProvider(matrix_file=repo_matrix()).matrix(OFF_GRID)
    start = point("A", OFF_GRID[0].lat, OFF_GRID[0].lon)
    end = point("B", OFF_GRID[1].lat, OFF_GRID[1].lon)
    source = EngineSnapshot(
        reference_time=T,
        drivers=[driver(start, identifier="D")],
        offers=[offer("X", start, end, revenue=60000)],
        matrix=EngineMatrix(
            points=[start, end],
            distance_km=routing.distance_km,
            duration_min=routing.duration_min,
            provider_id=routing.provider_id,
            fallback=routing.fallback,
        ),
    )
    plans = optimize(source).per_driver["D"]["profit"]
    assert plans, "the instance is feasible on the fallback matrix"
    assert all("ROUTING_FALLBACK" in plan.warnings for plan in plans)


@pytest.mark.ac("AC-FEAT-004-03")
def test_a_plan_on_the_repo_matrix_does_not_carry_routing_fallback() -> None:
    routing = CompositeRoutingProvider(matrix_file=repo_matrix()).matrix([KATOWICE, WROCLAW])
    assert routing.fallback is False
    start = point("Katowice", KATOWICE.lat, KATOWICE.lon)
    end = point("Wroclaw", WROCLAW.lat, WROCLAW.lon)
    source = EngineSnapshot(
        reference_time=T,
        drivers=[driver(start, identifier="D")],
        offers=[offer("X", start, end, revenue=60000)],
        matrix=EngineMatrix(
            points=[start, end],
            distance_km=routing.distance_km,
            duration_min=routing.duration_min,
            provider_id=routing.provider_id,
            fallback=routing.fallback,
        ),
    )
    plans = optimize(source).per_driver["D"]["profit"]
    assert all("ROUTING_FALLBACK" not in plan.warnings for plan in plans)


@pytest.mark.ac("AC-FEAT-004-06")
def test_without_a_key_no_request_is_attempted_for_matrices_or_routes() -> None:
    transport = RecordingTransport()
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        composite = CompositeRoutingProvider(
            matrix_file=repo_matrix(), ors=OrsRoutingProvider(api_key="", client=client)
        )
        from_repo = composite.matrix(CITY_POINTS)
        from_haversine = composite.matrix(OFF_GRID)
        route = composite.route(CITY_POINTS, variant="FASTEST")
    assert transport.requests == [], "no HTTP request without ORS_API_KEY"
    assert from_repo.provider_id == "matrix_repo_v1" and from_repo.fallback is False
    assert from_haversine.provider_id == "haversine_v1" and from_haversine.fallback is True
    assert route.approximate is True and route.geometry["type"] == "LineString"


@pytest.mark.ac("AC-FEAT-004-06")
def test_a_composite_without_any_ors_provider_never_needs_a_transport() -> None:
    composite = CompositeRoutingProvider()
    assert composite.matrix(OFF_GRID).fallback is True
    assert composite.route(OFF_GRID, variant="FASTEST").approximate is True


@pytest.mark.ac("AC-FEAT-004-03")
def test_a_repo_matrix_hit_never_reaches_ors_even_with_a_key() -> None:
    transport = RecordingTransport()
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        composite = CompositeRoutingProvider(
            matrix_file=repo_matrix(),
            ors=OrsRoutingProvider(api_key="offline-test-value", client=client),
        )
        matrix = composite.matrix(CITY_POINTS)
    assert transport.requests == []
    assert matrix.provider_id == "matrix_repo_v1"


@pytest.mark.ac("AC-FEAT-004-03")
def test_an_off_grid_matrix_uses_ors_when_a_key_is_set_and_the_call_succeeds() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=ORS_MATRIX))
    ) as client:
        composite = CompositeRoutingProvider(
            matrix_file=repo_matrix(),
            ors=OrsRoutingProvider(api_key="offline-test-value", client=client),
        )
        matrix = composite.matrix([*OFF_GRID, OFF_GRID[0].model_copy(update={"lat": 51.3})])
    assert matrix.provider_id == "ors_driving_car_v1"
    assert matrix.fallback is False


@pytest.mark.ac("AC-FEAT-004-03", "AC-FEAT-004-06")
def test_the_matrix_file_provider_answers_routes_with_straight_lines() -> None:
    route = repo_matrix().route(CITY_POINTS, variant="FASTEST")
    assert route.approximate is True
    assert route.geometry["coordinates"][0] == [KATOWICE.lon, KATOWICE.lat]
