"""Serializable, IO-free input and output contracts for FEAT-003."""

from decimal import Decimal
from functools import cached_property
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from routepilot.compliance.models import DriverState, ProfileId, RuleActivity

Objective = Literal["profit", "fastest", "fuel"]
PlanKind = Literal["optimized", "baseline_single", "baseline_greedy"]
ActionKind = Literal["PICKUP", "DELIVERY"]


class EngineModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Point(EngineModel):
    key: str
    city: str = ""
    country: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    timezone: str = "Europe/Warsaw"


class Stop(EngineModel):
    point: Point
    window_start: AwareDatetime
    window_end: AwareDatetime
    service_min: int | None = Field(default=None, ge=0)
    service_provenance: str = "default"


class VehicleSnapshot(EngineModel):
    id: str = ""
    vehicle_type: str = "VEHICLE_UP_TO_3_5_T"
    body_type: str = "CURTAIN_SIDER"
    equipment: list[str] = Field(default_factory=list)
    pallet_places: int = Field(default=10, gt=0)
    payload_kg: int = Field(default=1085, gt=0)
    inner_length_m: Decimal | None = None
    inner_height_m: Decimal | None = None
    sleeper_cab: bool = False
    fuel_l_per_100km_empty: Decimal = Decimal("11.0")
    fuel_l_per_100km_full: Decimal = Decimal("13.0")
    fuel_speed_curve: str = "VAN_DEFAULT_V1"
    fuel_provenance: str = "assumption"


class CostProfile(EngineModel):
    id: str = ""
    currency: str = "EUR"
    fuel_price_minor_per_l: int = 181
    driver_cost_minor_per_hour: int = 1400
    vehicle_cost_minor_per_km: int = 12
    accommodation_minor: int = 5500
    per_diem: dict[str, int] = Field(default_factory=lambda: {"PL": 1059})
    toll_per_km: dict[str, int] = Field(default_factory=dict)
    annual_vignettes: list[str] = Field(default_factory=list)
    fx_rates: dict[str, Decimal] = Field(default_factory=dict)
    min_profit_minor: int = 0
    min_margin_pct: Decimal = Decimal("0")
    provenance: dict[str, str] = Field(default_factory=dict)


class DriverSnapshot(EngineModel):
    id: str
    home: Point
    position: Point
    available_from: AwareDatetime
    home_by: AwareDatetime | None = None
    vehicle: VehicleSnapshot
    cost_profile: CostProfile
    rules_state: DriverState


class OfferSnapshot(EngineModel):
    id: str
    source_offer_id: str = ""
    version: int = 1
    status: str = "open"
    weight_kg: int | None
    pallet_count: int | None = None
    pallet_type: str = "EUR_1200x800"
    pallet_provenance: str = "generated_mock"
    loading_length_m: Decimal | None = None
    height_m: Decimal | None = None
    revenue_minor: int | None = None
    revenue_currency: str = "EUR"
    required_vehicle_types: list[str] = Field(default_factory=list)
    required_body_types: list[str] = Field(default_factory=list)
    required_equipment: list[str] = Field(default_factory=list)
    stops: tuple[Stop, Stop]
    warnings: list[str] = Field(default_factory=list)
    field_provenance: dict[str, str] = Field(default_factory=dict)


class TravelMatrix(EngineModel):
    points: list[Point]
    distance_km: list[list[Decimal]]
    duration_min: list[list[int]]
    provider_id: str = "matrix_repo_v1"
    fallback: bool = False

    @model_validator(mode="after")
    def square(self) -> "TravelMatrix":
        count = len(self.points)
        if len({p.key for p in self.points}) != count:
            raise ValueError("matrix point keys must be unique")
        for rows in (self.distance_km, self.duration_min):
            if len(rows) != count or any(len(row) != count for row in rows):
                raise ValueError("matrix must be square and match its point order")
            if any(value < 0 for row in rows for value in row):
                raise ValueError("matrix values must be non-negative")
        return self

    @cached_property
    def indices(self) -> dict[str, int]:
        return {point.key: index for index, point in enumerate(self.points)}

    def leg(self, start: Point, end: Point) -> tuple[Decimal, int]:
        i, j = self.indices[start.key], self.indices[end.key]
        return self.distance_km[i][j], self.duration_min[i][j]


