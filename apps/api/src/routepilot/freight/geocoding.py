"""Offline city lookup; no geocoding service is called."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def city_table() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[5] / "data/mock/cities.json"
    result: dict[str, Any] = json.loads(path.read_text())
    return result


def timezone_for_country(country: str) -> str:
    return str(city_table()["countryTimezones"].get(country.upper(), "UTC"))


def geocode(city: str, country: str) -> tuple[float, float] | None:
    for item in city_table()["cities"]:
        if item["name"].casefold() == city.casefold() and item["countryCode"] == country.upper():
            return float(item["lat"]), float(item["lon"])
    return None
