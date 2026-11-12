"""Routing values; all distances are km and durations whole minutes."""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RouteVariant = Literal["FASTEST"]


class GeoPoint(BaseModel):
    model_config = ConfigDict(frozen=True)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class TravelMatrix(BaseModel):
    distance_km: list[list[Decimal]]
    duration_min: list[list[int]]
    provider_id: str
    fallback: bool = False


class RouteResult(BaseModel):
    distance_km: Decimal
    duration_min: int
    geometry: dict[str, Any]
    approximate: bool


class RoutingFailure(Exception):
    """A provider cannot supply a complete result; the chain may fall back."""
