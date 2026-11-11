"""Persistence for immutable snapshots, plans and transactional assignments."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, REAL, Boolean, Integer, MetaData, Table, Text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from routepilot.shared.db.base import Base, EditableMixin, IdMixin
from routepilot.shared.db.types import UtcDateTime, UuidText


# Foreign keys are owned by the approved initial migration; these mappings do not
# couple jobs metadata to identity/agent domain modules.
class JobRow(IdMixin, Base):
    __tablename__ = "optimization_jobs"
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())
    status: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text)
    objectives: Mapped[list[str]] = mapped_column(JSON)
    idempotency_key: Mapped[str | None] = mapped_column(Text, unique=True)
    input_sha256: Mapped[str] = mapped_column(Text)
    request: Mapped[dict[str, Any]] = mapped_column(JSON)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    solver_version: Mapped[str] = mapped_column(Text)
    progress: Mapped[dict[str, Any]] = mapped_column(JSON)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON)
    error: Mapped[dict[str, str] | None] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(Integer)
    heartbeat_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    requested_by: Mapped[UUID] = mapped_column(UuidText())
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime())


class PlanRow(IdMixin, Base):
    __tablename__ = "route_plans"
    job_id: Mapped[UUID] = mapped_column(UuidText())
    driver_id: Mapped[UUID] = mapped_column(UuidText())
    kind: Mapped[str] = mapped_column(Text)
    variant: Mapped[str] = mapped_column(Text)
    rank: Mapped[int] = mapped_column(Integer)
    offer_ids: Mapped[list[str]] = mapped_column(JSON)
    rules_profile: Mapped[str] = mapped_column(Text)
    revenue_minor: Mapped[int] = mapped_column(Integer)
    cost_total_minor: Mapped[int] = mapped_column(Integer)
    net_profit_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(Text(3))
    margin_pct: Mapped[str] = mapped_column(Text)
    distance_m: Mapped[int] = mapped_column(Integer)
    empty_m: Mapped[int] = mapped_column(Integer)
    fuel_ml: Mapped[int] = mapped_column(Integer)
    co2_g: Mapped[int] = mapped_column(Integer)
    duration_min: Mapped[int] = mapped_column(Integer)
    work_min: Mapped[int] = mapped_column(Integer)
    drive_min: Mapped[int] = mapped_column(Integer)
    wait_min: Mapped[int] = mapped_column(Integer)
    finish_at: Mapped[datetime] = mapped_column(UtcDateTime())
    home_reached: Mapped[bool] = mapped_column(Boolean)
    risk_level: Mapped[str] = mapped_column(Text)
    calculation: Mapped[dict[str, Any]] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON)
    fleet_role: Mapped[list[str]] = mapped_column(JSON)
    geometry: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class StopRow(IdMixin, Base):
    __tablename__ = "route_stops"
    route_plan_id: Mapped[UUID] = mapped_column(UuidText())
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(Text)
    offer_id: Mapped[UUID | None] = mapped_column(UuidText())
    lat: Mapped[float] = mapped_column(REAL)
    lon: Mapped[float] = mapped_column(REAL)
    label: Mapped[str] = mapped_column(Text)
    arrival_at: Mapped[datetime] = mapped_column(UtcDateTime())
    wait_min: Mapped[int] = mapped_column(Integer)
    service_start_at: Mapped[datetime] = mapped_column(UtcDateTime())
    departure_at: Mapped[datetime] = mapped_column(UtcDateTime())
    leg_m: Mapped[int] = mapped_column(Integer)
    leg_drive_min: Mapped[int] = mapped_column(Integer)
    load_pallet_eq_after: Mapped[str] = mapped_column(Text)
    load_kg_after: Mapped[int] = mapped_column(Integer)
    work_today_min: Mapped[int] = mapped_column(Integer)
    drive_today_min: Mapped[int] = mapped_column(Integer)
    work_since_break_min: Mapped[int] = mapped_column(Integer)
    drive_since_break_min: Mapped[int] = mapped_column(Integer)


class AssignmentRow(EditableMixin, Base):
    __tablename__ = "assignments"
    route_plan_id: Mapped[UUID] = mapped_column(UuidText())
    driver_id: Mapped[UUID] = mapped_column(UuidText())
    approved_by: Mapped[UUID] = mapped_column(UuidText())
    approved_at: Mapped[datetime] = mapped_column(UtcDateTime())
    agent_run_id: Mapped[UUID | None] = mapped_column(UuidText())
    status: Mapped[str] = mapped_column(Text)


class JobsRepository:
    Job = JobRow

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        # Reflection stays at the repository edge and supports the reviewed schema
        # without importing identity, agents, or other domains' ORM registries.
        self.metadata = MetaData()
        self.metadata.reflect(
            engine,
            only=[
                "users",
                "drivers",
                "driver_states",
                "vehicles",
                "cost_profiles",
                "freight_offers",
                "freight_stops",
                "raw_freight_records",
            ],
        )

    def table(self, name: str) -> Table:
        return self.metadata.tables[name]

    @contextmanager
    def session(self) -> Iterator[Session]:
        with Session(self.engine) as session, session.begin():
            yield session
