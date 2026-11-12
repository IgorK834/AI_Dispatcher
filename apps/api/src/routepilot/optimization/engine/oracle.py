"""TEST ONLY: exhaustive offer subsets and pickup/delivery orders for at most five offers."""

from datetime import timedelta
from itertools import combinations

from routepilot.compliance.rules import choose_profile
from routepilot.optimization.engine.models import (
    Action,
    DriverSnapshot,
    EngineSnapshot,
    Objective,
    RoutePlan,
)
from routepilot.optimization.engine.prefilter import offer_pool
from routepilot.optimization.engine.schedule import Label, ScheduleBuilder
from routepilot.optimization.engine.search import OBJECTIVES, rank_plans


def brute_force(
    snapshot: EngineSnapshot, driver: DriverSnapshot
) -> dict[Objective, list[RoutePlan]]:
    pool, _, _ = offer_pool(snapshot, driver)
    if len(pool) > 5 or snapshot.params.top_k_per_driver > 3:
        raise ValueError("oracle supports at most five offers and top K of three")
    plans = []

    def enumerate_orders(builder: ScheduleBuilder, ids: frozenset[str], label: Label) -> None:
        if label.done == ids:
            plan, _ = builder.finish(label)
            if plan is not None:
                plans.append(plan)
            return
        for oid in sorted(ids):
            if oid not in label.picked:
                action = Action(kind="PICKUP", offer_id=oid)
            elif oid not in label.done:
                action = Action(kind="DELIVERY", offer_id=oid)
            else:
                continue
            extended, _ = builder.extend(label, action)
            if extended is not None:
                enumerate_orders(builder, ids, extended)

    for count in range(1, min(len(pool), snapshot.params.max_offers_per_plan) + 1):
        for subset in combinations(sorted(o.id for o in pool), count):
            countries = [
                driver.position.country,
                *[s.point.country for o in pool if o.id in subset for s in o.stops],
            ]
            if driver.home_by is not None and driver.home_by <= snapshot.reference_time + timedelta(
                days=snapshot.params.horizon_days
            ):
                countries.append(driver.home.country)
            profile = choose_profile(driver.home.country or "", countries)
            builder = ScheduleBuilder(snapshot, driver, profile)
            enumerate_orders(builder, frozenset(subset), builder.initial())
    return {
        objective: rank_plans(plans, objective, snapshot.params.top_k_per_driver)
        for objective in OBJECTIVES
    }
