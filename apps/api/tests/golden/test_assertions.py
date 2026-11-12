"""Shared assertions, with approved expected values supplied by each golden case."""

from decimal import Decimal

from routepilot.optimization.engine import RouteValidator, optimize

from .cases import EXPECTED, at, case


def assert_golden(number: int) -> None:
    source = case(number)
    expected = EXPECTED[number]
    result = optimize(source)
    driver = source.drivers[0]
    plans = result.per_driver[driver.id]["profit"]
    assert [p.offer_ids for p in plans] == expected["sets"]
    assert [p.net_profit_minor for p in plans[: len(expected["profits"])]] == expected["profits"]
    plan = plans[0]
    stops = [s for s in plan.stops if s.kind in ("PICKUP", "DELIVERY")]
    assert [s.kind[0] + str(s.offer_id) for s in stops] == expected["sequence"]
    assert [s.load_kg_after for s in stops] == expected["kg"]
    assert [s.load_pallet_eq_after for s in stops] == [Decimal(i) for i in expected["eq"]]
    assert [s.service_start_at for s in stops] == [at(*stamp) for stamp in expected["starts"]]
    assert plan.rules_profile == expected.get("profile", "pl_domestic_employee_v1")
    assert plan.finish_at == at(*expected["finish"])
    assert plan.distance_km == Decimal(expected["distance"])
    assert plan.drive_min == expected["drive"]
    assert plan.work_min == expected["work"]
    assert plan.wait_min == 0
    assert plan.fuel_l == Decimal(expected["fuel"])
    assert plan.co2_kg == Decimal(expected["co2"])
    assert (
        sum(a.activity.minutes for a in plan.activities if a.activity.kind == "BREAK")
        == expected["breaks"]
    )
    assert (
        sum(a.activity.minutes for a in plan.activities if a.activity.kind == "DAILY_REST")
        == expected["rest"]
    )
    c = plan.calculation
    assert [c.fuel, c.toll, c.driver, c.per_diem, c.accommodation, c.vehicle] == expected[
        "components"
    ]
    assert plan.cost_total_minor == expected["cost"]
    assert plan.revenue_minor == expected["revenue"]
    assert RouteValidator().validate(source, plan).valid
    assert optimize(source) == result
    assert {"LOADING_ORDER_NOT_MODELLED", "SERVICE_TIME_DEFAULTED"}.issubset(plan.warnings)
