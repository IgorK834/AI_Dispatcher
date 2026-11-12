"""Readers for the plan fields the golden assertions of section 4 compare."""

from datetime import datetime

from routepilot.optimization.engine.models import EngineResult, EngineSnapshot, PlanStop, RoutePlan


def action_stops(plan: RoutePlan) -> list[PlanStop]:
    return [s for s in plan.stops if s.kind in ("PICKUP", "DELIVERY")]


def sequence(plan: RoutePlan) -> list[str]:
    """``PICKUP A`` / ``DELIVERY A`` labels in plan order."""
    return [f"{s.kind} {s.offer_id}" for s in action_stops(plan)]


def inside_windows(source: EngineSnapshot, plan: RoutePlan) -> bool:
    """Invariant 4: every service start lies inside the window of its pickup or delivery."""
    offers = {o.id: o for o in source.offers}
    for stop in action_stops(plan):
        window = offers[stop.offer_id].stops[0 if stop.kind == "PICKUP" else 1]
        if not window.window_start <= stop.service_start_at <= window.window_end:
            return False
    return True


def inserted_events(plan: RoutePlan) -> list[tuple[str, datetime, int]]:
    """``(kind, start, minutes)`` of every inserted BREAK and DAILY_REST."""
    return [
        (a.activity.kind, a.activity.start_at, a.activity.minutes)
        for a in plan.activities
        if a.activity.kind in ("BREAK", "DAILY_REST")
    ]


def minutes_of(plan: RoutePlan, kind: str) -> int:
    return sum(a.activity.minutes for a in plan.activities if a.activity.kind == kind)


def plans(result: EngineResult, driver_id: str, objective: str = "profit") -> list[RoutePlan]:
    return result.per_driver[driver_id][objective]
