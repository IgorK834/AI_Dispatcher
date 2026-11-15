"""Plan load metrics (FEAT-010 FR-10, AC-FEAT-010-10) and their stored-stop form (FR-11)."""

from datetime import timedelta
from decimal import Decimal

import pytest

from routepilot.optimization.engine import optimize
from routepilot.optimization.engine.models import Action, PlanLeg, VehicleSnapshot
from routepilot.optimization.engine.plan_metrics import load_metrics, stop_load_metrics
from tests.golden.fixtures.gold_001 import build

from .factories import T, point

VAN = VehicleSnapshot(pallet_places=10, payload_kg=1000)
ACTIONS = [
    Action(kind="PICKUP", offer_id="A"),
    Action(kind="PICKUP", offer_id="B"),
    Action(kind="DELIVERY", offer_id="A"),
    Action(kind="DELIVERY", offer_id="B"),
]


def leg(km: str, pallet_eq: str, kg: int) -> PlanLeg:
    return PlanLeg(
        start=point("A"),
        end=point("B", 52, 20),
        distance_km=Decimal(km),
        drive_min=60,
        load_kg=kg,
        load_pallet_eq=Decimal(pallet_eq),
        departed_at=T,
        arrived_at=T + timedelta(hours=1),
    )


@pytest.mark.ac("AC-FEAT-010-10")
def test_load_factors_are_weighted_by_kilometres_and_orders_on_board_are_counted() -> None:
    legs = [leg("100", "4", 300), leg("50", "0", 0), leg("150", "8", 900)]
    assert load_metrics(legs, ACTIONS, VAN) == (Decimal("0.5333"), Decimal("0.5500"), 2)
    # A chain never has more than one order on board.
    chain = [ACTIONS[0], ACTIONS[2], ACTIONS[1], ACTIONS[3]]
    assert load_metrics(legs, chain, VAN)[2] == 1


@pytest.mark.ac("AC-FEAT-010-10")
def test_a_plan_without_kilometres_has_zero_factors() -> None:
    assert load_metrics([], ACTIONS, VAN) == (Decimal("0"), Decimal("0"), 2)
    assert load_metrics([leg("0", "4", 300)], [], VAN) == (Decimal("0"), Decimal("0"), 0)
    assert stop_load_metrics([], VAN) == (Decimal("0"), Decimal("0"), 0)


@pytest.mark.ac("AC-FEAT-010-11")
def test_stored_stops_give_the_leg_example_and_ignore_the_weekly_rest_marker() -> None:
    zero, km = Decimal("0"), Decimal
    stops = [
        ("START", zero, zero, 0),
        ("PICKUP", zero, km("4"), 300),  # A on board
        ("DELIVERY", km("100"), zero, 0),  # 100 km at 4 EP / 300 kg
        ("BREAK", zero, zero, 0),
        ("PICKUP", km("50"), km("8"), 900),  # 50 km empty, then B on board
        ("DAILY_REST", zero, km("8"), 900),
        ("DELIVERY", km("150"), zero, 0),  # 150 km at 8 EP / 900 kg
        ("END", zero, zero, 0),
        ("WEEKLY_REST", km("150"), zero, 0),  # a copy of the last leg: not counted
    ]
    assert stop_load_metrics(stops, VAN) == (Decimal("0.5333"), Decimal("0.5500"), 1)


@pytest.mark.ac("AC-FEAT-010-10")
def test_factors_are_rounded_half_up_to_four_places_and_stay_within_zero_and_one() -> None:
    ep, kg, _ = load_metrics([leg("3", "1", 1), leg("3", "0", 0), leg("3", "0", 0)], [], VAN)
    assert (ep, kg) == (Decimal("0.0333"), Decimal("0.0003"))
    ep, kg, _ = load_metrics([leg("1", "0.5", 5), leg("3", "0", 0)], [], VAN)
    assert (ep, kg) == (Decimal("0.0125"), Decimal("0.0013"))  # 0.00125 rounds half-up
    full = load_metrics([leg("10", "10", 1000)], [], VAN)
    assert full[:2] == (Decimal("1"), Decimal("1"))


@pytest.mark.ac("AC-FEAT-010-10")
@pytest.mark.ac("AC-FEAT-010-11")
def test_engine_plans_carry_the_metrics_and_stored_stops_give_the_same_values() -> None:
    source = build()  # GOLD-001: pick A, pick B, drop A, pick C, drop B, drop C
    vehicle = source.drivers[0].vehicle
    plans = optimize(source).per_driver["D1"]["profit"]
    assert plans
    for plan in plans:
        expected = load_metrics(plan.legs, plan.actions, vehicle)
        assert (plan.load_factor_ep, plan.load_factor_kg, plan.max_orders_on_board) == expected
        assert 0 <= plan.load_factor_ep <= 1 and 0 <= plan.load_factor_kg <= 1
        stored = [
            (stop.kind, stop.leg_km, stop.load_pallet_eq_after, stop.load_kg_after)
            for stop in plan.stops
        ]
        assert stop_load_metrics(stored, vehicle) == expected  # leg i ends at stop i
    assert plans[0].max_orders_on_board == 2 and plans[0].load_factor_ep > 0
