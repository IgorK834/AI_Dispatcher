"""Fleet records matching the reviewed initial migration."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, REAL, Text
from sqlalchemy.orm import Mapped, mapped_column

from routepilot.shared.db.base import Base, EditableMixin, IdMixin
from routepilot.shared.db.types import UtcDateTime, UuidText


class CostProfile(EditableMixin, Base):
    __tablename__ = "cost_profiles"
    name: Mapped[str] = mapped_column(Text, unique=True)
    currency: Mapped[str] = mapped_column(Text(3))
    fuel_price_minor_per_l: Mapped[int] = mapped_column(Integer)
    driver_cost_minor_per_hour: Mapped[int] = mapped_column(Integer)
    vehicle_cost_minor_per_km: Mapped[int] = mapped_column(Integer)
    accommodation_minor: Mapped[int] = mapped_column(Integer)
    per_diem: Mapped[dict[str, int]] = mapped_column(JSON)
    tolls: Mapped[dict[str, Any]] = mapped_column(JSON)
    fx_rates: Mapped[dict[str, str]] = mapped_column(JSON)
    min_profit_minor: Mapped[int] = mapped_column(Integer)
    min_margin_pct: Mapped[str] = mapped_column(Text)
    provenance: Mapped[dict[str, str]] = mapped_column(JSON)
    is_synthetic: Mapped[bool] = mapped_column(Boolean)


class Vehicle(EditableMixin, Base):
    __tablename__ = "vehicles"
    label: Mapped[str] = mapped_column(Text, unique=True)
    vehicle_type: Mapped[str] = mapped_column(Text)
    body_type: Mapped[str] = mapped_column(Text)
    inner_length_mm: Mapped[int | None] = mapped_column(Integer)
    inner_width_mm: Mapped[int | None] = mapped_column(Integer)
    inner_height_mm: Mapped[int | None] = mapped_column(Integer)
    pallet_places: Mapped[int] = mapped_column(Integer)
    layout_template: Mapped[str] = mapped_column(Text)
    side_access: Mapped[str] = mapped_column(Text)
    payload_kg: Mapped[int] = mapped_column(Integer)
    gvw_kg: Mapped[int] = mapped_column(Integer)
    sleeper_cab: Mapped[bool] = mapped_column(Boolean)
    fuel_l_per_100km_empty_x10: Mapped[int] = mapped_column(Integer)
    fuel_l_per_100km_full_x10: Mapped[int] = mapped_column(Integer)
    fuel_speed_curve: Mapped[str] = mapped_column(Text)
    fuel_provenance: Mapped[str] = mapped_column(Text)
    cost_profile_id: Mapped[UUID] = mapped_column(
        UuidText(), ForeignKey("cost_profiles.id", ondelete="RESTRICT")
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean)


class Driver(EditableMixin, Base):
    __tablename__ = "drivers"
    name: Mapped[str] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    home_city: Mapped[str] = mapped_column(Text)
    home_country: Mapped[str] = mapped_column(Text(2))
    home_lat: Mapped[float] = mapped_column(REAL)
    home_lon: Mapped[float] = mapped_column(REAL)
    default_rules_profile: Mapped[str] = mapped_column(Text)
    vehicle_id: Mapped[UUID | None] = mapped_column(
        UuidText(), ForeignKey("vehicles.id", ondelete="RESTRICT"), unique=True
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    deleted_at: Mapped[datetime | None] = mapped_column(UtcDateTime())


class DriverState(IdMixin, Base):
    __tablename__ = "driver_states"
    driver_id: Mapped[UUID] = mapped_column(
        UuidText(), ForeignKey("drivers.id", ondelete="CASCADE")
    )
    valid_from: Mapped[datetime] = mapped_column(UtcDateTime())
    current_city: Mapped[str | None] = mapped_column(Text)
    current_lat: Mapped[float] = mapped_column(REAL)
    current_lon: Mapped[float] = mapped_column(REAL)
    available_from: Mapped[datetime] = mapped_column(UtcDateTime())
    work_today_min: Mapped[int] = mapped_column(Integer)
    drive_today_min: Mapped[int] = mapped_column(Integer)
    work_since_break_min: Mapped[int] = mapped_column(Integer)
    drive_since_break_min: Mapped[int] = mapped_column(Integer)
    work_week_min: Mapped[int] = mapped_column(Integer)
    drive_week_min: Mapped[int] = mapped_column(Integer)
    drive_prev_week_min: Mapped[int] = mapped_column(Integer)
    last_daily_rest_end: Mapped[datetime | None] = mapped_column(UtcDateTime())
    last_weekly_rest_end: Mapped[datetime | None] = mapped_column(UtcDateTime())
    home_by: Mapped[datetime | None] = mapped_column(UtcDateTime())
    source: Mapped[str] = mapped_column(Text)
