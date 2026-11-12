"""Engine construction, rejection and baseline contracts (FEAT-003)."""

from datetime import timedelta
from decimal import Decimal

import pytest

from routepilot.optimization.engine import RouteValidator, optimize
from routepilot.optimization.engine.models import Action
from routepilot.optimization.engine.schedule import build_plan

from .factories import T, driver, offer, point, snapshot


@pytest.mark.ac("AC-FEAT-003-22")
def test_empty_and_infeasible_result() -> None:
    a = point("A")
    b = point("B", 52.2297, 21.0122)
    source = snapshot([driver(a)], [offer("X", a, b, weight=2000)])
    result = optimize(source)
    assert all(not plans for plans in result.per_driver["D"].values())
    assert len(result.rejections) == 1
    assert result.rejections[0].code == "OVERWEIGHT"
    assert optimize(snapshot([], [])).fleet["profit"].totals.net_profit_minor == 0


@pytest.mark.ac("AC-FEAT-003-18")
def test_first_wait_defers_departure() -> None:
    a = point("A")
    source = snapshot(
        [driver(a)],
        [
            offer(
                "X",
                a,
                a,
                pickup=(T + timedelta(minutes=45), T + timedelta(hours=1)),
                delivery=(T, T + timedelta(hours=8)),
            )
        ],
    )
    plan, _ = build_plan(
        source,
        source.drivers[0],
        [Action(kind="PICKUP", offer_id="X"), Action(kind="DELIVERY", offer_id="X")],
    )
    assert plan is not None
    assert plan.departure_at == T + timedelta(minutes=45)
    assert plan.wait_min == 0
    assert RouteValidator().validate(source, plan).valid


@pytest.mark.ac("AC-FEAT-003-26")
def test_consolidation_baselines_and_validation() -> None:
    a, b = point("A"), point("B", 52.2297, 21.0122)
    source = snapshot(
        [driver(a, payload=880, pallets=8)],
        [
            offer(
                "P", a, b, weight=320, pallets=4, revenue=21000, pallet_type="INDUSTRIAL_1200x1000"
            ),
            offer("Q", a, b, weight=240, pallets=3, revenue=15000),
            offer("R", a, b, weight=160, pallets=2, revenue=10000),
        ],
    )
    result = optimize(source)
    plan = result.per_driver["D"]["profit"][0]
    assert plan.offer_ids == ["P", "R"]
    assert plan.net_profit_minor == 19642
    assert plan.fuel_l == Decimal("18.368")
    assert plan.co2_kg == Decimal("47.76")
    assert plan.finish_at == T + timedelta(minutes=268)
    assert [p.offer_ids for p in result.per_driver["D"]["profit"]] == [
        ["P", "R"],
        ["Q", "R"],
        ["P"],
        ["Q"],
        ["R"],
    ]
    assert {p.kind for p in result.baseline_plans} == {"baseline_single", "baseline_greedy"}
    assert optimize(source) == result
