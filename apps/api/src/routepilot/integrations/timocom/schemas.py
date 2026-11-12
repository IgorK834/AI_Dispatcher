"""TIMOCOM Freight Exchange API 3.0.6 subset. Unknown provider fields are ignored.

Source: https://api.stoplight.io/projects/cHJqOjIwMTI4Nw/branches/v3/export/reference/openapi.yaml
Read once with owner approval, 2026-11-11; examples in tests/fixtures/timocom.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ProviderModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Coordinates(ProviderModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class Address(ProviderModel):
    city: str
    country: str
    postalCode: str | None = None
    geoCoordinate: Coordinates | None = None
    geocoded: bool | None = None


class LoadingPlace(ProviderModel):
    loadingType: str
    address: Address
    earliestLoadingDate: date
    latestLoadingDate: date
    startTime: str | None = None
    endTime: str | None = None


class VehicleProperties(ProviderModel):
    type: list[str] = Field(default_factory=list)
    body: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)


class Price(ProviderModel):
    amount: Decimal = Field(ge=0)
    currency: str


class FreightOffer(ProviderModel):
    id: str
    freightDescription: str | None = None
    publicRemark: str | None = None
    vehicleProperties: VehicleProperties = Field(default_factory=VehicleProperties)
    loadingPlaces: list[LoadingPlace]
    price: Price | None = None
    weight_t: Decimal | None = Field(default=None, ge=0)
    length_m: Decimal | None = Field(default=None, ge=0)
    distance_km: Decimal | None = Field(default=None, ge=0)
    creationDateTime: datetime | None = Field(
        default=None, validation_alias=AliasChoices("creationDateTime", "creationDateTime ")
    )
