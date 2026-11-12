"""Independent fleet validation for AC-FEAT-003-25."""

import pytest

from routepilot.optimization.engine.models import (
    FleetAssignment,
    FleetSolution,
    FleetTotals,
)
from routepilot.optimization.engine.validators import FleetValidator
from tests.fixtures.engine.plan_mutators import valid_international_plan


@pytest.mark.ac("AC-FEAT-003-25")
def test_duplicate_offer_or_driver_is_rejected_from_a_plan_mapping() -> None:
    snapshot, plan = valid_international_plan()
    solution = FleetSolution(
        objective="profit",
        assignments=[
            FleetAssignment(driver_id=plan.driver_id, plan_ref=plan.plan_ref),
            FleetAssignment(driver_id=plan.driver_id, plan_ref=plan.plan_ref),
        ],
        totals=FleetTotals(
            net_profit_minor=plan.net_profit_minor * 2,
            fuel_l=plan.fuel_l * 2,
            co2_kg=plan.co2_kg * 2,
            distance_km=plan.distance_km * 2,
            drivers_with_plan=2,
        ),
    )
    report = FleetValidator().validate(snapshot, solution, {plan.plan_ref: plan})
    assert not report.ok
    assert report.errors == ["DUPLICATED_ASSIGNMENT"]
    violation = report.violations[0]
    assert (violation.invariant, violation.code) == (12, "DUPLICATED_ASSIGNMENT")
    assert violation.message
