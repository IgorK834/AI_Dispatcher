"""Strict model-facing reports and application wire contracts."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from routepilot.agents.models import Role

Objective = Literal["profit", "fastest", "fuel"]
StepKind = Literal["llm", "tool", "guard", "interrupt"]
TraceStatus = Literal["ok", "error", "rejected"]


def all_objectives() -> list[Objective]:
    return ["profit", "fastest", "fuel"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DispatcherDecision(StrictModel):
    next: Literal["freight_scout", "fleet_compliance", "route_planner", "approve", "finish"]
    task: str
    rationale: str
    assumptions: list[str]


class ExcludedOffer(StrictModel):
    id: str
    reason: str


class ScoutReport(StrictModel):
    candidate_offer_ids: list[str]
    excluded: list[ExcludedOffer]
    data_issues: list[str]
    notes: str


class DriverAvailability(StrictModel):
    id: str
    available_from: str
    remaining_work_min: int | None
    remaining_drive_min: int | None
    home_by: str | None
    profile: str


class FleetReport(StrictModel):
    drivers: list[DriverAvailability]
    warnings: list[str]


class Recommendation(StrictModel):
    variant: str
    fleet_solution_id: str | None


class PlannerReport(StrictModel):
    recommended: Recommendation | None
    alternatives: list[Recommendation]
    tradeoffs: list[str]
    baseline_uplift: str | None


class AnswerText(StrictModel):
    summary: str
    citedFacts: list[str]


class ExplanationOutput(StrictModel):
    headline: str
    reasons: list[str] = Field(max_length=5)
    tradeoffs: list[str] = Field(max_length=3)
    warnings: list[str]


class SearchOffersInput(StrictModel):
    origin_city: str | None = None
    origin_country: str | None = None
    destination_city: str | None = None
    destination_country: str | None = None
    near_driver_ref: str | None = None
    radius_km: int | None = Field(default=None, ge=0, le=500)
    pickup_from: str | None = None
    pickup_to: str | None = None
    max_weight_kg: int | None = Field(default=None, ge=0)
    max_pallet_eq: str | None = None
    only_complete: bool = False
    limit: int = Field(default=20, ge=1, le=20)


class GetOfferInput(StrictModel):
    offer_id: str


class OfferQualityInput(StrictModel):
    offer_ids: list[str] = Field(max_length=20)


class ListDriversInput(StrictModel):
    pass


class DriverStateInput(StrictModel):
    driver_ref: str


class DriverAvailabilityInput(DriverStateInput):
    horizon_days: int = Field(default=5, ge=1, le=7)


class GetPlanInput(StrictModel):
    plan_ref: str


class OptimizeDriverInput(DriverStateInput):
    offer_ids: list[str] | None = Field(default=None, max_length=60)
    objectives: list[Objective] = Field(default_factory=all_objectives, min_length=1, max_length=3)


class OptimizeFleetInput(StrictModel):
    driver_refs: list[str] | None = Field(default=None, max_length=20)
    offer_ids: list[str] | None = Field(default=None, max_length=60)
    objectives: list[Objective] = Field(default_factory=all_objectives, min_length=1, max_length=3)


class ComparePlansInput(StrictModel):
    plan_refs: list[str] = Field(min_length=2, max_length=6)


class RequestApprovalInput(StrictModel):
    action: Literal["assign_plan"]
    plan_refs: list[str] = Field(min_length=1, max_length=10)
    summary: str = Field(max_length=300)


class ApprovalProblem(StrictModel):
    plan_ref: str
    code: str


class RequestApprovalOutput(StrictModel):
    accepted: bool
    problems: list[ApprovalProblem]


class AssignPlanInput(StrictModel):
    plan_id: UUID
    approval_id: UUID


class ExplanationInput(StrictModel):
    locale: Literal["en", "pl"] | None = None


class ThreadCreate(StrictModel):
    title: str | None = Field(default=None, max_length=200)


class MessageCreate(ExplanationInput):
    content: str = Field(min_length=1, max_length=2000)


class ResumeInput(StrictModel):
    approvalId: UUID
    decision: Literal["approve", "reject", "edit"]
    comment: str | None = Field(default=None, max_length=500)


class TraceStep(StrictModel):
    seq: int
    agent: str
    type: Literal["llm", "tool", "guard", "interrupt"]
    toolName: str | None = None
    inputSummary: str = Field(max_length=500)
    outputSummary: str = Field(default="", max_length=500)
    tokens: dict[str, int] = Field(default_factory=dict)
    durationMs: int = 0
    status: Literal["ok", "error", "rejected"] = "ok"


class ToolResult(StrictModel):
    tool: str
    call_id: str
    facts: dict[str, Any]


REPORT_SCHEMAS: dict[Role, type[BaseModel]] = {
    "dispatcher": DispatcherDecision,
    "freight_scout": ScoutReport,
    "fleet_compliance": FleetReport,
    "route_planner": PlannerReport,
    "explainer": ExplanationOutput,
}
