"""GOLD-002 (Tempting detour).

Every assertion of section 4 of specs/golden/GOLD-002.md, one assert per item.
"""

from decimal import ROUND_HALF_UP, Decimal

import pytest

from routepilot.optimization.engine import RouteValidator
from routepilot.optimization.engine.models import Action
from routepilot.optimization.engine.schedule import build_plan

from .fixtures.common import at
from .fixtures.gold_002 import build
from .helpers import action_stops, inside_windows, minutes_of, plans, sequence


@pytest.mark.ac("AC-FEAT-003-31")
def test_gold_002(run) -> None:
    source = build()
    result, repeatable = run(source)
    vehicle = source.drivers[0].vehicle
    ranked = plans(result, "D1")
    plan = ranked[0]
    stops = action_stops(plan)

    # 1: rank 1 plan, offers and order
    assert sorted(plan.offer_ids) == ["A"], "GOLD-002 §4.1: offers of the rank 1 plan"
    assert sequence(plan) == ["PICKUP A", "DELIVERY A"], "GOLD-002 §4.1: order of the stops"

    # 2: load after every stop, within capacity (invariant 1)
    assert [s.load_pallet_eq_after for s in stops] == [Decimal("3.0"), Decimal("0.0")], (
        "GOLD-002 §4.2: load_pallet_eq_after"
    )
    assert [s.load_kg_after for s in stops] == [300, 0], "GOLD-002 §4.2: load_kg_after"
    assert all(0 <= s.load_kg_after <= vehicle.payload_kg for s in stops), (
        "GOLD-002 §4.2: payload respected"
    )
    assert all(0 <= s.load_pallet_eq_after <= vehicle.pallet_places for s in stops), (
        "GOLD-002 §4.2: pallet places respected"
    )

    # 3: profile
    assert plan.rules_profile == "pl_domestic_employee_v1", "GOLD-002 §4.3: rules_profile"

    # 4: service starts, inside the windows (invariant 4)
    assert [s.service_start_at for s in stops] == [at(0, 6, 0), at(0, 10, 0)], (
        "GOLD-002 §4.4: service start times"
    )
    assert inside_windows(source, plan), "GOLD-002 §4.4: every service start inside its window"

    # 5: totals
    assert plan.distance_km == Decimal("210.45"), "GOLD-002 §4.5: distance_km"
    assert plan.drive_min == 210, "GOLD-002 §4.5: drive_min"
    assert plan.work_min == 270, "GOLD-002 §4.5: work_min"
    assert plan.wait_min == 0, "GOLD-002 §4.5: wait_min"
    assert minutes_of(plan, "BREAK") == 0, "GOLD-002 §4.5: break minutes"
    assert minutes_of(plan, "DAILY_REST") == 0, "GOLD-002 §4.5: daily rest minutes"
    assert plan.finish_at == at(0, 10, 30), "GOLD-002 §4.5: finish_at"

    # 6: fuel and CO2 (invariant 17)
    assert plan.fuel_l == Decimal("24.898"), "GOLD-002 §4.6: fuel_l"
    assert plan.co2_kg == Decimal("64.73"), "GOLD-002 §4.6: co2_kg"
    assert plan.co2_kg == (plan.fuel_l * Decimal("2.6")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    ), "GOLD-002 §4.6: co2_kg = fuel_l x 2.6"

    # 7: cost breakdown in minor units (invariant 7)
    c = plan.calculation
    assert (c.fuel, c.toll, c.driver, c.per_diem, c.accommodation, c.vehicle) == (
        4507,
        0,
        6300,
        0,
        0,
        2525,
    ), "GOLD-002 §4.7: cost components"
    assert plan.cost_total_minor == 13332, "GOLD-002 §4.7: cost_total_minor"
    assert plan.revenue_minor == 20000, "GOLD-002 §4.7: revenue_minor"
    assert plan.net_profit_minor == 6668, "GOLD-002 §4.7: net_profit_minor"
    assert plan.net_profit_minor == plan.revenue_minor - plan.cost_total_minor, (
        "GOLD-002 §4.7: profit reconstructs"
    )

    # not a section 4 item: the warning flags every golden plan carries
    assert {"LOADING_ORDER_NOT_MODELLED", "SERVICE_TIME_DEFAULTED"} <= set(plan.warnings), (
        "GOLD-002: warning flags"
    )

    # 8: validator and determinism (invariant 8)
    assert RouteValidator().validate(source, plan).valid, (
        "GOLD-002 §4.8: RouteValidator accepts the plan"
    )
    assert repeatable, "GOLD-002 §4.8: a second run is identical"

    # 9: {A, X} is feasible and ranks second; adding X raises revenue but lowers profit
    assert ranked[1].offer_ids == ["A", "X"], "GOLD-002 §4.9: {A, X} ranks second"
    assert ranked[1].net_profit_minor == 5334, "GOLD-002 §4.9: net_profit_minor of {A, X}"
    assert ranked[1].revenue_minor - plan.revenue_minor == 11500, "GOLD-002 §4.9: X adds 115.00"
    assert ranked[1].cost_total_minor - plan.cost_total_minor == 12834, (
        "GOLD-002 §4.9: X adds 128.34 of cost"
    )
    assert ranked[1].calculation.per_diem == 530, "GOLD-002 §4.9: half a domestic per diem, 5.30"
    assert ranked[1].duration_min == 551, "GOLD-002 §4.9: the trip grows to 551 min"

    # 10: no plan consists of X alone; its single-offer plan is below min_profit
    assert len(ranked) == 2, "GOLD-002 §4.10: exactly two plans are returned"
    assert ["X"] not in [p.offer_ids for p in ranked], "GOLD-002 §4.10: X alone is not returned"
    alone, failure = build_plan(
        source,
        source.drivers[0],
        [Action(kind="PICKUP", offer_id="X"), Action(kind="DELIVERY", offer_id="X")],
        thresholds=False,
    )
    assert failure is None and alone is not None, "GOLD-002 §4.10: X alone is schedulable"
    assert alone.net_profit_minor == -1905, "GOLD-002 §4.10: X alone earns -19.05"
