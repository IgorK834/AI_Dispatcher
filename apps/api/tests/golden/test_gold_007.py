"""GOLD-007 (Domestic: break after 6 h of work, 12-hour day).

Every assertion of section 4 of specs/golden/GOLD-007.md, one assert per item.
"""

from decimal import ROUND_HALF_UP, Decimal

import pytest

from routepilot.optimization.engine import RouteValidator
from routepilot.optimization.engine.models import Action
from routepilot.optimization.engine.schedule import build_plan

from .fixtures.common import at
from .fixtures.gold_007 import build
from .helpers import action_stops, inserted_events, inside_windows, minutes_of, plans, sequence


@pytest.mark.ac("AC-FEAT-003-36")
def test_gold_007(run) -> None:
    source = build()
    result, repeatable = run(source)
    vehicle = source.drivers[0].vehicle
    ranked = plans(result, "D1")
    plan = ranked[0]
    stops = action_stops(plan)

    # 1: rank 1 plan, offers and order
    assert sorted(plan.offer_ids) == ["J", "K"], "GOLD-007 §4.1: offers of the rank 1 plan"
    assert sequence(plan) == ["PICKUP J", "DELIVERY J", "PICKUP K", "DELIVERY K"], (
        "GOLD-007 §4.1: order of the stops"
    )

    # 2: load after every stop, within capacity (invariant 1)
    assert [s.load_pallet_eq_after for s in stops] == [
        Decimal("5.0"),
        Decimal("0.0"),
        Decimal("4.0"),
        Decimal("0.0"),
    ], "GOLD-007 §4.2: load_pallet_eq_after"
    assert [s.load_kg_after for s in stops] == [500, 0, 400, 0], "GOLD-007 §4.2: load_kg_after"
    assert all(0 <= s.load_kg_after <= vehicle.payload_kg for s in stops), (
        "GOLD-007 §4.2: payload respected"
    )
    assert all(0 <= s.load_pallet_eq_after <= vehicle.pallet_places for s in stops), (
        "GOLD-007 §4.2: pallet places respected"
    )

    # 3: profile
    assert plan.rules_profile == "pl_domestic_employee_v1", "GOLD-007 §4.3: rules_profile"

    # 4: service starts, inside the windows (invariant 4)
    assert [s.service_start_at for s in stops] == [
        at(0, 6, 0),
        at(0, 16, 43),
        at(0, 17, 13),
        at(1, 10, 41),
    ], "GOLD-007 §4.4: service start times"
    assert inside_windows(source, plan), "GOLD-007 §4.4: every service start inside its window"

    # 5: totals
    assert plan.distance_km == Decimal("927.98"), "GOLD-007 §4.5: distance_km"
    assert plan.drive_min == 926, "GOLD-007 §4.5: drive_min"
    assert plan.work_min == 1046, "GOLD-007 §4.5: work_min"
    assert plan.wait_min == 0, "GOLD-007 §4.5: wait_min"
    assert minutes_of(plan, "BREAK") == 45, "GOLD-007 §4.5: break minutes"
    assert minutes_of(plan, "DAILY_REST") == 660, "GOLD-007 §4.5: daily rest minutes"
    assert plan.finish_at == at(1, 11, 11), "GOLD-007 §4.5: finish_at"

    # 6: fuel and CO2 (invariant 17)
    assert plan.fuel_l == Decimal("112.612"), "GOLD-007 §4.6: fuel_l"
    assert plan.co2_kg == Decimal("292.79"), "GOLD-007 §4.6: co2_kg"
    assert plan.co2_kg == (plan.fuel_l * Decimal("2.6")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    ), "GOLD-007 §4.6: co2_kg = fuel_l x 2.6"

    # 7: cost breakdown in minor units (invariant 7)
    c = plan.calculation
    assert (c.fuel, c.toll, c.driver, c.per_diem, c.accommodation, c.vehicle) == (
        20383,
        0,
        24407,
        1589,
        5500,
        11136,
    ), "GOLD-007 §4.7: cost components"
    assert plan.cost_total_minor == 63015, "GOLD-007 §4.7: cost_total_minor"
    assert plan.revenue_minor == 85000, "GOLD-007 §4.7: revenue_minor"
    assert plan.net_profit_minor == 21985, "GOLD-007 §4.7: net_profit_minor"
    assert plan.net_profit_minor == plan.revenue_minor - plan.cost_total_minor, (
        "GOLD-007 §4.7: profit reconstructs"
    )

    # not a section 4 item: the warning flags every golden plan carries
    assert {"LOADING_ORDER_NOT_MODELLED", "SERVICE_TIME_DEFAULTED"} <= set(plan.warnings), (
        "GOLD-007: warning flags"
    )

    # 8: validator and determinism (invariant 8)
    assert RouteValidator().validate(source, plan).valid, (
        "GOLD-007 §4.8: RouteValidator accepts the plan"
    )
    assert repeatable, "GOLD-007 §4.8: a second run is identical"

    # 9: inserted events on day 1 (the 15-minute top-up is convention G4)
    assert inserted_events(plan) == [
        ("BREAK", at(0, 12, 0), 30),
        ("BREAK", at(0, 15, 30), 15),
        ("DAILY_REST", at(0, 18, 45), 660),
    ], "GOLD-007 §4.9: BREAK 30 at Mon 12:00, BREAK 15 at Mon 15:30, DAILY_REST 660 at Mon 18:45"

    # 10: daily work is 720 min on Monday and 326 min on Tuesday, no break on Tuesday
    rest_start = at(0, 18, 45)
    work_kinds = ("WORK", "WAIT", "DRIVE")
    monday = sum(
        a.activity.minutes
        for a in plan.activities
        if a.activity.kind in work_kinds and a.activity.start_at < rest_start
    )
    tuesday = sum(
        a.activity.minutes
        for a in plan.activities
        if a.activity.kind in work_kinds and a.activity.start_at >= rest_start
    )
    assert monday == 720, "GOLD-007 §4.10: daily work on Monday is 720 min"
    assert tuesday == 326, "GOLD-007 §4.10: daily work on Tuesday is 326 min"
    assert plan.stops[-1].counters.work_today == 326, "GOLD-007 §4.10: counter after the last stop"
    assert [e for e in inserted_events(plan) if e[1] >= rest_start and e[0] == "BREAK"] == [], (
        "GOLD-007 §4.10: no break on Tuesday"
    )

    # 11: one accommodation, the rest is away from base without a sleeper cab
    assert plan.calculation.accommodation == 5500, "GOLD-007 §4.11: one accommodation of 55.00"
    assert source.drivers[0].vehicle.sleeper_cab is False, "GOLD-007 §4.11: no sleeper cab"

    # 12: rank order; {J} alone is half a per diem; K cannot be a first pickup
    assert [p.offer_ids for p in ranked] == [["J", "K"], ["J"]], "GOLD-007 §4.12: {J, K} > {J}"
    assert ranked[1].net_profit_minor == 17414, "GOLD-007 §4.12: {J} earns 174.14"
    assert ranked[1].duration_min == 673, "GOLD-007 §4.12: {J} takes 673 min"
    assert ranked[1].calculation.per_diem == 530, "GOLD-007 §4.12: {J} gets half a per diem"
    k_first, failure = build_plan(
        source, source.drivers[0], _actions(["PICKUP K", "DELIVERY K"]), thresholds=False
    )
    assert k_first is None and failure == "FIRST_DEADHEAD_TOO_LONG", (
        "GOLD-007 §4.12: K as a first pickup fails with FIRST_DEADHEAD_TOO_LONG"
    )


def _actions(labels: list[str]) -> list[Action]:
    return [Action(kind=label.split()[0], offer_id=label.split()[1]) for label in labels]
