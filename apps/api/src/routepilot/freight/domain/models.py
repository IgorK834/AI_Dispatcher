"""Validated manual input and normalized freight DTOs."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, model_validator
from pydantic.alias_generators import to_camel


class Schema(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, alias_generator=to_camel, from_attributes=True
    )


class Revenue(Schema):
    amount_minor: Annotated[StrictInt, Field(ge=0)]
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class StopCreate(Schema):
    stop_type: Literal["LOADING", "UNLOADING"]
    city: str = Field(min_length=1, max_length=120)
    postal_code: str | None = None
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    window_start: AwareDatetime
    window_end: AwareDatetime
    service_minutes: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def ordered_window(self) -> Self:
        if self.window_start > self.window_end:
            raise ValueError("windowStart must be before windowEnd")
        if (self.lat is None) != (self.lon is None):
            raise ValueError("lat and lon must be provided together")
        return self


class StopView(StopCreate):
    sequence: int
    timezone: str
    service_minutes: int
    provenance: dict[str, str]


class FreightOfferCreate(Schema):
    description: str = Field(min_length=3, max_length=50)
    revenue: Revenue | None = None
    weight_kg: int = Field(ge=1, le=3500)
    pallet_count: int | None = Field(default=None, ge=1, le=33)
    pallet_type: Literal["EUR_1200x800", "IND_1200x1000", "HALF_800x600", "UNKNOWN"]
    loading_length_m: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    required_body_types: list[str]
    public_remark: str | None = Field(default=None, max_length=500)
    stops: list[StopCreate] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def stops_ordered(self) -> Self:
        if self.stops[0].stop_type != "LOADING" or self.stops[-1].stop_type != "UNLOADING":
            raise ValueError("stops must be LOADING then UNLOADING")
        return self


class FreightOfferUpdate(Schema):
    version: int = Field(ge=1)
    description: str | None = Field(default=None, min_length=3, max_length=50)
    revenue: Revenue | None = None
    weight_kg: int | None = Field(default=None, ge=1, le=3500)
    pallet_count: int | None = Field(default=None, ge=1, le=33)
    pallet_type: Literal["EUR_1200x800", "IND_1200x1000", "HALF_800x600", "UNKNOWN"] | None = None
    loading_length_m: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    required_body_types: list[str] | None = None
    public_remark: str | None = Field(default=None, max_length=500)
    stops: list[StopCreate] | None = Field(default=None, min_length=2, max_length=2)


class NormalizedOffer(Schema):
    source_offer_id: str
    description: str | None = None
    public_remark: str | None = None
    revenue: Revenue | None = None
    weight_kg: int | None = None
    pallet_count: int | None = None
    pallet_type: str = "UNKNOWN"
    loading_length_m: Decimal | None = None
    required_body_types: list[str] = Field(default_factory=list)
    required_vehicle_types: list[str] = Field(default_factory=list)
    required_equipment: list[str] = Field(default_factory=list, exclude=True)
    completeness_score: float = 0
    missing_fields: list[str] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)
    field_provenance: dict[str, str] = Field(default_factory=dict)
    stops: list[StopView]
    retention_until: AwareDatetime | None = None


class FreightOfferView(NormalizedOffer):
    id: UUID
    source: str
    status: Literal["open", "assigned", "expired", "withdrawn"]
    is_synthetic: bool
    version: int
    created_at: datetime
    updated_at: datetime


class RawOfferRecord(Schema):
    source: str
    source_offer_id: str
    payload: dict[str, Any]
    fetched_at: AwareDatetime
    enrichment: dict[str, Any] = Field(default_factory=dict)


class MappingFailure(Schema):
    code: str
    detail: str


class FreightSearchQuery(Schema):
    origin: str | None = None
    destination: str | None = None
    radius_km: Decimal | None = Field(default=None, ge=0)
    loading_from: AwareDatetime | None = None
    loading_to: AwareDatetime | None = None
    max_weight_kg: int | None = Field(default=None, ge=1)
    vehicle_type: str = "VEHICLE_UP_TO_3_5_T"


class ImportBatchView(Schema):
    id: UUID
    source: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    counts: dict[str, int]
