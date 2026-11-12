"""Bounded model-facing tool results. Internal identifiers never occur here."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Place(Output):
    city: str
    country: str


class Window(Output):
    start: str
    end: str


class OfferSummary(Output):
    offer_id: str
    origin: Place
    destination: Place
    pickup_window: Window
    delivery_window: Window
    weight_kg: int | None
    pallet_eq: str | None
    price_eur: str | None
    completeness: float
    flags: list[str]
    suspicious: bool


class SearchOffersOutput(Output):
    offers: list[OfferSummary] = Field(max_length=20)
    total_matching: int
    truncated: bool


class OfferStop(Output):
    type: str
    city: str
    country: str
    window_start: str
    window_end: str
    service_min: int


class OfferDetail(Output):
    offer_id: str
    source: str
    status: str
    stops: list[OfferStop] = Field(max_length=2)
    weight_kg: int | None
    pallet_count: int | None
    pallet_type: str
    pallet_eq: str | None
    loading_length_m: str | None
    price_eur: str | None
    required_body_types: list[str]
    missing_fields: list[str]
    flags: list[str]
    provenance: dict[str, str]
    suspicious: bool
    untrusted_text: str = Field(max_length=300)


class QualityItem(Output):
    offer_id: str
    completeness: float | None
    missing_fields: list[str]
    flags: list[str]
    usable_by_engine: bool
    reason_code: str | None


class OfferQualityOutput(Output):
    items: list[QualityItem] = Field(max_length=20)


class Driver(Output):
    driver_ref: str
    home_city: str
    current_city: str | None
    pallet_places: int | None
    payload_kg: int | None
    sleeper_cab: bool | None
    available_from: str | None
    home_by: str | None


class ListDriversOutput(Output):
    drivers: list[Driver] = Field(max_length=20)
    count: int


class DriverStateOutput(Output):
    driver_ref: str
    current_city: str | None
    available_from: str
    work_today_min: int
    drive_today_min: int
    work_since_break_min: int
    drive_since_break_min: int
    work_week_min: int
    drive_week_min: int
    drive_prev_week_min: int
    last_daily_rest_end: str | None
    home_by: str | None
    state_source: str


class RemainingWork(Output):
    work_today_min: int | None
    work_week_min: int


class Remaining561(Output):
    drive_before_break_min: int | None
    drive_today_min: int | None
    drive_week_min: int | None
    drive_two_weeks_min: int | None


class DriverAvailabilityOutput(Output):
    driver_ref: str
    profile_domestic: str
    remaining: RemainingWork
    remaining_561: Remaining561
    must_be_home_by: str | None
    has_active_assignment: bool


class Violation(Output):
    invariant: str
    message: str


class CheckPlanRulesOutput(Output):
    plan_ref: str
    rules_profile: str
    valid: bool
    violations: list[Violation]
    inserted_breaks: int
    inserted_daily_rests: int
    max_work_day_min: int
    max_drive_day_min: int
    finish_at: str
    home_reached: bool


class PlanFacts(Output):
    plan_ref: str
    driver_ref: str
    variant: Literal["profit", "fastest", "fuel"]
    rank: int
    offer_ids: list[str]
    rules_profile: str
    net_profit_eur: str
    revenue_eur: str
    cost_eur: str
    distance_km: str
    empty_km: str
    fuel_l: str
    co2_kg: str
    duration_min: int
    finish_at: str
    home_reached: bool
    warnings: list[str]


class Baselines(Output):
    single_profit_eur: str
    greedy_profit_eur: str


class OptimizeOutput(Output):
    job_id: str
    plans: dict[str, list[PlanFacts]]
    baselines: Baselines
    rejections_summary: dict[str, int]
    truncated: bool


class FleetTotals(Output):
    net_profit_eur: str
    fuel_l: str
    co2_kg: str
    distance_km: str
    drivers_with_plan: int


class FleetVariant(Output):
    plans: list[PlanFacts] = Field(max_length=20)
    totals: FleetTotals


class OptimizeFleetOutput(Output):
    job_id: str
    fleet: dict[str, FleetVariant]
    baselines: Baselines
    uplift_vs_best_baseline_eur: str | None
    rejections_summary: dict[str, int]
    truncated: bool


class Costs(Output):
    fuel: str
    toll: str
    driver: str
    per_diem: str
    accommodation: str
    vehicle: str


class PlanStop(Output):
    seq: int
    kind: str
    city: str
    offer_id: str | None
    arrival_at: str
    service_start_at: str
    departure_at: str
    load_pallet_eq_after: str
    load_kg_after: int


class PlanDetail(PlanFacts):
    cost_breakdown: Costs
    stops: list[PlanStop] = Field(max_length=30)


class ComparisonRow(Output):
    plan_ref: str
    variant: str
    net_profit_eur: str
    finish_at: str
    fuel_l: str
    co2_kg: str
    distance_km: str


class ComparisonDelta(Output):
    plan_ref: str
    d_profit_eur: str
    d_finish_min: int
    d_fuel_l: str
    d_co2_kg: str


class ComparePlansOutput(Output):
    rows: list[ComparisonRow] = Field(max_length=6)
    deltas_vs_first: list[ComparisonDelta] = Field(max_length=5)


class ExplainPlanOutput(Output):
    plan_ref: str
    source: Literal["llm", "template"]
    headline: str
    reasons: list[str] = Field(max_length=5)
    tradeoffs: list[str] = Field(max_length=3)
    warnings: list[str]


class AssignPlanOutput(Output):
    assignment_id: str
    plan_ref: str
    driver_ref: str
    status: Literal["active"]
