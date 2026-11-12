"""GOLD-004 (Time window forces the order).

Every assertion of section 4 of specs/golden/GOLD-004.md, one assert per item.
"""

from decimal import ROUND_HALF_UP, Decimal

import pytest

from routepilot.optimization.engine import RouteValidator
from routepilot.optimization.engine.models import Action
from routepilot.optimization.engine.schedule import build_plan

from .fixtures.common import at
from .fixtures.gold_004 import build
from .helpers import action_stops, inserted_events, inside_windows, minutes_of, plans, sequence


@pytest.mark.ac("AC-FEAT-003-33")
def test_gold_004(run) -> None:
    source = build()
    result, repeatable = run(source)
    vehicle = source.drivers[0].vehicle
    ranked = plans(result, "D2")
    plan = ranked[0]
    stops = action_stops(plan)

    # 1: rank 1 plan, offers and order
    assert sorted(plan.offer_ids) == ["G", "H"], "GOLD-004 §4.1: offers of the rank 1 plan"
    assert sequence(plan) == ["PICKUP G", "PICKUP H", "DELIVERY H", "DELIVERY G"], (
        "GOLD-004 §4.1: order of the stops"
    )

    # 2: load after every stop, within capacity (invariant 1)
    assert [s.load_pallet_eq_after for s in stops] == [
        Decimal("3.0"),
        Decimal("6.0"),
        Decimal("3.0"),
        Decimal("0.0"),
    ], "GOLD-004 §4.2: load_pallet_eq_after"
    assert [s.load_kg_after for s in stops] == [300, 650, 300, 0], "GOLD-004 §4.2: load_kg_after"
    assert all(0 <= s.load_kg_after <= vehicle.payload_kg for s in stops), (
        "GOLD-004 §4.2: payload respected"
    )
    assert all(0 <= s.load_pallet_eq_after <= vehicle.pallet_places for s in stops), (
        "GOLD-004 §4.2: pallet places respected"
    )

    # 3: profile
    assert plan.rules_profile == "pl_domestic_employee_v1", "GOLD-004 §4.3: rules_profile"

    # 4: service starts, inside the windows (invariant 4)
    assert [s.service_start_at for s in stops] == [
        at(0, 6, 0),
        at(0, 6, 30),
        at(0, 10, 30),
        at(0, 13, 23),
    ], "GOLD-004 §4.4: service start times"
    assert inside_windows(source, plan), "GOLD-004 §4.4: every service start inside its window"

    # 5: totals
    assert plan.distance_km == Decimal("323.43"), "GOLD-004 §4.5: distance_km"
    assert plan.drive_min == 323, "GOLD-004 §4.5: drive_min"
    assert plan.work_min == 443, "GOLD-004 §4.5: work_min"
    assert plan.wait_min == 0, "GOLD-004 §4.5: wait_min"
    assert minutes_of(plan, "BREAK") == 30, "GOLD-004 §4.5: break minutes"
    assert minutes_of(plan, "DAILY_REST") == 0, "GOLD-004 §4.5: daily rest minutes"
    assert plan.finish_at == at(0, 13, 53), "GOLD-004 §4.5: finish_at"

    # 6: fuel and CO2 (invariant 17)
    assert plan.fuel_l == Decimal("39.775"), "GOLD-004 §4.6: fuel_l"
    assert plan.co2_kg == Decimal("103.42"), "GOLD-004 §4.6: co2_kg"
    assert plan.co2_kg == (plan.fuel_l * Decimal("2.6")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    ), "GOLD-004 §4.6: co2_kg = fuel_l x 2.6"

    # 7: cost breakdown in minor units (invariant 7)
    c = plan.calculation
    assert (c.fuel, c.toll, c.driver, c.per_diem, c.accommodation, c.vehicle) == (
        7199,
        0,
        10337,
        0,
        0,
        3881,
    ), "GOLD-004 §4.7: cost components"
    assert plan.cost_total_minor == 21417, "GOLD-004 §4.7: cost_total_minor"
    assert plan.revenue_minor == 37000, "GOLD-004 §4.7: revenue_minor"
    assert plan.net_profit_minor == 15583, "GOLD-004 §4.7: net_profit_minor"
    assert plan.net_profit_minor == plan.revenue_minor - plan.cost_total_minor, (
        "GOLD-004 §4.7: profit reconstructs"
    )

    # not a section 4 item: the warning flags every golden plan carries
    assert {"LOADING_ORDER_NOT_MODELLED", "SERVICE_TIME_DEFAULTED"} <= set(plan.warnings), (
        "GOLD-004: warning flags"
    )

    # 8: validator and determinism (invariant 8)
    assert RouteValidator().validate(source, plan).valid, (
        "GOLD-004 §4.8: RouteValidator accepts the plan"
    )
    assert repeatable, "GOLD-004 §4.8: a second run is identical"

    # 9: DELIVERY H precedes DELIVERY G; the geographic order misses H's window
    assert sequence(plan).index("DELIVERY H") < sequence(plan).index("DELIVERY G"), (
        "GOLD-004 §4.9: DELIVERY H precedes DELIVERY G"
    )
    geographic, failure = build_plan(
        source,
        source.drivers[0],
        _actions(["PICKUP G", "PICKUP H", "DELIVERY G", "DELIVERY H"]),
        thresholds=False,
    )
    assert geographic is None and failure == "DELIVERY_WINDOW_MISSED", (
        "GOLD-004 §4.9: the geographic order fails with DELIVERY_WINDOW_MISSED"
    )

    # 10: a 30-minute break when work since the start reaches 6 h
    assert inserted_events(plan) == [("BREAK", at(0, 12, 0), 30)], (
        "GOLD-004 §4.10: BREAK 30 at Mon 12:00"
    )

    # 11: rank order of the offer sets
    assert [p.offer_ids for p in ranked] == [["G", "H"], ["H"], ["G"]], (
        "GOLD-004 §4.11: {G, H} > {H} > {G}"
    )
    assert [p.net_profit_minor for p in ranked[:2]] == [15583, 8624], (
        "GOLD-004 §4.11: profit of {G, H} and {H}"
    )


def _actions(labels: list[str]) -> list[Action]:
    return [Action(kind=label.split()[0], offer_id=label.split()[1]) for label in labels]
