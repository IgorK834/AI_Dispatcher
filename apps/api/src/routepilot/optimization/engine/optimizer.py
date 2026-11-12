"""Pure public optimization entry point (FEAT-003)."""

from collections.abc import Callable
from typing import Literal

from routepilot.optimization.engine.fleet import assign_fleet, build_baselines
from routepilot.optimization.engine.models import (
    Action,
    EngineInvariantError,
    EngineResult,
    EngineSnapshot,
    EngineStats,
    FleetSolution,
    Objective,
    Rejection,
)
from routepilot.optimization.engine.prefilter import offer_pool
from routepilot.optimization.engine.schedule import build_plan
from routepilot.optimization.engine.search import search_driver
from routepilot.optimization.engine.validators import FleetValidator, RouteValidator


def optimize(
    snapshot: EngineSnapshot, *, elapsed_ms: Callable[[], int] | None = None
) -> EngineResult:
    per_driver = {}
    pools = {}
    rejections = []
    nodes, truncated, pool_truncated = 0, False, False
    for driver in sorted(snapshot.drivers, key=lambda d: d.id):
        pool, rejected, cut = offer_pool(snapshot, driver)
        pools[driver.id] = pool
        top, expanded, stopped = search_driver(snapshot, driver, pool, elapsed_ms=elapsed_ms)
        per_driver[driver.id] = top
        nodes += expanded
        truncated |= stopped
        pool_truncated |= cut
        returned = {oid for plans in top.values() for plan in plans for oid in plan.offer_ids}
        for offer in sorted(snapshot.offers, key=lambda o: o.id):
            if offer.id in returned:
                continue
            stage: Literal["prefilter", "search"]
            if offer.id in rejected:
                stage, code = "prefilter", rejected[offer.id]
            else:
                _, failure = build_plan(
                    snapshot,
                    driver,
                    [
                        Action(kind="PICKUP", offer_id=offer.id),
                        Action(kind="DELIVERY", offer_id=offer.id),
                    ],
                )
                stage, code = "search", failure or "NOT_IN_TOP_K"
            rejections.append(
                Rejection(driver_id=driver.id, offer_id=offer.id, stage=stage, code=code)
            )
    baselines, baseline_plans = build_baselines(snapshot, pools)
    listed = {
        p.plan_ref: p for groups in per_driver.values() for plans in groups.values() for p in plans
    }
    extra_candidates = {}
    drivers = {driver.id: driver for driver in snapshot.drivers}
    for baseline in baseline_plans:
        candidate, _ = build_plan(snapshot, drivers[baseline.driver_id], baseline.actions)
        if candidate is None:
            raise EngineInvariantError("validated baseline could not be copied as optimized")
        if candidate.plan_ref not in listed:
            extra_candidates[candidate.plan_ref] = candidate
    profit_candidates = {
        d: [*groups["profit"], *[p for p in extra_candidates.values() if p.driver_id == d]]
        for d, groups in per_driver.items()
    }
    fleet: dict[Objective, FleetSolution] = {
        "profit": assign_fleet(profit_candidates, "profit", snapshot.reference_time)
    }
    required = frozenset(a.driver_id for a in fleet["profit"].assignments)
    for objective in ("fastest", "fuel"):
        candidates = {
            d: [*groups[objective], *profit_candidates[d]] for d, groups in per_driver.items()
        }
        fleet[objective] = assign_fleet(candidates, objective, snapshot.reference_time, required)
    plans = [*listed.values(), *extra_candidates.values(), *baseline_plans]
    unique = {p.plan_ref: p for p in plans}
    for plan in unique.values():
        validation = RouteValidator().validate(snapshot, plan)
        if not validation.valid:
            raise EngineInvariantError(f"route {plan.plan_ref}: {validation.errors}")
    for solution in [*fleet.values(), *baselines.values()]:
        validation = FleetValidator().validate(snapshot, solution, list(unique.values()))
        if not validation.valid:
            raise EngineInvariantError(f"fleet {solution.objective}: {validation.errors}")
    if not truncated and any(
        fleet["profit"].totals.net_profit_minor < baseline.totals.net_profit_minor
        for baseline in baselines.values()
    ):
        raise EngineInvariantError("profit fleet is worse than a baseline")
    return EngineResult(
        per_driver=per_driver,
        fleet=fleet,
        baselines=baselines,
        baseline_plans=baseline_plans,
        fleet_candidates=sorted(extra_candidates.values(), key=lambda p: (p.driver_id, p.plan_ref)),
        rejections=rejections,
        warnings=["POOL_TRUNCATED"] if pool_truncated else [],
        stats=EngineStats(
            nodes=nodes,
            truncated=truncated,
            pool_truncated=pool_truncated,
            runtime_ms=elapsed_ms() if elapsed_ms else 0,
        ),
    )
