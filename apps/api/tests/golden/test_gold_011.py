"""GOLD-011 (Consolidation beats a chain).

Every assertion of section 4 of specs/golden/GOLD-011.md, one assert per item. The values were
approved by the owner on 2026-11-15 (FEAT-010, AC-FEAT-010-13).
"""

from decimal import ROUND_HALF_UP, Decimal

import pytest

from routepilot.optimization.engine import RouteValidator

from .fixtures.common import at
from .fixtures.gold_011 import build
from .helpers import action_stops, inserted_events, inside_windows, minutes_of, plans, sequence


@pytest.mark.ac("AC-FEAT-010-13")
def test_gold_011(run) -> None:
    source = build()
    result, repeatable = run(source)
    vehicle = source.drivers[0].vehicle
    ranked = plans(result, "D1")
    plan = ranked[0]
    stops = action_stops(plan)

    # 1: rank 1 plan, offers and order
    assert sorted(plan.offer_ids) == ["A1", "A2", "A3", "A4", "R"], "GOLD-011 §4.1: offers"
    assert sequence(plan) == [
        "PICKUP A1",
        "PICKUP A2",
        "PICKUP A3",
        "PICKUP A4",
        "DELIVERY A1",
        "DELIVERY A2",
        "DELIVERY A3",
        "DELIVERY A4",
        "PICKUP R",
        "DELIVERY R",
    ], "GOLD-011 §4.1: order of the stops"

    # 2: the chain set is not the top plan
    assert not {"C1", "C2", "C3"} & set(plan.offer_ids), "GOLD-011 §4.2: no chain offer in rank 1"
    assert all(sorted(p.offer_ids) != ["C1", "C2", "C3"] for p in ranked[:3]), (
        "GOLD-011 §4.2: the chain set is not among the three best"
    )

    # 3: load metrics (FEAT-010 FR-10)
    assert plan.max_orders_on_board == 4, "GOLD-011 §4.3: max_orders_on_board"
    assert plan.load_factor_ep == Decimal("0.8000"), "GOLD-011 §4.3: load_factor_ep"
    assert plan.load_factor_kg == Decimal("0.7512"), "GOLD-011 §4.3: load_factor_kg"

    # 4: load after every stop, within capacity (invariant 1)
    assert [s.load_pallet_eq_after for s in stops] == [
        Decimal(n) for n in (3, 5, 8, 10, 7, 5, 2, 0, 6, 0)
    ], "GOLD-011 §4.4: load_pallet_eq_after"
    assert [s.load_kg_after for s in stops] == [
        300, 520, 830, 1030, 730, 510, 200, 0, 600, 0,
    ], "GOLD-011 §4.4: load_kg_after"  # fmt: skip
    assert all(0 <= s.load_kg_after <= vehicle.payload_kg for s in stops)
    assert all(0 <= s.load_pallet_eq_after <= vehicle.pallet_places for s in stops)

    # 5: profile
    assert plan.rules_profile == "eu561_van_international_v1", "GOLD-011 §4.5: rules_profile"

    # 6: service starts, inside the windows (invariant 4)
    assert [s.service_start_at for s in stops] == [
        at(0, 6, 0),
        at(0, 6, 30),
        at(0, 7, 0),
        at(0, 7, 30),
        at(0, 16, 42),
        at(0, 17, 12),
        at(0, 17, 42),
        at(0, 18, 12),
        at(1, 6, 0),
        at(1, 15, 12),
    ], "GOLD-011 §4.6: service start times"
    assert inside_windows(source, plan), "GOLD-011 §4.6: every service start inside its window"

    # 7: totals
    assert plan.distance_km == Decimal("956.66"), "GOLD-011 §4.7: distance_km"
    assert plan.empty_km == Decimal("0.00"), "GOLD-011 §4.7: empty_km"
    assert plan.drive_min == 954, "GOLD-011 §4.7: drive_min"
    assert plan.work_min == 1254, "GOLD-011 §4.7: work_min"
    assert plan.wait_min == 0, "GOLD-011 §4.7: wait_min"
    assert minutes_of(plan, "BREAK") == 90, "GOLD-011 §4.7: break minutes"
    assert minutes_of(plan, "DAILY_REST") == 678, "GOLD-011 §4.7: daily rest minutes"
    assert plan.finish_at == at(1, 15, 42), "GOLD-011 §4.7: finish_at"

    # 8: fuel and CO2 (invariant 17)
    assert plan.fuel_l == Decimal("122.445"), "GOLD-011 §4.8: fuel_l"
    assert plan.co2_kg == Decimal("318.36"), "GOLD-011 §4.8: co2_kg"
    assert plan.co2_kg == (plan.fuel_l * Decimal("2.6")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    ), "GOLD-011 §4.8: co2_kg = fuel_l x 2.6"

    # 9: cost breakdown in minor units (invariant 7)
    c = plan.calculation
    assert (c.fuel, c.toll, c.driver, c.per_diem, c.accommodation, c.vehicle) == (
        22163,
        0,
        29260,
        0,
        5500,
        11480,
    ), "GOLD-011 §4.9: cost components"
    assert plan.cost_total_minor == 68403, "GOLD-011 §4.9: cost_total_minor"
    assert plan.revenue_minor == 121200, "GOLD-011 §4.9: revenue_minor"
    assert plan.net_profit_minor == 52797, "GOLD-011 §4.9: net_profit_minor"
    assert plan.net_profit_minor == plan.revenue_minor - plan.cost_total_minor

    # 10: ranks 2 and 3
    assert sorted(ranked[1].offer_ids) == ["A1", "A2", "A3", "A4"]
    assert ranked[1].net_profit_minor == 49397, "GOLD-011 §4.10: rank 2"
    assert sorted(ranked[2].offer_ids) == ["A1", "A2", "A3", "A4", "C3"]
    assert ranked[2].net_profit_minor == 47361, "GOLD-011 §4.10: rank 3"

    # 11: validator and determinism (invariant 8)
    assert RouteValidator().validate(source, plan).valid, "GOLD-011 §4.11: validator"
    assert repeatable, "GOLD-011 §4.11: a second run is identical"

    # 12: warning flags, and the inserted events of §3.2
    assert {"LOADING_ORDER_NOT_MODELLED", "SERVICE_TIME_DEFAULTED"} <= set(plan.warnings)
    assert inserted_events(plan) == [
        ("BREAK", at(0, 12, 0), 45),
        ("DAILY_REST", at(0, 18, 42), 678),
        ("BREAK", at(1, 11, 0), 45),
    ], "GOLD-011 §3.2: BREAK Mon 12:00, DAILY_REST 678 Mon 18:42, BREAK Tue 11:00"
