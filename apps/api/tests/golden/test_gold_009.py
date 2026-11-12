"""GOLD-009 (Fleet: one offer best for two drivers).

Every assertion of section 4 of specs/golden/GOLD-009.md, one assert per item.
"""

from decimal import Decimal

import pytest

from routepilot.optimization.engine import FleetValidator, RouteValidator
from routepilot.optimization.engine.fleet_oracle import brute_force_fleet

from .fixtures.gold_009 import build


@pytest.mark.ac("AC-FEAT-003-38")
def test_gold_009(run) -> None:
    source = build()
    result, repeatable = run(source)
    by_ref = {
        p.plan_ref: p
        for groups in result.per_driver.values()
        for group in groups.values()
        for p in group
    }
    by_ref.update({p.plan_ref: p for p in result.fleet_candidates})
    solution = result.fleet["profit"]
    chosen = {a.driver_id: by_ref[a.plan_ref] for a in solution.assignments}

    # 1: exact assignment D1 <- {Y}, D5 <- {X}
    assert {d: p.offer_ids for d, p in chosen.items()} == {"D1": ["Y"], "D5": ["X"]}, (
        "GOLD-009 §4.1: D1 gets {Y} and D5 gets {X}"
    )
    assert solution.totals.net_profit_minor == 21627, "GOLD-009 §4.1: fleet profit 216.27"

    # 2: no offer twice, no driver twice (invariant 12)
    offers = [oid for p in chosen.values() for oid in p.offer_ids]
    assert offers.count("X") == 1, "GOLD-009 §4.2: X appears in exactly one plan"
    assert len(offers) == len(set(offers)), "GOLD-009 §4.2: no offer is used twice"
    assert len(solution.assignments) == len({a.driver_id for a in solution.assignments}), (
        "GOLD-009 §4.2: each driver has at most one plan"
    )
    assert FleetValidator().validate(source, solution, list(by_ref.values())).valid, (
        "GOLD-009 §4.2: FleetValidator accepts the solution"
    )

    # 3: both baselines are 18811, the optimum is strictly greater (invariant 15)
    for name in ("baseline_single", "baseline_greedy"):
        assert result.baselines[name].totals.net_profit_minor == 18811, (
            f"GOLD-009 §4.3: {name} fleet profit is 188.11"
        )
        assert solution.totals.net_profit_minor > result.baselines[name].totals.net_profit_minor, (
            f"GOLD-009 §4.3: the optimum beats {name}"
        )

    # 4: per-plan values
    assert chosen["D1"].net_profit_minor == 10992, "GOLD-009 §4.4: D1 {Y} net_profit_minor"
    assert chosen["D1"].fuel_l == Decimal("14.447"), "GOLD-009 §4.4: D1 {Y} fuel_l"
    assert chosen["D1"].co2_kg == Decimal("37.56"), "GOLD-009 §4.4: D1 {Y} co2_kg"
    assert chosen["D5"].net_profit_minor == 10635, "GOLD-009 §4.4: D5 {X} net_profit_minor"
    assert chosen["D5"].fuel_l == Decimal("35.744"), "GOLD-009 §4.4: D5 {X} fuel_l"
    assert chosen["D5"].co2_kg == Decimal("92.93"), "GOLD-009 §4.4: D5 {X} co2_kg"
    assert chosen["D5"].empty_km == Decimal("86.61"), "GOLD-009 §4.4: D5 {X} empty_km"

    # 5: D5 rejects Y on mass (800 kg > 765 kg)
    assert ("Y", "OVERWEIGHT") in [
        (r.offer_id, r.code) for r in result.rejections if r.driver_id == "D5"
    ], "GOLD-009 §4.5: D5's rejection report contains Y with OVERWEIGHT"
    weights = {o.id: o.weight_kg for o in source.offers}
    assert weights["Y"] == 800 > source.drivers[1].vehicle.payload_kg == 765, (
        "GOLD-009 §4.5: 800 kg > 765 kg"
    )

    # 6: equal to the brute-force result over all combinations (P10)
    candidates = {
        driver_id: list(
            {
                p.plan_ref: p
                for p in [
                    *groups["profit"],
                    *(p for p in result.fleet_candidates if p.driver_id == driver_id),
                ]
            }.values()
        )
        for driver_id, groups in result.per_driver.items()
    }
    assert solution == brute_force_fleet(candidates, "profit", source.reference_time), (
        "GOLD-009 §4.6: the assignment equals the brute-force optimum"
    )

    # 7: both plans pass RouteValidator, and the result is deterministic (invariant 8)
    for driver_id, plan in chosen.items():
        assert RouteValidator().validate(source, plan).valid, (
            f"GOLD-009 §4.7: RouteValidator accepts the plan of {driver_id}"
        )
    assert repeatable, "GOLD-009 §4.7: a second run is identical"
