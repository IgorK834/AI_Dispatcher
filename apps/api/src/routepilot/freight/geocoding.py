"""Offline city lookup; no geocoding service is called."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Self
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class City(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    name: str = Field(min_length=1)
    country_code: str = Field(alias="countryCode", pattern=r"^[A-Z]{2}$")
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    timezone: str

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value


class CityTable(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    version: int
    cities: list[City]
    country_timezones: dict[str, str] = Field(alias="countryTimezones")

    @model_validator(mode="after")
    def unique_cities(self) -> Self:
        keys = [(city.name.casefold(), city.country_code) for city in self.cities]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate city/country")
        for zone in self.country_timezones.values():
            ZoneInfo(zone)
        return self


@lru_cache(maxsize=1)
def city_table() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[5] / "data/mock/cities.json"
    return CityTable.model_validate(json.loads(path.read_text())).model_dump(by_alias=True)


def timezone_for_country(country: str) -> str:
    return str(city_table()["countryTimezones"].get(country.upper(), "UTC"))


def geocode(city: str, country: str) -> tuple[float, float] | None:
    for item in city_table()["cities"]:
        if item["name"].casefold() == city.casefold() and item["countryCode"] == country.upper():
            return float(item["lat"]), float(item["lon"])
    return None
