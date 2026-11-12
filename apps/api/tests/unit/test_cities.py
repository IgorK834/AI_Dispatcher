"""The committed city table: schema, the 39 cities of FEAT-002 §6.1 and lookup rules."""

import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import jsonschema_rs
import pytest

from routepilot.freight.geocoding import CityTable, geocode, timezone_for_country

ROOT = Path(__file__).resolve().parents[4]
CITIES = ROOT / "data/mock/cities.json"
SCHEMA = ROOT / "data/mock/cities.schema.json"
SPEC = ROOT / "specs/FEAT-002-demo-data-generators.md"


def spec_rows() -> dict[tuple[str, str], tuple[float, float, str]]:
    """The binding table of §6.1, read from the specification itself."""
    text = SPEC.read_text()
    section = text[text.index("### 6.1") : text.index("### 6.2")]
    rows = re.findall(
        r"^\| ([A-Z]{2}) \| (.+?) \| ([\d.]+) \| ([\d.]+) \| (\S+) \|$", section, re.M
    )
    return {(name, code): (float(lat), float(lon), zone) for code, name, lat, lon, zone in rows}


def document() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(CITIES.read_text())
    return loaded


@pytest.mark.ac("AC-FEAT-002-08")
def test_file_validates_against_its_schema_and_rejects_broken_documents() -> None:
    validator = jsonschema_rs.validator_for(json.loads(SCHEMA.read_text()))
    assert validator.is_valid(document())
    good = document()
    broken = [
        {**good, "version": 2},
        {**good, "extra": 1},
        {key: value for key, value in good.items() if key != "countryTimezones"},
        {**good, "cities": [{**good["cities"][0], "countryCode": "pl"}]},
        {**good, "cities": [{**good["cities"][0], "lat": 91}]},
        {**good, "cities": [{k: v for k, v in good["cities"][0].items() if k != "timezone"}]},
        {**good, "cities": [{**good["cities"][0], "population": 1}]},
        {**good, "cities": [good["cities"][0], good["cities"][0]]},
    ]
    for candidate in broken:
        assert not validator.is_valid(candidate), candidate


@pytest.mark.ac("AC-FEAT-002-08")
def test_the_39_cities_of_section_6_1_with_their_coordinates_and_zones() -> None:
    expected = spec_rows()
    assert len(expected) == 39
    cities = document()["cities"]
    found = {(c["name"], c["countryCode"]): (c["lat"], c["lon"], c["timezone"]) for c in cities}
    assert len(cities) == len(found) == 39, "no duplicate (name, countryCode)"
    assert found == expected
    for city in cities:
        assert round(city["lat"], 4) == city["lat"] and round(city["lon"], 4) == city["lon"]
        assert unicodedata.is_normalized("NFC", city["name"])
        ZoneInfo(city["timezone"])
    CityTable.model_validate(document())  # the loader accepts exactly this file


@pytest.mark.ac("AC-FEAT-002-08")
def test_country_timezone_map_covers_the_demo_countries_and_agrees_with_the_cities() -> None:
    zones = document()["countryTimezones"]
    assert set(zones) == {"PL", "DE", "CZ", "SK", "AT", "HU", "NL", "BE", "FR", "IT", "DK"}
    for city in document()["cities"]:
        assert zones[city["countryCode"]] == city["timezone"], city["name"]
    assert timezone_for_country("pl") == "Europe/Warsaw"
    assert timezone_for_country("XX") == "UTC"  # unknown countries are not guessed


@pytest.mark.ac("AC-FEAT-002-08")
def test_lookup_is_exact_on_name_and_country_but_ignores_case() -> None:
    assert geocode("Wrocław", "PL") == (51.1079, 17.0385)
    assert geocode("wROCŁAW", "pl") == (51.1079, 17.0385)
    assert geocode("Katowice", "DE") is None  # right name, wrong country
    assert geocode("Breslau", "PL") is None  # an exonym is not matched
    assert geocode("Wroclaw", "PL") is None  # no diacritics folding


@pytest.mark.ac("AC-FEAT-002-08")
@pytest.mark.parametrize("name", [" Katowice", "Katowice ", "  kAtOwIcE\t", "\nKatowice\n"])
def test_surrounding_spaces_are_ignored_by_the_lookup(name: str) -> None:
    # FEAT-002 §8: a different letter case or surrounding spaces still match.
    assert geocode(name, "PL") == (50.2649, 19.0238)
    assert geocode(name, " pl ") == (50.2649, 19.0238)
    assert geocode("Kat owice", "PL") is None  # inner spaces are part of the name
