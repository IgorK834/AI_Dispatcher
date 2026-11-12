"""HaversineRoutingProvider: golden conventions G1-G3 and straight-line routes (FR-4)."""

from decimal import Decimal

import pytest

from routepilot.routing.domain import GeoPoint
from routepilot.routing.haversine import HaversineRoutingProvider

KATOWICE = GeoPoint(lat=50.2649, lon=19.0238)
WROCLAW = GeoPoint(lat=51.1079, lon=17.0385)
DRESDEN = GeoPoint(lat=51.0504, lon=13.7373)
POINTS = [KATOWICE, WROCLAW, DRESDEN]


@pytest.mark.ac("AC-FEAT-004-02")
def test_demo_city_values_match_the_golden_conventions() -> None:
    matrix = HaversineRoutingProvider().matrix(POINTS)
    assert matrix.distance_km[0][1] == Decimal("210.45"), "Katowice -> Wroclaw km"
    assert matrix.duration_min[0][1] == 210, "Katowice -> Wroclaw min"
    assert matrix.distance_km[1][2] == Decimal("288.36"), "Wroclaw -> Dresden km"
    assert matrix.duration_min[1][2] == 288, "Wroclaw -> Dresden min"
    assert matrix.provider_id == "haversine_v1"


@pytest.mark.ac("AC-FEAT-004-02")
def test_a_point_to_itself_is_zero_and_the_matrix_is_symmetric() -> None:
    matrix = HaversineRoutingProvider().matrix(POINTS)
    for i in range(3):
        assert matrix.distance_km[i][i] == 0 and matrix.duration_min[i][i] == 0
        for j in range(3):
            assert matrix.distance_km[i][j] == matrix.distance_km[j][i]
            assert matrix.duration_min[i][j] == matrix.duration_min[j][i]


@pytest.mark.ac("AC-FEAT-004-02")
def test_distances_have_two_decimals_and_durations_are_whole_minutes() -> None:
    matrix = HaversineRoutingProvider().matrix(POINTS)
    for row in matrix.distance_km:
        assert all(value == value.quantize(Decimal("0.01")) for value in row)
    for row in matrix.duration_min:
        assert all(isinstance(value, int) for value in row)


@pytest.mark.ac("AC-FEAT-004-02")
def test_the_van_speed_factor_multiplies_time_and_not_distance() -> None:
    slower = HaversineRoutingProvider(Decimal("1.08")).matrix(POINTS)
    faster = HaversineRoutingProvider(Decimal("1.0")).matrix(POINTS)
    assert slower.distance_km == faster.distance_km
    assert faster.duration_min[0][1] == 195, "ceil(210.45 x 60 x 1.0 / 65)"
    assert slower.duration_min[0][1] == 210


@pytest.mark.ac("AC-FEAT-004-02")
def test_route_is_one_straight_line_through_the_waypoints_and_marked_approximate() -> None:
    route = HaversineRoutingProvider().route(POINTS, variant="FASTEST")
    assert route.approximate is True
    assert route.geometry == {
        "type": "LineString",
        "coordinates": [[19.0238, 50.2649], [17.0385, 51.1079], [13.7373, 51.0504]],
    }
    assert route.distance_km == Decimal("210.45") + Decimal("288.36")
    assert route.duration_min == 210 + 288
