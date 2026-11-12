"""Persist engine results atomically and convert them to public API documents."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from routepilot.optimization.engine.models import EngineResult
from routepilot.optimization.engine.models import RoutePlan as EnginePlan
from routepilot.optimization.jobs.domain import (
    Baselines,
    DriverPlans,
    FleetAssignment,
    FleetSolution,
    JobResult,
    Money,
    PlanSummary,
    Rejection,
    Stats,
    Totals,
)
from routepilot.optimization.jobs.repository import JobRow, PlanRow, StopRow


def scaled(value: Decimal, factor: int = 1000) -> int:
    return int((value * factor).to_integral_value(rounding=ROUND_HALF_UP))


def plan_summary(row: PlanRow) -> PlanSummary:
    return PlanSummary.model_validate(
        dict(
            id=row.id,
            driver_id=row.driver_id,
            kind=row.kind,
            variant=row.variant,
            rank=row.rank,
            offer_ids=row.offer_ids,
            rules_profile=row.rules_profile,
            net_profit=Money(amount_minor=row.net_profit_minor, currency=row.currency),
            margin_pct=row.margin_pct,
            distance_km=Decimal(row.distance_m) / 1000,
            empty_km=Decimal(row.empty_m) / 1000,
            fuel_l=Decimal(row.fuel_ml) / 1000,
            co2_kg=Decimal(row.co2_g) / 1000,
            duration_min=row.duration_min,
            finish_at=row.finish_at,
            home_reached=row.home_reached,
            warnings=row.warnings,
        )
    )


def store_result(session: Session, job: JobRow, result: EngineResult) -> None:
    plans: dict[str, EnginePlan] = {}
    for variants in result.per_driver.values():
        for variants_plans in variants.values():
            for plan in variants_plans:
                plans[plan.plan_ref] = plan
    for plan in [*result.fleet_candidates, *result.baseline_plans]:
        plans[plan.plan_ref] = plan
    ids = {ref: uuid4() for ref in sorted(plans)}
    rows = {}
    for ref, plan in plans.items():
        fleet_role = [
            objective
            for objective, solution in result.fleet.items()
            if any(assignment.plan_ref == ref for assignment in solution.assignments)
        ]
        row = PlanRow(
            id=ids[ref],
            job_id=job.id,
            driver_id=UUID(plan.driver_id),
            kind=plan.kind,
            variant=plan.variant,
            rank=plan.rank,
            offer_ids=plan.offer_ids,
            rules_profile=plan.rules_profile,
            revenue_minor=plan.revenue_minor,
            cost_total_minor=plan.cost_total_minor,
            net_profit_minor=plan.net_profit_minor,
            currency="EUR",
            margin_pct=str(plan.margin_pct),
            distance_m=scaled(plan.distance_km),
            empty_m=scaled(plan.empty_km),
            fuel_ml=scaled(plan.fuel_l),
            co2_g=scaled(plan.co2_kg),
            duration_min=plan.duration_min,
            work_min=plan.work_min,
            drive_min=plan.drive_min,
            wait_min=plan.wait_min,
            finish_at=plan.finish_at,
            home_reached=plan.home_reached,
            risk_level="unknown",
            calculation=plan.calculation.model_dump(mode="json"),
            warnings=plan.warnings,
            fleet_role=fleet_role,
            geometry=None,
        )
        session.add(row)
        rows[ref] = row
        for stop in plan.stops:
            # A rest may not carry a new Point. It remains at the preceding stop.
            point = stop.point
            if point is None:
                prior = [
                    s.point
                    for s in plan.stops
                    if s.sequence < stop.sequence and s.point is not None
                ]
                point = prior[-1] if prior else plan.legs[0].start if plan.legs else None
            if point is None or point.lat is None or point.lon is None:
                raise ValueError("A validated route stop must have coordinates")
            session.add(
                StopRow(
                    id=uuid4(),
                    route_plan_id=row.id,
                    sequence=stop.sequence,
                    kind=stop.kind,
                    offer_id=UUID(stop.offer_id) if stop.offer_id else None,
                    lat=point.lat,
                    lon=point.lon,
                    label=stop.label or point.city,
                    arrival_at=stop.arrival_at,
                    wait_min=stop.wait_min,
                    service_start_at=stop.service_start_at,
                    departure_at=stop.departure_at,
                    leg_m=scaled(stop.leg_km),
                    leg_drive_min=stop.leg_drive_min,
                    load_pallet_eq_after=str(stop.load_pallet_eq_after),
                    load_kg_after=stop.load_kg_after,
                    work_today_min=stop.counters.work_today,
                    drive_today_min=stop.counters.drive_today,
                    work_since_break_min=stop.counters.work_since_break,
                    drive_since_break_min=stop.counters.drive_since_break,
                )
            )
    session.flush()

    def fleet(solution: Any) -> FleetSolution:
        return FleetSolution(
            objective=solution.objective,
            assignments=[
                FleetAssignment(driver_id=UUID(item.driver_id), route_plan_id=ids[item.plan_ref])
                for item in solution.assignments
            ],
            totals=Totals(
                net_profit=Money(amount_minor=solution.totals.net_profit_minor),
                fuel_l=solution.totals.fuel_l,
                co2_kg=solution.totals.co2_kg,
                distance_km=solution.totals.distance_km,
                drivers_with_plan=solution.totals.drivers_with_plan,
            ),
        )

    public = JobResult(
        job_id=job.id,
        fleet={key: fleet(value) for key, value in result.fleet.items()},
        per_driver=[
            DriverPlans(
                driver_id=UUID(driver_id),
                plans={
                    key: [plan_summary(rows[plan.plan_ref]) for plan in value]
                    for key, value in variants.items()
                },
            )
            for driver_id, variants in sorted(result.per_driver.items())
        ],
        baselines=Baselines(
            baseline_single=fleet(result.baselines["baseline_single"]),
            baseline_greedy=fleet(result.baselines["baseline_greedy"]),
        ),
        rejections=[Rejection(**item.model_dump()) for item in result.rejections],
        warnings=result.warnings,
        stats=Stats(**result.stats.model_dump()),
    )
    job.result = {
        "public": public.model_dump(mode="json", by_alias=True),
        "engine": result.model_dump(mode="json"),
        "plan_ids": {ref: str(value) for ref, value in ids.items()},
    }
    job.stats = result.stats.model_dump(mode="json", by_alias=True)
