"""TEST ONLY: Cartesian-product fleet assignment without search or bounds."""

from datetime import datetime
from itertools import product

from routepilot.optimization.engine.fleet import fleet_key, fleet_solution
from routepilot.optimization.engine.models import FleetSolution, Objective, RoutePlan


def brute_force_fleet(
    candidates: dict[str, list[RoutePlan]],
    objective: Objective,
    reference: datetime,
    required_drivers: frozenset[str] = frozenset(),
) -> FleetSolution:
    if len(candidates) > 3 or any(len(plans) > 4 for plans in candidates.values()):
        raise ValueError("fleet oracle supports at most three drivers with four plans each")
    choices = [
        [*candidates[d], *([None] if d not in required_drivers else [])] for d in sorted(candidates)
    ]
    feasible: list[list[RoutePlan]] = []
    for combination in product(*choices):
        plans = [p for p in combination if p is not None]
        ids = [oid for p in plans for oid in p.offer_ids]
        if len(set(ids)) == len(ids):
            feasible.append(plans)
    best = (
        min(feasible, key=lambda plans: fleet_key(plans, objective, reference)) if feasible else []
    )
    return fleet_solution(objective, best)
