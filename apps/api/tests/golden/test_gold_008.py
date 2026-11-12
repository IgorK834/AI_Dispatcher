"""GOLD-008 (Weekend return).

Every assertion of section 4 of specs/golden/GOLD-008.md, one assert per item.
"""

from decimal import ROUND_HALF_UP, Decimal

import pytest

from routepilot.optimization.engine import RouteValidator
from routepilot.optimization.engine.models import Action
from routepilot.optimization.engine.schedule import build_plan

from .fixtures.common import at
from .fixtures.gold_008 import build
from .helpers import action_stops, inside_windows, minutes_of, plans, sequence


@pytest.mark.ac("AC-FEAT-003-37")
def test_gold_008(run) -> None:
    source = build()
    result, repeatable = run(source)
    vehicle = source.drivers[0].vehicle
    ranked = plans(result, "D1")
    plan = ranked[0]
    stops = action_stops(plan)

    # 1: rank 1 plan, offers and order
    assert sorted(plan.offer_ids) == ["L", "M"], "GOLD-008 §4.1: offers of the rank 1 plan"
    assert sequence(plan) == ["PICKUP L", "DELIVERY L", "PICKUP M", "DELIVERY M"], (
        "GOLD-008 §4.1: order of the stops"
    )

    # 2: load after every stop, within capacity (invariant 1)
    assert [s.load_pallet_eq_after for s in stops] == [
        Decimal("6.0"),
        Decimal("0.0"),
        Decimal("4.0"),
        Decimal("0.0"),
    ], "GOLD-008 §4.2: load_pallet_eq_after"
    assert [s.load_kg_after for s in stops] == [600, 0, 350, 0], "GOLD-008 §4.2: load_kg_after"
    assert all(0 <= s.load_kg_after <= vehicle.payload_kg for s in stops), (
        "GOLD-008 §4.2: payload respected"
    )
    assert all(0 <= s.load_pallet_eq_after <= vehicle.pallet_places for s in stops), (
        "GOLD-008 §4.2: pallet places respected"
    )

    # 3: profile
    assert plan.rules_profile == "pl_domestic_employee_v1", "GOLD-008 §4.3: rules_profile"

    # 4: service starts, inside the windows (invariant 4)
    assert [s.service_start_at for s in stops] == [
        at(3, 6, 0),
        at(3, 12, 48),
        at(3, 13, 18),
        at(4, 6, 51),
    ], "GOLD-008 §4.4: service start times"
    assert inside_windows(source, plan), "GOLD-008 §4.4: every service start inside its window"

    # 5: totals
    assert plan.distance_km == Decimal("697.96"), "GOLD-008 §4.5: distance_km"
    assert plan.drive_min == 696, "GOLD-008 §4.5: drive_min"
    assert plan.work_min == 816, "GOLD-008 §4.5: work_min"
    assert plan.wait_min == 0, "GOLD-008 §4.5: wait_min"
    assert minutes_of(plan, "BREAK") == 45, "GOLD-008 §4.5: break minutes"
    assert minutes_of(plan, "DAILY_REST") == 660, "GOLD-008 §4.5: daily rest minutes"
    assert plan.finish_at == at(4, 7, 21), "GOLD-008 §4.5: finish_at"

    # 6: fuel and CO2 (invariant 17)
    assert plan.fuel_l == Decimal("84.854"), "GOLD-008 §4.6: fuel_l"
    assert plan.co2_kg == Decimal("220.62"), "GOLD-008 §4.6: co2_kg"
    assert plan.co2_kg == (plan.fuel_l * Decimal("2.6")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    ), "GOLD-008 §4.6: co2_kg = fuel_l x 2.6"

    # 7: cost breakdown in minor units (invariant 7)
    c = plan.calculation
    assert (c.fuel, c.toll, c.driver, c.per_diem, c.accommodation, c.vehicle) == (
        15359,
        0,
        19040,
        1589,
        5500,
        8376,
    ), "GOLD-008 §4.7: cost components"
    assert plan.cost_total_minor == 49864, "GOLD-008 §4.7: cost_total_minor"
    assert plan.revenue_minor == 54500, "GOLD-008 §4.7: revenue_minor"
    assert plan.net_profit_minor == 4636, "GOLD-008 §4.7: net_profit_minor"
    assert plan.net_profit_minor == plan.revenue_minor - plan.cost_total_minor, (
        "GOLD-008 §4.7: profit reconstructs"
    )

    # not a section 4 item: the warning flags every golden plan carries
    assert {"LOADING_ORDER_NOT_MODELLED", "SERVICE_TIME_DEFAULTED"} <= set(plan.warnings), (
        "GOLD-008: warning flags"
    )

    # 8: validator and determinism (invariant 8)
    assert RouteValidator().validate(source, plan).valid, (
        "GOLD-008 §4.8: RouteValidator accepts the plan"
    )
    assert repeatable, "GOLD-008 §4.8: a second run is identical"

    # 9: the plan ends at the home base before home_by (invariant 13)
    driver = source.drivers[0]
    # FR-9: an informational WEEKLY_REST marker may follow END; END is the last real stop.
    real_stops = [s for s in plan.stops if s.kind != "WEEKLY_REST"]
    assert real_stops[-1].kind == "END", "GOLD-008 §4.9: the plan ends with an END stop"
    assert real_stops[-1].point == driver.home, "GOLD-008 §4.9: END is at the home base Katowice"
    assert plan.home_reached, "GOLD-008 §4.9: home_reached"
    assert plan.finish_at == at(4, 7, 21), "GOLD-008 §4.9: finish_at Fri 07:21"
    assert plan.finish_at <= driver.home_by, "GOLD-008 §4.9: finish_at <= home_by (Fri 18:00)"

    # 10: exactly one plan; every single-offer plan drives home empty and loses money
    assert len(ranked) == 1, "GOLD-008 §4.10: exactly one plan is returned"
    for offer_id, loss in (("L", -15046), ("N", -23359), ("M", -26248)):
        single, failure = build_plan(
            source,
            driver,
            _actions([f"PICKUP {offer_id}", f"DELIVERY {offer_id}"]),
            thresholds=False,
        )
        assert failure is None and single is not None, f"GOLD-008 §4.10: {{{offer_id}}} schedulable"
        assert single.net_profit_minor == loss, f"GOLD-008 §4.10: {{{offer_id}}} earns {loss}"
        assert single.net_profit_minor < driver.cost_profile.min_profit_minor, (
            f"GOLD-008 §4.10: {{{offer_id}}} is below min_profit"
        )

    # 11: offer N is rejected as BELOW_MIN_PROFIT
    assert [(r.offer_id, r.code) for r in result.rejections] == [("N", "BELOW_MIN_PROFIT")], (
        "GOLD-008 §4.11: N is rejected with BELOW_MIN_PROFIT"
    )

    # 12: baseline_single is empty, the optimised fleet profit is strictly greater (invariant 15)
    assert result.baselines["baseline_single"].assignments == [], (
        "GOLD-008 §4.12: baseline_single is empty"
    )
    assert result.baselines["baseline_single"].totals.net_profit_minor == 0, (
        "GOLD-008 §4.12: baseline_single profit is 0.00"
    )
    assert result.fleet["profit"].totals.net_profit_minor == 4636, (
        "GOLD-008 §4.12: optimised fleet profit is 46.36"
    )
    assert result.fleet["profit"].totals.net_profit_minor > 0, (
        "GOLD-008 §4.12: fleet profit is strictly greater than the baseline"
    )

    # 13: weekly counter after the plan
    assert plan.stops[-1].counters.work_week == 2316, "GOLD-008 §4.13: work_week = 1500 + 816"
    assert plan.stops[-1].counters.work_week <= 3600, "GOLD-008 §4.13: work_week <= 3600"


def _actions(labels: list[str]) -> list[Action]:
    return [Action(kind=label.split()[0], offer_id=label.split()[1]) for label in labels]
