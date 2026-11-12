"""MatrixFileRoutingProvider: city matching, ORS factor applied once, malformed files (FR-2)."""

import json
from decimal import Decimal
from fractions import Fraction
from math import ceil
from pathlib import Path

import pytest

from routepilot.routing.domain import GeoPoint, RoutingFailure
from routepilot.routing.matrix_file import MatrixFileRoutingProvider, build_matrix_document

ROOT = Path(__file__).resolve().parents[5]
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/routing/matrix_ors_small.json"
CITIES = {c["name"]: c for c in json.loads((ROOT / "data/mock/cities.json").read_text())["cities"]}
SMALL = [CITIES[name] for name in ("Katowice", "Wrocław", "Dresden")]
POINTS = [GeoPoint(lat=c["lat"], lon=c["lon"]) for c in SMALL]


@pytest.mark.ac("AC-FEAT-004-01")
def test_ors_sourced_matrix_gives_file_km_ceiled_minutes_and_provider_id() -> None:
    # The committed file is the haversine variant (OQ-004-02), so AC-01 runs on an ORS-shaped file.
    data = json.loads(FIXTURE.read_text())
    matrix = MatrixFileRoutingProvider(FIXTURE, cities=SMALL).matrix(POINTS)
    for i in range(3):
        for j in range(3):
            assert matrix.distance_km[i][j] == (Decimal(data["distanceM"][i][j]) / 1000).quantize(
                Decimal("0.01")
            ), f"distance {i}->{j}"
            expected = ceil(Fraction(data["durationS"][i][j]) * Fraction("1.08") / 60)
            assert matrix.duration_min[i][j] == expected, f"duration {i}->{j}"
    assert matrix.distance_km[0][1] == Decimal("187.45")
    assert matrix.duration_min[1][2] == 147, "8123 s x 1.08 / 60 = 146.2 is ceiled to 147"
    assert matrix.provider_id == "matrix_repo_v1"
    assert matrix.fallback is False


@pytest.mark.ac("AC-FEAT-004-07")
def test_ors_duration_of_6000_s_is_108_min_with_1_08_and_100_min_with_1_0() -> None:
    with_factor = MatrixFileRoutingProvider(FIXTURE, cities=SMALL).matrix(POINTS)
    without = MatrixFileRoutingProvider(
        FIXTURE, cities=SMALL, van_speed_factor=Decimal("1.0")
    ).matrix(POINTS)
    assert with_factor.duration_min[0][1] == 108
    assert without.duration_min[0][1] == 100


@pytest.mark.ac("AC-FEAT-004-01", "AC-FEAT-004-07")
def test_haversine_sourced_file_is_used_as_stored_without_a_second_factor(tmp_path: Path) -> None:
    data = json.loads(FIXTURE.read_text())
    data["source"] = "haversine_v1"
    data["durationS"] = [[0, 6480, 12000], [6480, 0, 8123], [12000, 8123, 0]]
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(data))
    matrix = MatrixFileRoutingProvider(path, cities=SMALL).matrix(POINTS)
    assert matrix.duration_min[0][1] == 108, "6480 s is 108 min as stored"
    assert matrix.duration_min[1][2] == 136, "8123 s is ceil(8123 / 60) with no factor applied"


@pytest.mark.ac("AC-FEAT-004-01")
def test_a_point_matches_a_city_within_one_km_and_the_answer_is_all_or_nothing() -> None:
    provider = MatrixFileRoutingProvider(FIXTURE, cities=SMALL)
    near = GeoPoint(lat=POINTS[0].lat + 0.004, lon=POINTS[0].lon)  # about 440 m north
    assert provider.matrix([near, POINTS[1]]).distance_km[0][1] == Decimal("187.45")
    far = GeoPoint(lat=POINTS[0].lat + 0.03, lon=POINTS[0].lon)  # about 3.3 km north
    with pytest.raises(RoutingFailure, match="outside"):
        provider.matrix([POINTS[1], far])


@pytest.mark.ac("AC-FEAT-004-08")
@pytest.mark.parametrize(
    "corruption", ["source", "cities", "dimensions", "negative", "bool", "diagonal", "missing"]
)
def test_malformed_matrix_is_explicitly_unavailable(tmp_path: Path, corruption: str) -> None:
    cities = [{"name": str(i), "lat": p.lat, "lon": p.lon} for i, p in enumerate(POINTS)]
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
