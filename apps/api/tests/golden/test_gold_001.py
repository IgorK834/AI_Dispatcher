"""GOLD-001 (Consolidated loads on one van).

Every assertion of section 4 of specs/golden/GOLD-001.md, one assert per item.
"""

from decimal import ROUND_HALF_UP, Decimal

import pytest

from routepilot.optimization.engine import RouteValidator

from .fixtures.common import at
from .fixtures.gold_001 import build
from .helpers import action_stops, inserted_events, inside_windows, minutes_of, plans, sequence


@pytest.mark.ac("AC-FEAT-003-30")
def test_gold_001(run) -> None:
    source = build()
    result, repeatable = run(source)
    vehicle = source.drivers[0].vehicle
    ranked = plans(result, "D1")
    plan = ranked[0]
    stops = action_stops(plan)

    # 1: rank 1 plan, offers and order
    assert sorted(plan.offer_ids) == ["A", "B", "C"], "GOLD-001 §4.1: offers of the rank 1 plan"
    assert sequence(plan) == [
        "PICKUP A",
        "PICKUP B",
        "DELIVERY A",
        "PICKUP C",
        "DELIVERY B",
        "DELIVERY C",
    ], "GOLD-001 §4.1: order of the stops"

    # 2: load after every stop, within capacity (invariant 1)
    assert [s.load_pallet_eq_after for s in stops] == [
        Decimal("4.0"),
        Decimal("8.0"),
        Decimal("4.0"),
        Decimal("6.0"),
        Decimal("2.0"),
        Decimal("0.0"),
    ], "GOLD-001 §4.2: load_pallet_eq_after"
    assert [s.load_kg_after for s in stops] == [380, 800, 420, 620, 200, 0], (
        "GOLD-001 §4.2: load_kg_after"
    )
    assert all(0 <= s.load_kg_after <= vehicle.payload_kg for s in stops), (
        "GOLD-001 §4.2: payload respected"
    )
    assert all(0 <= s.load_pallet_eq_after <= vehicle.pallet_places for s in stops), (
        "GOLD-001 §4.2: pallet places respected"
    )

    # 3: profile
    assert plan.rules_profile == "eu561_van_international_v1", "GOLD-001 §4.3: rules_profile"

    # 4: service starts, inside the windows (invariant 4)
    assert [s.service_start_at for s in stops] == [
        at(0, 6, 0),
        at(0, 8, 23),
        at(0, 10, 31),
        at(0, 11, 1),
        at(0, 17, 4),
        at(1, 7, 25),
    ], "GOLD-001 §4.4: service start times"
    assert inside_windows(source, plan), "GOLD-001 §4.4: every service start inside its window"

    # 5: totals
    assert plan.distance_km == Decimal("624.81"), "GOLD-001 §4.5: distance_km"
    assert plan.drive_min == 625, "GOLD-001 §4.5: drive_min"
    assert plan.work_min == 805, "GOLD-001 §4.5: work_min"
    assert plan.wait_min == 0, "GOLD-001 §4.5: wait_min"
    assert minutes_of(plan, "BREAK") == 90, "GOLD-001 §4.5: break minutes"
    assert minutes_of(plan, "DAILY_REST") == 660, "GOLD-001 §4.5: daily rest minutes"
    assert plan.finish_at == at(1, 7, 55), "GOLD-001 §4.5: finish_at"

    # 6: fuel and CO2 (invariant 17)
    assert plan.fuel_l == Decimal("76.601"), "GOLD-001 §4.6: fuel_l"
    assert plan.co2_kg == Decimal("199.16"), "GOLD-001 §4.6: co2_kg"
    assert plan.co2_kg == (plan.fuel_l * Decimal("2.6")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    ), "GOLD-001 §4.6: co2_kg = fuel_l x 2.6"

    # 7: cost breakdown in minor units (invariant 7)
    c = plan.calculation
    assert (c.fuel, c.toll, c.driver, c.per_diem, c.accommodation, c.vehicle) == (
        13865,
        0,
        18783,
        0,
        5500,
        7498,
    ), "GOLD-001 §4.7: cost components"
    assert plan.cost_total_minor == 45646, "GOLD-001 §4.7: cost_total_minor"
    assert plan.revenue_minor == 78000, "GOLD-001 §4.7: revenue_minor"
    assert plan.net_profit_minor == 32354, "GOLD-001 §4.7: net_profit_minor"
    assert plan.net_profit_minor == plan.revenue_minor - plan.cost_total_minor, (
        "GOLD-001 §4.7: profit reconstructs"
    )

    # not a section 4 item: the warning flags every golden plan carries
    assert {"LOADING_ORDER_NOT_MODELLED", "SERVICE_TIME_DEFAULTED"} <= set(plan.warnings), (
        "GOLD-001: warning flags"
    )

    # 8: validator and determinism (invariant 8)
    assert RouteValidator().validate(source, plan).valid, (
        "GOLD-001 §4.8: RouteValidator accepts the plan"
    )
    assert repeatable, "GOLD-001 §4.8: a second run is identical"

    # 9: inserted events (45-minute breaks always on the 561 profile, G5)
    assert inserted_events(plan) == [
        ("BREAK", at(0, 12, 0), 45),
        ("BREAK", at(0, 17, 45), 45),
        ("DAILY_REST", at(0, 19, 0), 660),
    ], "GOLD-001 §4.9: BREAK 45 at Mon 12:00, BREAK 45 at Mon 17:45, DAILY_REST 660 at Mon 19:00"

    # 10: warning flags
    assert {"LOADING_ORDER_NOT_MODELLED", "SERVICE_TIME_DEFAULTED"} <= set(plan.warnings), (
        "GOLD-001 §4.10: warning flags"
    )

    # 11: top-K list, distinct sets in the order of section 3.1 (invariant 10)
    assert len(ranked) == 6, "GOLD-001 §4.11: six plans are returned"
    assert [p.offer_ids for p in ranked] == [
        ["A", "B", "C"],
        ["A", "B"],
        ["B", "C"],
        ["A"],
        ["A", "C"],
        ["B"],
    ], "GOLD-001 §4.11: order of the offer sets"
    assert [p.net_profit_minor for p in ranked] == [32354, 17548, 14562, 5611, 4085, 1129], (
        "GOLD-001 §4.11: profit of each ranked plan"
    )

    # 12: fastest and fuel rank {A} first and respect invariant 16 against the profit plan
    fastest = plans(result, "D1", "fastest")
    fuel = plans(result, "D1", "fuel")
    assert fastest[0].offer_ids == ["A"], "GOLD-001 §4.12: fastest ranks {A} first"
    assert fastest[0].finish_at == at(0, 10, 30), "GOLD-001 §4.12: fastest finish_at Mon 10:30"
    assert fuel[0].offer_ids == ["A"], "GOLD-001 §4.12: fuel ranks {A} first"
    assert fuel[0].fuel_l == Decimal("25.215"), "GOLD-001 §4.12: fuel rank 1 burns 25.215 l"
    assert fastest[0].finish_at <= plan.finish_at, "GOLD-001 §4.12: fastest no later than profit"
    assert fuel[0].fuel_l <= plan.fuel_l, "GOLD-001 §4.12: fuel burns no more than profit"
