"""GOLD-006 (No feasible combination).

Every assertion of section 4 of specs/golden/GOLD-006.md, one assert per item. Item 5 (the API
job status) belongs to FEAT-004 and is not testable on the pure engine.
"""

import pytest

from routepilot.optimization.engine import FleetValidator

from .fixtures.gold_006 import build
from .helpers import plans


@pytest.mark.ac("AC-FEAT-003-35")
def test_gold_006(run) -> None:
    source = build()
    result, repeatable = run(source)

    # 1: no plan for any objective, search not truncated
    for objective in ("profit", "fastest", "fuel"):
        assert plans(result, "D4", objective) == [], f"GOLD-006 §4.1: no {objective} plan"
    assert result.stats.truncated is False, "GOLD-006 §4.1: truncated is false"

    # 2: exactly 8 rejections, one per offer, with the codes and stages of section 3
    assert [(r.offer_id, r.stage, r.code) for r in result.rejections] == [
        ("O1", "prefilter", "OVERWEIGHT"),
        ("O2", "prefilter", "MISSING_REVENUE"),
        ("O3", "search", "FIRST_DEADHEAD_TOO_LONG"),
        ("O4", "prefilter", "PICKUP_WINDOW_UNREACHABLE"),
        ("O5", "prefilter", "BODY_TYPE_MISMATCH"),
        ("O6", "prefilter", "PALLET_CAPACITY_EXCEEDED"),
        ("O7", "prefilter", "MISSING_CAPACITY_DATA"),
        ("O8", "prefilter", "MISSING_COORDINATES"),
    ], "GOLD-006 §4.2: eight rejections with the codes of the table"
    assert len({r.offer_id for r in result.rejections}) == len(source.offers) == 8, (
        "GOLD-006 §4.2: one entry per offer"
    )

    # 3: both baselines are empty and the fleet profit is 0
    assert not result.baseline_plans, "GOLD-006 §4.3: no baseline plan"
    for name in ("baseline_single", "baseline_greedy"):
        assert result.baselines[name].assignments == [], f"GOLD-006 §4.3: {name} is empty"
        assert result.baselines[name].totals.net_profit_minor == 0, (
            f"GOLD-006 §4.3: {name} profit is 0"
        )
    assert result.fleet["profit"].totals.net_profit_minor == 0, "GOLD-006 §4.3: fleet profit is 0"

    # 4: FleetValidator accepts the empty solution; no error is raised (invariant 9)
    assert FleetValidator().validate(source, result.fleet["profit"], []).valid, (
        "GOLD-006 §4.4: the empty fleet solution is valid"
    )
    assert repeatable, "GOLD-006: a second run is identical"
