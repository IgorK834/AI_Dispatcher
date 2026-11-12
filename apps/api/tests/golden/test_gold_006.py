"""Exact assertions from specs/golden/GOLD-006.md section 4 (API status belongs to FEAT-004)."""

import pytest

from routepilot.optimization.engine import FleetValidator, optimize

from .cases import case


@pytest.mark.ac("AC-FEAT-003-35")
def test_gold_006() -> None:
    source = case(6)
    result = optimize(source)
    assert all(not plans for plans in result.per_driver["D4"].values())
    assert not result.stats.truncated
    assert {r.offer_id: r.code for r in result.rejections} == dict(
        zip(
            [f"O{i}" for i in range(1, 9)],
            [
                "OVERWEIGHT",
                "MISSING_REVENUE",
                "FIRST_DEADHEAD_TOO_LONG",
                "PICKUP_WINDOW_UNREACHABLE",
                "BODY_TYPE_MISMATCH",
                "PALLET_CAPACITY_EXCEEDED",
                "MISSING_CAPACITY_DATA",
                "MISSING_COORDINATES",
            ],
            strict=True,
        )
    )
    assert result.rejections[2].stage == "search"
    assert not result.baseline_plans
    assert result.fleet["profit"].totals.net_profit_minor == 0
    assert FleetValidator().validate(source, result.fleet["profit"], []).valid
