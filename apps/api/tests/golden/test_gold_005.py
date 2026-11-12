"""GOLD-005 (International: 45-minute break makes delivery late).

Every assertion of section 4 of specs/golden/GOLD-005.md, one assert per item.
"""

from datetime import timedelta

import pytest

from routepilot.compliance.models import DriverState, Ok
from routepilot.compliance.rules import choose_profile, rules_for_profile
from routepilot.optimization.engine import RouteValidator

from .fixtures.common import at
from .fixtures.gold_005 import build
from .helpers import plans, sequence


@pytest.mark.ac("AC-FEAT-003-34")
def test_gold_005(run) -> None:
    source = build()
    result, repeatable = run(source)
    offer = source.offers[0]

    # 1: no plan for D2 under any objective (invariant 9)
    for objective in ("profit", "fastest", "fuel"):
        assert plans(result, "D2", objective) == [], f"GOLD-005 §4.1: D2 has no {objective} plan"

    # 2: rejection report, with the earliest service start and the window end as detail
    assert [(r.driver_id, r.offer_id, r.stage, r.code) for r in result.rejections] == [
        ("D2", "I", "search", "DELIVERY_WINDOW_MISSED")
    ], "GOLD-005 §4.2: offer I is rejected in the search with DELIVERY_WINDOW_MISSED"
    assert result.rejections[0].detail == (
        "earliest service start 2026-11-16T11:03Z, window end 2026-11-16T10:45Z"
    ), "GOLD-005 §4.2: detail names 11:03Z against the window end 10:45Z"

    # 3: the evaluated candidate (control run below, same stops) uses the 561 profile (invariant 14)
    countries = [
        source.drivers[0].position.country,
        offer.stops[0].point.country,
        offer.stops[1].point.country,
    ]
    assert choose_profile("PL", countries) == "eu561_van_international_v1", (
        "GOLD-005 §4.3: Wroclaw -> Dresden selects the international profile"
    )

    # 4: DriverRules.advance_drive on a fresh state: one 45-minute BREAK after 270 min of driving
    start = at(0, 6, 0)
    outcome = rules_for_profile("eu561_van_international_v1").advance_drive(
        DriverState(t=start), 288
    )
    assert isinstance(outcome, Ok), "GOLD-005 §4.4: 288 minutes of driving are allowed"
    assert [(e.kind, e.start_at, e.minutes) for e in outcome.events] == [
        ("BREAK", start + timedelta(minutes=270), 45)
    ], "GOLD-005 §4.4: one BREAK of 45 min after 270 min of driving"
    assert outcome.elapsed_min == 333, "GOLD-005 §4.4: total elapsed 333 min"

    # 5: control run, only the delivery window end changed to Mon 12:03
    control = source.model_copy(
        update={
            "offers": [
                offer.model_copy(
                    update={
                        "stops": (
                            offer.stops[0],
                            offer.stops[1].model_copy(update={"window_end": at(0, 12, 3)}),
                        )
                    }
                )
            ]
        }
    )
    control_result, _ = run(control)
    control_plans = plans(control_result, "D2")
    assert len(control_plans) == 1, "GOLD-005 §4.5: exactly one plan"
    control_plan = control_plans[0]
    assert sequence(control_plan) == ["PICKUP I", "DELIVERY I"], (
        "GOLD-005 §4.5: PICKUP I, DELIVERY I"
    )
    assert control_plan.stops[-1].service_start_at == at(0, 12, 3), (
        "GOLD-005 §4.5: DELIVERY I service start 2026-11-16T11:03Z"
    )
    assert control_plan.rules_profile == "eu561_van_international_v1", (
        "GOLD-005 §4.3: the control plan uses the 561 profile"
    )
    assert RouteValidator().validate(control, control_plan).valid, (
        "GOLD-005 §4.5: the control plan is valid"
    )
    assert repeatable, "GOLD-005: a second run is identical"
