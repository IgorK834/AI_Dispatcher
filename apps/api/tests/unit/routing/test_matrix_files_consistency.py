"""routing-matrix.json and cities.json agree, and the generator reproduces the committed file."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from routepilot.routing.matrix_file import MatrixFileRoutingProvider

ROOT = Path(__file__).resolve().parents[5]
CITIES_FILE = ROOT / "data/mock/cities.json"
MATRIX_FILE = ROOT / "data/mock/routing-matrix.json"
SCRIPT = ROOT / "scripts/generate_routing_matrix.py"


@pytest.fixture
def generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_routing_matrix", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.ac("AC-FEAT-004-08")
def test_matrix_lists_the_same_39_cities_in_the_same_order() -> None:
    cities = json.loads(CITIES_FILE.read_text())["cities"]
    matrix = json.loads(MATRIX_FILE.read_text())
    assert len(cities) == 39
    assert matrix["cities"] == [city["name"] for city in cities]


@pytest.mark.ac("AC-FEAT-004-08")
@pytest.mark.parametrize("table", ["distanceM", "durationS"])
def test_both_tables_are_39_by_39_with_a_zero_diagonal_and_non_negative_integers(
    table: str,
) -> None:
    rows = json.loads(MATRIX_FILE.read_text())[table]
    assert len(rows) == 39
    for index, row in enumerate(rows):
        assert len(row) == 39, f"{table} row {index} has {len(row)} columns"
        assert row[index] == 0, f"{table} diagonal at {index}"
        assert all(type(value) is int and value >= 0 for value in row), f"{table} row {index}"


@pytest.mark.ac("AC-FEAT-004-08")
def test_source_is_one_of_the_two_allowed_values() -> None:
    assert json.loads(MATRIX_FILE.read_text())["source"] in {"ors_driving_car_v1", "haversine_v1"}


@pytest.mark.ac("AC-FEAT-004-08")
def test_the_provider_accepts_the_committed_file_for_the_committed_cities() -> None:
    cities = json.loads(CITIES_FILE.read_text())["cities"]
    provider = MatrixFileRoutingProvider(MATRIX_FILE, cities=cities)
    assert len(provider.points) == 39


@pytest.mark.ac("AC-FEAT-004-08")
def test_the_generator_reproduces_the_committed_haversine_file_byte_for_byte(
    generator: ModuleType, tmp_path: Path
) -> None:
    out = tmp_path / "routing-matrix.json"
    assert generator.main(["--source", "haversine", "--out", str(out)]) == 0
    assert out.read_bytes() == MATRIX_FILE.read_bytes()


@pytest.mark.ac("AC-FEAT-004-08")
def test_the_generator_refuses_an_unreadable_city_table(
    generator: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out.json"
    code = generator.main(
        ["--source", "haversine", "--cities", str(tmp_path / "missing.json"), "--out", str(out)]
    )
    assert code == 1
    assert "city table" in capsys.readouterr().err
    assert not out.exists()
