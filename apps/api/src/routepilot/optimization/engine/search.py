"""Deterministic two-profile Branch-and-Bound with distinct offer-set top K."""

from collections.abc import Callable

from routepilot.optimization.engine.costs import CostModel, revenue_in_profile_currency
from routepilot.optimization.engine.models import (
    Action,
    DriverSnapshot,
    EngineSnapshot,
    Objective,
    OfferSnapshot,
    RoutePlan,
)
from routepilot.optimization.engine.schedule import Label, ScheduleBuilder

OBJECTIVES: tuple[Objective, ...] = ("profit", "fastest", "fuel")


def action_key(plan: RoutePlan) -> tuple[tuple[int, str], ...]:
    return tuple((0 if a.kind == "DELIVERY" else 1, a.offer_id) for a in plan.actions)


def plan_key(plan: RoutePlan, objective: Objective) -> tuple[object, ...]:
    primary: tuple[object, ...]
    if objective == "profit":
        primary = (-plan.net_profit_minor, plan.finish_at, plan.fuel_l)
    elif objective == "fastest":
        primary = (plan.finish_at, -plan.net_profit_minor)
    else:
        primary = (plan.fuel_l, -plan.net_profit_minor)
    return (*primary, tuple(sorted(plan.offer_ids)), action_key(plan))


def rank_plans(plans: list[RoutePlan], objective: Objective, top_k: int) -> list[RoutePlan]:
    best: dict[tuple[str, ...], RoutePlan] = {}
    for plan in plans:
        key = tuple(sorted(plan.offer_ids))
        if key not in best or plan_key(plan, objective) < plan_key(best[key], objective):
            best[key] = plan
    ordered = sorted(best.values(), key=lambda p: plan_key(p, objective))[:top_k]
    return [
        p.model_copy(update={"variant": objective, "rank": i + 1}) for i, p in enumerate(ordered)
    ]


def search_driver(
    snapshot: EngineSnapshot,
    driver: DriverSnapshot,
    pool: list[OfferSnapshot],
    *,
    bounded: bool = True,
    elapsed_ms: Callable[[], int] | None = None,
) -> tuple[dict[Objective, list[RoutePlan]], int, bool]:
    top: dict[Objective, list[RoutePlan]] = {objective: [] for objective in OBJECTIVES}
    nodes, truncated = 0, False
    started_ms = elapsed_ms() if elapsed_ms else 0
    time_limit_ms = int(snapshot.params.wall_clock_safety_s * 1000)
    k = snapshot.params.top_k_per_driver
    revenues = {
        o.id: revenue_in_profile_currency(
            o.revenue_minor or 0, o.revenue_currency, driver.cost_profile
        )
        or 0
        for o in pool
    }
    cost_model = CostModel(snapshot.co2_factor_kg_per_l)
    by_id = {o.id: o for o in pool}

    def cannot_enter(label: Label) -> bool:
        if not bounded or not all(len(top[o]) >= k for o in OBJECTIVES):
            return False
        # Paid and prospective revenue overestimate the achievable profit; all remaining costs
        # are non-negative. Clock and consumed fuel only increase along any extension.
        remaining = sorted((revenues[o.id] for o in pool if o.id not in label.picked), reverse=True)
        prospective = sum(revenues[oid] for oid in label.picked) + sum(
            remaining[: snapshot.params.max_offers_per_plan - len(label.picked)]
        )
        partial = cost_model.calculate(
            driver,
            [by_id[oid] for oid in sorted(label.picked)],
            list(label.legs),
            list(label.activities),
            label.departure,
            label.state.t,
        )
        return (
            prospective - (partial.calculation.total - partial.calculation.per_diem)
            < top["profit"][-1].net_profit_minor
            and label.state.t > top["fastest"][-1].finish_at
            and partial.fuel_l > top["fuel"][-1].fuel_l
        )

    def visit(builder: ScheduleBuilder, label: Label, eligible: list[OfferSnapshot]) -> None:
        nonlocal nodes, truncated
        if nodes >= snapshot.params.node_budget_per_driver or (
            elapsed_ms is not None and elapsed_ms() - started_ms >= time_limit_ms
        ):
            truncated = True
            return
        nodes += 1
        if label.done and not label.onboard:
            plan, _ = builder.finish(label)
            if plan is not None:
                for objective in OBJECTIVES:
                    top[objective] = rank_plans([*top[objective], plan], objective, k)
        if cannot_enter(label):
            return
        moves = [Action(kind="DELIVERY", offer_id=oid) for oid in sorted(label.onboard)]
        if len(label.picked) < snapshot.params.max_offers_per_plan:
            moves.extend(
                Action(kind="PICKUP", offer_id=o.id) for o in eligible if o.id not in label.picked
            )
        for action in moves:
            if truncated:
                return
            extended, _ = builder.extend(label, action)
            if extended is not None:
                visit(builder, extended, eligible)

    domestic = [o for o in pool if all(s.point.country == driver.home.country for s in o.stops)]
    if driver.position.country is not None and driver.position.country == driver.home.country:
        visit(
            ScheduleBuilder(snapshot, driver, "pl_domestic_employee_v1"),
            ScheduleBuilder(snapshot, driver, "pl_domestic_employee_v1").initial(),
            domestic,
        )
    if not truncated and (
        driver.position.country != driver.home.country
        or driver.position.country is None
        or any(o not in domestic for o in pool)
    ):
        builder = ScheduleBuilder(snapshot, driver, "eu561_van_international_v1")
        visit(builder, builder.initial(), pool)
    return top, nodes, truncated
