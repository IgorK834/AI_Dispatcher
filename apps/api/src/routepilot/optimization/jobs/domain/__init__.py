"""Optimization job API contracts and fixed planning notice."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from routepilot.optimization.engine.models import Objective

DISCLAIMER = (
    "The work/driving/rest schedule is a planning estimate based on a simplified model of selected "
    "rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). "
    "It does not certify legal compliance."
)


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, alias_generator=to_camel)


class JobParams(Schema):
    horizon_days: int = Field(default=5, ge=1, le=7)
    max_offers_per_plan: int = Field(default=6, ge=1, le=6)
    top_k_per_driver: int = Field(default=10, ge=1, le=10)


def all_objectives() -> list[Objective]:
    return ["profit", "fastest", "fuel"]


class JobCreate(Schema):
    scope: Literal["driver", "fleet"]
    driver_ids: list[UUID] = Field(default_factory=list)
    offer_ids: list[UUID] | None = None
    objectives: list[Objective] = Field(default_factory=all_objectives, min_length=1)
    params: JobParams = Field(default_factory=JobParams)

    @model_validator(mode="after")
    def valid_ids(self) -> Self:
        if self.scope == "driver" and len(self.driver_ids) != 1:
            raise ValueError("driver scope requires exactly one driver")
        if len(set(self.driver_ids)) != len(self.driver_ids) or len(set(self.objectives)) != len(
            self.objectives
        ):
            raise ValueError("duplicate drivers or objectives")
        if self.offer_ids is not None and len(set(self.offer_ids)) != len(self.offer_ids):
            raise ValueError("duplicate offers")
        return self


class Progress(Schema):
    phase: Literal["queued", "routing", "search", "assignment", "saving"] = "queued"
    drivers_done: int = 0
    drivers_total: int = 0


class Stats(Schema):
    nodes: int = 0
    truncated: bool = False
    pool_truncated: bool = False
    runtime_ms: int = 0


class JobError(Schema):
    code: str
    message: str


class Job(Schema):
    id: UUID
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    scope: Literal["driver", "fleet"]
    objectives: list[Objective]
    progress: Progress
    stats: Stats | None = None
    error: JobError | None = None
    requested_by: UUID
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class Money(Schema):
    amount_minor: int
    currency: str = "EUR"


class PlanSummary(Schema):
    id: UUID
    driver_id: UUID
    kind: Literal["optimized", "baseline_single", "baseline_greedy"]
    variant: Objective
    rank: int
    offer_ids: list[UUID]
    rules_profile: str
    net_profit: Money
    margin_pct: Decimal
    distance_km: Decimal
    empty_km: Decimal
    fuel_l: Decimal
    co2_kg: Decimal
    duration_min: int
    finish_at: datetime
    home_reached: bool
    warnings: list[str]


class Calculation(Schema):
    fuel: Money
    toll: Money
    driver: Money
    per_diem: Money
    accommodation: Money
    vehicle: Money
    parameters: dict[str, dict[str, str]]


class Counters(Schema):
    work_today: int
    drive_today: int
    work_since_break: int
    drive_since_break: int


class PlanStop(Schema):
    sequence: int
    kind: str
    offer_id: UUID | None
    label: str
    lat: float
    lon: float
    arrival_at: datetime
    wait_min: int
    service_start_at: datetime
    departure_at: datetime
    leg_km: Decimal
    leg_drive_min: int
    load_pallet_eq_after: Decimal
    load_kg_after: int
    counters: Counters


class RoutePlan(PlanSummary):
    revenue: Money
    cost_total: Money
    calculation: Calculation
    work_min: int
    drive_min: int
    wait_min: int
    stops: list[PlanStop]
    geometry: dict[str, Any] | None = None
    disclaimer: str = DISCLAIMER


class FleetAssignment(Schema):
    driver_id: UUID
    route_plan_id: UUID


class Totals(Schema):
    net_profit: Money
    fuel_l: Decimal
    co2_kg: Decimal
    distance_km: Decimal
    drivers_with_plan: int


class FleetSolution(Schema):
    objective: Objective
    assignments: list[FleetAssignment]
    totals: Totals


class DriverPlans(Schema):
    driver_id: UUID
    plans: dict[Objective, list[PlanSummary]]


class Baselines(Schema):
    baseline_single: FleetSolution
    baseline_greedy: FleetSolution


class Rejection(Schema):
    driver_id: UUID
    offer_id: UUID
    stage: str
    code: str
    detail: str


class JobResult(Schema):
    job_id: UUID
    fleet: dict[Objective, FleetSolution]
    per_driver: list[DriverPlans]
    baselines: Baselines
    rejections: list[Rejection]
    warnings: list[str]
    stats: Stats
    disclaimer: str = DISCLAIMER


class AssignmentCreate(Schema):
    route_plan_id: UUID


class Assignment(Schema):
    id: UUID
    route_plan_id: UUID
    driver_id: UUID
    status: Literal["active", "cancelled"]
    approved_by: UUID
    approved_at: datetime
    agent_run_id: UUID | None
    created_at: datetime


class RemainingWork(Schema):
    work_today_min: int | None
    work_week_min: int


class Remaining561(Schema):
    drive_before_break_min: int | None
    drive_today_min: int | None
    drive_week_min: int | None
    drive_two_weeks_min: int | None


class DriverAvailability(Schema):
    driver_id: UUID
    profile_domestic: str
    remaining: RemainingWork
    remaining_561: Remaining561
    must_be_home_by: datetime | None
    has_active_assignment: bool


class PlanRules(Schema):
    plan_id: UUID
    rules_profile: str
    valid: bool
    violations: list[dict[str, str]]
    inserted_breaks: int
    inserted_daily_rests: int
    max_work_day_min: int
    max_drive_day_min: int
    finish_at: datetime
    home_reached: bool
