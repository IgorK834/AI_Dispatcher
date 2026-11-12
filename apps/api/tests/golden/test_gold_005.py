"""Exact assertions from specs/golden/GOLD-005.md section 4."""

import pytest

from routepilot.optimization.engine import optimize

from .cases import at, case


@pytest.mark.ac("AC-FEAT-003-34")
def test_gold_005() -> None:
    source = case(5)
    result = optimize(source)
    assert all(not plans for plans in result.per_driver["D2"].values())
    assert [(r.offer_id, r.stage, r.code) for r in result.rejections] == [
        ("I", "search", "DELIVERY_WINDOW_MISSED")
    ]
    o = source.offers[0]
    control = source.model_copy(
        update={
            "offers": [
                o.model_copy(
                    update={
                        "stops": (
                            o.stops[0],
                            o.stops[1].model_copy(update={"window_end": at(0, 12, 3)}),
                        )
                    }
                )
            ]
        }
    )
    plan = optimize(control).per_driver["D2"]["profit"][0]
    assert plan.rules_profile == "eu561_van_international_v1"
    assert plan.stops[-1].service_start_at == at(0, 12, 3)