class EngineParams(EngineModel):
    horizon_days: int = Field(default=5, gt=0)
    max_offers_per_plan: int = Field(default=6, gt=0)
    top_k_per_driver: int = Field(default=10, gt=0)
    max_pool_per_driver: int = Field(default=60, gt=0)
    node_budget_per_driver: int = Field(default=1_500_000, gt=0)
    max_first_deadhead_km: Decimal = Decimal("350")
    default_service_min: int = 30
    max_daily_work_min: int = 720
    van_speed_factor: Decimal = Decimal("1.08")
    wall_clock_safety_s: Decimal = Decimal("30")


class EngineSnapshot(EngineModel):
    reference_time: AwareDatetime
    drivers: list[DriverSnapshot]
    offers: list[OfferSnapshot]
    matrix: TravelMatrix
    params: EngineParams = Field(default_factory=EngineParams)
    objectives: list[Objective] = Field(
        default_factory=lambda: list[Objective](("profit", "fastest", "fuel"))
    )
    co2_factor_kg_per_l: Decimal = Decimal("2.6")
    solver_version: str = "branch_and_bound_v1"


class Action(EngineModel):
    kind: ActionKind
    offer_id: str


class PlanActivity(EngineModel):
    activity: RuleActivity
    point_key: str | None = None
    leg_index: int | None = None


class PlanStop(EngineModel):
    sequence: int
    kind: Literal["START", "PICKUP", "DELIVERY", "BREAK", "DAILY_REST", "WEEKLY_REST", "END"]
    offer_id: str | None = None
    point: Point | None = None
    label: str = ""
    arrival_at: AwareDatetime
    service_start_at: AwareDatetime
    departure_at: AwareDatetime
    wait_min: int = 0
    service_min: int = 0
    leg_km: Decimal = Decimal("0")
    leg_drive_min: int = 0
    load_pallet_eq_after: Decimal = Decimal("0")
    load_kg_after: int = 0
    counters: DriverState


class PlanLeg(EngineModel):
    start: Point
    end: Point
    distance_km: Decimal
    drive_min: int
    load_kg: int
    load_pallet_eq: Decimal
    departed_at: AwareDatetime
    arrived_at: AwareDatetime


class Calculation(EngineModel):
    fuel: int = 0
    toll: int = 0
    driver: int = 0
    per_diem: int = 0
    accommodation: int = 0
    vehicle: int = 0
    parameters: dict[str, dict[str, str]] = Field(default_factory=dict)

    @property
    def total(self) -> int:
        return (
            self.fuel + self.toll + self.driver + self.per_diem + self.accommodation + self.vehicle
        )


class RoutePlan(EngineModel):
    plan_ref: str
    driver_id: str
    kind: PlanKind = "optimized"
    variant: Objective = "profit"
    rank: int = 1
    offer_ids: list[str]
    actions: list[Action]
    rules_profile: ProfileId
    departure_at: AwareDatetime
    finish_at: AwareDatetime
    home_reached: bool
    revenue_minor: int
    cost_total_minor: int
    net_profit_minor: int
    margin_pct: Decimal
    calculation: Calculation
    distance_km: Decimal
    empty_km: Decimal
    fuel_l: Decimal
    co2_kg: Decimal
    duration_min: int
    work_min: int
    drive_min: int
    service_min: int
    wait_min: int
    warnings: list[str]
    stops: list[PlanStop]
    legs: list[PlanLeg]
    activities: list[PlanActivity]


class FleetAssignment(EngineModel):
    driver_id: str
    plan_ref: str


class FleetTotals(EngineModel):
    net_profit_minor: int = 0
    fuel_l: Decimal = Decimal("0")
    co2_kg: Decimal = Decimal("0")
    distance_km: Decimal = Decimal("0")
    drivers_with_plan: int = 0


class FleetSolution(EngineModel):
    objective: Objective
    assignments: list[FleetAssignment] = Field(default_factory=list)
    totals: FleetTotals = Field(default_factory=FleetTotals)


class Rejection(EngineModel):
    driver_id: str
    offer_id: str
    stage: Literal["prefilter", "search"]
    code: str
    detail: str = ""


class EngineStats(EngineModel):
    nodes: int = 0
    truncated: bool = False
    pool_truncated: bool = False
    runtime_ms: int = 0


class EngineResult(EngineModel):
    per_driver: dict[str, dict[Objective, list[RoutePlan]]]
    fleet: dict[Objective, FleetSolution]
    baselines: dict[str, FleetSolution]
    baseline_plans: list[RoutePlan]
    fleet_candidates: list[RoutePlan] = Field(default_factory=list)
    rejections: list[Rejection]
    warnings: list[str]
    stats: EngineStats


class ValidationResult(EngineModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class EngineInvariantError(RuntimeError):
    """A computed result failed an independent invariant check."""
