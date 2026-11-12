"""GOLD-010 (Industrial pallets overflow 8 places).

Every assertion of section 4 of specs/golden/GOLD-010.md, one assert per item.
"""

from decimal import ROUND_HALF_UP, Decimal

import pytest

from routepilot.optimization.engine import RouteValidator
from routepilot.optimization.engine.models import Action
from routepilot.optimization.engine.schedule import build_plan

from .fixtures.common import at
from .fixtures.gold_010 import build
from .helpers import action_stops, inside_windows, minutes_of, plans, sequence


@pytest.mark.ac("AC-FEAT-003-39")
def test_gold_010(run) -> None:
    source = build()
    result, repeatable = run(source)
    vehicle = source.drivers[0].vehicle
    ranked = plans(result, "D4")
    plan = ranked[0]
    stops = action_stops(plan)

    # 1: rank 1 plan, offers and order
    assert sorted(plan.offer_ids) == ["P", "R"], "GOLD-010 §4.1: offers of the rank 1 plan"
    assert sequence(plan) == ["PICKUP P", "PICKUP R", "DELIVERY P", "DELIVERY R"], (
        "GOLD-010 §4.1: order of the stops"
    )

    # 2: load after every stop, within capacity (invariant 1)
    assert [s.load_pallet_eq_after for s in stops] == [
        Decimal("6.0"),
        Decimal("8.0"),
        Decimal("2.0"),
        Decimal("0.0"),
    ], "GOLD-010 §4.2: load_pallet_eq_after"
    assert [s.load_kg_after for s in stops] == [320, 480, 160, 0], "GOLD-010 §4.2: load_kg_after"
    assert all(0 <= s.load_kg_after <= vehicle.payload_kg for s in stops), (
        "GOLD-010 §4.2: payload respected"
    )
    assert all(0 <= s.load_pallet_eq_after <= vehicle.pallet_places for s in stops), (
        "GOLD-010 §4.2: pallet places respected"
    )

    # 3: profile
    assert plan.rules_profile == "pl_domestic_employee_v1", "GOLD-010 §4.3: rules_profile"

    # 4: service starts, inside the windows (invariant 4)
    assert [s.service_start_at for s in stops] == [
        at(0, 6, 0),
        at(0, 6, 30),
        at(0, 9, 28),
        at(0, 9, 58),
    ], "GOLD-010 §4.4: service start times"
    assert inside_windows(source, plan), "GOLD-010 §4.4: every service start inside its window"

    # 5: totals
    assert plan.distance_km == Decimal("148.37"), "GOLD-010 §4.5: distance_km"
    assert plan.drive_min == 148, "GOLD-010 §4.5: drive_min"
    assert plan.work_min == 268, "GOLD-010 §4.5: work_min"
    assert plan.wait_min == 0, "GOLD-010 §4.5: wait_min"
    assert minutes_of(plan, "BREAK") == 0, "GOLD-010 §4.5: break minutes"
    assert minutes_of(plan, "DAILY_REST") == 0, "GOLD-010 §4.5: daily rest minutes"
    assert plan.finish_at == at(0, 10, 28), "GOLD-010 §4.5: finish_at"

    # 6: fuel and CO2 (invariant 17)
    assert plan.fuel_l == Decimal("18.368"), "GOLD-010 §4.6: fuel_l"
    assert plan.co2_kg == Decimal("47.76"), "GOLD-010 §4.6: co2_kg"
    assert plan.co2_kg == (plan.fuel_l * Decimal("2.6")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    ), "GOLD-010 §4.6: co2_kg = fuel_l x 2.6"

    # 7: cost breakdown in minor units (invariant 7)
    c = plan.calculation
    assert (c.fuel, c.toll, c.driver, c.per_diem, c.accommodation, c.vehicle) == (
        3325,
        0,
        6253,
        0,
        0,
        1780,
    ), "GOLD-010 §4.7: cost components"
    assert plan.cost_total_minor == 11358, "GOLD-010 §4.7: cost_total_minor"
    assert plan.revenue_minor == 31000, "GOLD-010 §4.7: revenue_minor"
    assert plan.net_profit_minor == 19642, "GOLD-010 §4.7: net_profit_minor"
    assert plan.net_profit_minor == plan.revenue_minor - plan.cost_total_minor, (
        "GOLD-010 §4.7: profit reconstructs"
    )

    # not a section 4 item: the warning flags every golden plan carries
    assert {"LOADING_ORDER_NOT_MODELLED", "SERVICE_TIME_DEFAULTED"} <= set(plan.warnings), (
        "GOLD-010: warning flags"
    )

    # 8: validator and determinism (invariant 8)
    assert RouteValidator().validate(source, plan).valid, (
        "GOLD-010 §4.8: RouteValidator accepts the plan"
    )
    assert repeatable, "GOLD-010 §4.8: a second run is identical"

    # 9: industrial pallets count 1.5 each; 8.0 equals pallet_places and is allowed
    assert stops[0].load_pallet_eq_after == Decimal("6.0"), (
        "GOLD-010 §4.9: after PICKUP P the load is 6.0 equivalents"
    )
    assert stops[1].load_pallet_eq_after == vehicle.pallet_places == 8, (
        "GOLD-010 §4.9: after PICKUP R exactly 8.0 = pallet_places"
    )

    # 10: P and Q are never together: 9.0 > 8 although the pallet count is 7
    assert all(not {"P", "Q"} <= set(p.offer_ids) for p in ranked), (
        "GOLD-010 §4.10: no returned plan contains both P and Q"
    )
    counts = {o.id: o.pallet_count for o in source.offers}
    assert counts["P"] + counts["Q"] == 7 <= vehicle.pallet_places, (
        "GOLD-010 §4.10: the pallet count of P and Q is 7, within 8 places"
    )
    equivalents = {"P": Decimal("6.0"), "Q": Decimal("3.0")}
    assert sum(equivalents.values()) == Decimal("9.0") > vehicle.pallet_places, (
        "GOLD-010 §4.10: 6.0 + 3.0 = 9.0 equivalents exceed 8 places"
    )
    # The spec text names the cause PALLET_CAPACITY_EXCEEDED; the schedule builder reports every
    # capacity failure of a sequence as CAPACITY_EXCEEDED. Reported to the owner.
    together, failure = build_plan(
        source,
        source.drivers[0],
        _actions(["PICKUP P", "PICKUP Q", "DELIVERY P", "DELIVERY Q"]),
        thresholds=False,
    )
    assert together is None and failure == "CAPACITY_EXCEEDED", (
        "GOLD-010 §4.10: P and Q together are infeasible on pallet equivalents"
    )

    # 11: rank order of the offer sets and their profits
    assert [p.offer_ids for p in ranked] == [["P", "R"], ["Q", "R"], ["P"], ["Q"], ["R"]], (
        "GOLD-010 §4.11: {P, R} > {Q, R} > {P} > {Q} > {R}"
    )
    assert [p.net_profit_minor for p in ranked] == [19642, 13693, 11142, 5192, 242], (
        "GOLD-010 §4.11: 196.42, 136.93, 111.42, 51.92, 2.42"
    )

    # 12: the layout template EUR_MIXED_5X3 is display-only (ADR-0014); the engine has no layout
    # input, so the capacity check above (equivalents) is the only thing a test can show here.


def _actions(labels: list[str]) -> list[Action]:
    return [Action(kind=label.split()[0], offer_id=label.split()[1]) for label in labels]
