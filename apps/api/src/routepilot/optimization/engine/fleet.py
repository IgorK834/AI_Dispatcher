"""Exact conflict-pruned fleet assignment and deterministic baseline construction."""

from datetime import datetime
from decimal import Decimal

from routepilot.optimization.engine.models import (
    Action,
    EngineSnapshot,
    FleetAssignment,
    FleetSolution,
    FleetTotals,
    Objective,
    OfferSnapshot,
    RoutePlan,
)
from routepilot.optimization.engine.schedule import build_plan
from routepilot.optimization.engine.search import plan_key


def fleet_solution(objective: Objective, plans: list[RoutePlan]) -> FleetSolution:
    ordered = sorted(plans, key=lambda p: (p.driver_id, p.plan_ref))
    return FleetSolution(
        objective=objective,
        assignments=[FleetAssignment(driver_id=p.driver_id, plan_ref=p.plan_ref) for p in ordered],
        totals=FleetTotals(
            net_profit_minor=sum(p.net_profit_minor for p in plans),
            fuel_l=sum((p.fuel_l for p in plans), Decimal("0")),
            co2_kg=sum((p.co2_kg for p in plans), Decimal("0")),
            distance_km=sum((p.distance_km for p in plans), Decimal("0")),
            drivers_with_plan=len(plans),
        ),
    )


def fleet_key(
    plans: list[RoutePlan], objective: Objective, reference: datetime
) -> tuple[object, ...]:
    profit = sum(p.net_profit_minor for p in plans)
    finish = sum(int((p.finish_at - reference).total_seconds() // 60) for p in plans)
    fuel = sum((p.fuel_l for p in plans), Decimal("0"))
    ids = tuple(sorted((p.driver_id, p.plan_ref) for p in plans))
    if objective == "profit":
        return -profit, finish, fuel, ids
    return (finish if objective == "fastest" else fuel), -profit, ids


def assign_fleet(
    candidates: dict[str, list[RoutePlan]],
    objective: Objective,
    reference: datetime,
    required_drivers: frozenset[str] = frozenset(),
    *,
    bounded: bool = True,
) -> FleetSolution:
    driver_ids = sorted(candidates, key=lambda d: (len(candidates[d]), d))
    ordered = {
        d: sorted(
            {p.plan_ref: p for p in candidates[d]}.values(), key=lambda p: plan_key(p, objective)
        )
        for d in driver_ids
    }
    best: list[RoutePlan] | None = None
    best_key: tuple[object, ...] | None = None

    def visit(index: int, chosen: list[RoutePlan], used: frozenset[str], profit: int) -> None:
        nonlocal best, best_key
        if bounded and objective == "profit" and best is not None:
            upper = profit + sum(
                max([0, *[p.net_profit_minor for p in ordered[d]]]) for d in driver_ids[index:]
            )
            if upper < sum(p.net_profit_minor for p in best):
                return
        if index == len(driver_ids):
            key = fleet_key(chosen, objective, reference)
            if best_key is None or key < best_key:
                best, best_key = list(chosen), key
            return
        driver = driver_ids[index]
        if driver not in required_drivers:
            visit(index + 1, chosen, used, profit)
        for plan in ordered[driver]:
            if not used.intersection(plan.offer_ids):
                visit(
                    index + 1,
                    [*chosen, plan],
                    used | frozenset(plan.offer_ids),
                    profit + plan.net_profit_minor,
                )

    visit(0, [], frozenset(), 0)
    return fleet_solution(objective, best or [])


def build_baselines(
    snapshot: EngineSnapshot, pools: dict[str, list[OfferSnapshot]]
) -> tuple[dict[str, FleetSolution], list[RoutePlan]]:
    single: list[RoutePlan] = []
    taken: set[str] = set()
    drivers = sorted(snapshot.drivers, key=lambda d: d.id)
    for driver in drivers:
        feasible = []
        for offer in pools[driver.id]:
            if offer.id in taken:
                continue
            plan, _ = build_plan(
                snapshot,
                driver,
                [
                    Action(kind="PICKUP", offer_id=offer.id),
                    Action(kind="DELIVERY", offer_id=offer.id),
                ],
                "baseline_single",
            )
            if plan is not None:
                feasible.append(plan)
        if feasible:
            best = min(feasible, key=lambda p: plan_key(p, "profit"))
            single.append(best)
            taken.update(best.offer_ids)
    greedy: dict[str, RoutePlan] = {}
    taken = set()
    while True:
        winner: tuple[tuple[object, ...], RoutePlan] | None = None
        for driver in drivers:
            current = greedy.get(driver.id)
            actions = current.actions if current else []
            if current and len(current.offer_ids) >= snapshot.params.max_offers_per_plan:
                continue
            for offer in pools[driver.id]:
                if offer.id in taken:
                    continue
                for pickup in range(len(actions) + 1):
                    for delivery in range(pickup + 1, len(actions) + 2):
                        proposed = list(actions)
                        proposed.insert(pickup, Action(kind="PICKUP", offer_id=offer.id))
                        proposed.insert(delivery, Action(kind="DELIVERY", offer_id=offer.id))
                        plan, _ = build_plan(
                            snapshot, driver, proposed, "baseline_greedy", thresholds=False
                        )
                        if plan is None:
                            continue
                        increase = plan.net_profit_minor - (
                            current.net_profit_minor if current else 0
                        )
                        if increase <= 0:
                            continue
                        key = (-increase, driver.id, offer.id, pickup, delivery)
                        if winner is None or key < winner[0]:
                            winner = key, plan
        if winner is None:
            break
        plan = winner[1]
        greedy[plan.driver_id] = plan
        taken.update(plan.offer_ids)
    kept = [
        plan
        for driver in drivers
        if (plan := greedy.get(driver.id)) is not None
        and plan.net_profit_minor >= driver.cost_profile.min_profit_minor
        and plan.margin_pct >= driver.cost_profile.min_margin_pct
    ]
    return {
        "baseline_single": fleet_solution("profit", single),
        "baseline_greedy": fleet_solution("profit", kept),
    }, [*single, *kept]
