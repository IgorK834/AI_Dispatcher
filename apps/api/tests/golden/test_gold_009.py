"""Exact assertions from specs/golden/GOLD-009.md section 4."""

from decimal import Decimal

import pytest

from routepilot.optimization.engine import optimize

from .cases import case


@pytest.mark.ac("AC-FEAT-003-38")
def test_gold_009() -> None:
    source = case(9)
    result = optimize(source)
    plans = {
        p.plan_ref: p
        for by_obj in result.per_driver.values()
        for group in by_obj.values()
        for p in group
    }
    chosen = {a.driver_id: plans[a.plan_ref] for a in result.fleet["profit"].assignments}
    assert {d: p.offer_ids for d, p in chosen.items()} == {"D1": ["Y"], "D5": ["X"]}
    assert result.fleet["profit"].totals.net_profit_minor == 21627
    assert all(b.totals.net_profit_minor == 18811 for b in result.baselines.values())
    assert (chosen["D1"].net_profit_minor, chosen["D1"].fuel_l, chosen["D1"].co2_kg) == (
        10992,
        Decimal("14.447"),
        Decimal("37.56"),
    )
    assert (
        chosen["D5"].net_profit_minor,
        chosen["D5"].fuel_l,
        chosen["D5"].co2_kg,
        chosen["D5"].empty_km,
    ) == (10635, Decimal("35.744"), Decimal("92.93"), Decimal("86.61"))
    assert [(r.offer_id, r.code) for r in result.rejections if r.driver_id == "D5"] == [
        ("Y", "OVERWEIGHT")
    ]
    assert optimize(source) == result
