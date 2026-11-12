"""Validated fleet API contracts, stored units converted at the service boundary."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, model_validator
from pydantic.alias_generators import to_camel

PositiveMoney = Annotated[StrictInt, Field(ge=0)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
RulesProfile = Literal["pl_domestic_employee_v1", "eu561_van_international_v1"]


class Schema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
        from_attributes=True,
        allow_inf_nan=False,
    )


class Fuel(Schema):
    # Stored as tenths of a litre: finer input would be silently truncated, so it is rejected.
    l_per_100km_empty_at90: Decimal = Field(alias="lPer100kmEmptyAt90", gt=0, decimal_places=1)
    l_per_100km_full_at90: Decimal = Field(alias="lPer100kmFullAt90", gt=0, decimal_places=1)
    speed_curve: Literal["VAN_DEFAULT_V1"] = "VAN_DEFAULT_V1"


class FuelView(Fuel):
    provenance: str


class Tolls(Schema):
    per_km: dict[str, PositiveMoney]
    annual_vignettes: list[str]


class CostProfileCreate(Schema):
    name: str = Field(min_length=1, max_length=120)
    currency: Literal["EUR"] = "EUR"
    fuel_price_minor_per_l: PositiveMoney
    driver_cost_minor_per_hour: PositiveMoney
    vehicle_cost_minor_per_km: PositiveMoney
    accommodation_minor: PositiveMoney
    per_diem: dict[str, PositiveMoney]
    tolls: Tolls
    fx_rates: dict[str, str]
    min_profit_minor: StrictInt
    min_margin_pct: str

    @model_validator(mode="after")
    def decimal_parameters(self) -> Self:
        try:
            values = [Decimal(self.min_margin_pct), *(Decimal(v) for v in self.fx_rates.values())]
        except InvalidOperation:
            raise ValueError("invalid cost-profile decimal parameter") from None
        if not all(v.is_finite() and v >= 0 for v in values) or any(
            Decimal(v) == 0 for v in self.fx_rates.values()
        ):
            raise ValueError("invalid cost-profile decimal parameter")
        return self


class CostProfileUpdate(Schema):
    version: int = Field(ge=1)
    name: str | None = None
    currency: Literal["EUR"] | None = None
    fuel_price_minor_per_l: PositiveMoney | None = None
    driver_cost_minor_per_hour: PositiveMoney | None = None
    vehicle_cost_minor_per_km: PositiveMoney | None = None
    accommodation_minor: PositiveMoney | None = None
    per_diem: dict[str, PositiveMoney] | None = None
    tolls: Tolls | None = None
    fx_rates: dict[str, str] | None = None
    min_profit_minor: StrictInt | None = None
    min_margin_pct: str | None = None


class CostProfileView(CostProfileCreate):
    id: UUID
    provenance: dict[str, str]
    is_synthetic: bool
    version: int
    created_at: datetime
    updated_at: datetime


class VehicleCreate(Schema):
    label: str = Field(min_length=1, max_length=120)
    vehicle_type: Literal["VEHICLE_UP_TO_3_5_T"]
    body_type: Literal["CURTAIN_SIDER", "TAUTLINER", "BOX"]
    inner_length_m: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    inner_width_m: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    inner_height_m: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    pallet_places: int = Field(ge=1, le=12)
    layout_template: Literal["EUR_MIXED_5X3", "EUR_MIXED_6X4", "DECLARED_ONLY"]
    side_access: Literal["LEFT", "RIGHT", "BOTH", "NONE"]
    payload_kg: int = Field(ge=100, le=2000)
    gvw_kg: int = Field(gt=0, le=3500)
    sleeper_cab: bool
    fuel: Fuel
    cost_profile_id: UUID


class VehicleUpdate(Schema):
    version: int = Field(ge=1)
    label: str | None = None
    vehicle_type: Literal["VEHICLE_UP_TO_3_5_T"] | None = None
    body_type: Literal["CURTAIN_SIDER", "TAUTLINER", "BOX"] | None = None
    inner_length_m: Decimal | None = None
    inner_width_m: Decimal | None = None
    inner_height_m: Decimal | None = None
    pallet_places: int | None = None
    layout_template: str | None = None
    side_access: str | None = None
    payload_kg: int | None = None
    gvw_kg: int | None = None
    sleeper_cab: bool | None = None
    fuel: Fuel | None = None
    cost_profile_id: UUID | None = None


class VehicleView(VehicleCreate):
    id: UUID
    fuel: FuelView
    is_synthetic: bool
    version: int
    created_at: datetime
    updated_at: datetime


class DriverCreate(Schema):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=80)
    home_city: str = Field(min_length=1)
    home_country: str = Field(pattern="^[A-Z]{2}$")
    home_lat: Latitude
    home_lon: Longitude
    default_rules_profile: RulesProfile = "pl_domestic_employee_v1"
    vehicle_id: UUID | None = None


class DriverUpdate(Schema):
    version: int = Field(ge=1)
    name: str | None = None
    phone: str | None = None
    home_city: str | None = None
    home_country: str | None = None
    home_lat: Latitude | None = None
    home_lon: Longitude | None = None
    default_rules_profile: RulesProfile | None = None
    vehicle_id: UUID | None = None


class DriverStateCreate(Schema):
    current_city: str | None = None
    current_lat: Latitude
    current_lon: Longitude
    available_from: AwareDatetime
    work_today_min: int = Field(ge=0)
    drive_today_min: int = Field(ge=0)
    work_since_break_min: int = Field(ge=0)
    drive_since_break_min: int = Field(ge=0)
    work_week_min: int = Field(ge=0)
    drive_week_min: int = Field(ge=0)
    drive_prev_week_min: int = Field(ge=0)
    last_daily_rest_end: AwareDatetime | None = None
    last_weekly_rest_end: AwareDatetime | None = None
    home_by: AwareDatetime | None = None


class DriverStateView(DriverStateCreate):
    id: UUID
    driver_id: UUID
    valid_from: datetime
    source: str


class DriverView(DriverCreate):
    id: UUID
    is_synthetic: bool
    version: int
    created_at: datetime
    updated_at: datetime
    vehicle: VehicleView | None = None
    state: DriverStateView | None = None
