"""Independent route validation for AC-FEAT-003-25."""

import pytest

from routepilot.optimization.engine.validators import RouteValidator
from tests.fixtures.engine.plan_mutators import route_mutations, valid_international_plan


@pytest.mark.ac("AC-FEAT-003-25")
def test_valid_hand_built_plan_passes() -> None:
    snapshot, plan = valid_international_plan()
    report = RouteValidator().validate(snapshot, plan)
    assert report.ok
    assert report.valid
    assert report.violations == ()
    assert report.errors == []


@pytest.mark.ac("AC-FEAT-003-25")
def test_each_invariant_mutation_has_a_distinct_error() -> None:
    snapshot, plan = valid_international_plan()
    observed: set[str] = set()
    for name, mutated, code, invariant in route_mutations(plan):
        report = RouteValidator().validate(snapshot, mutated)
        assert not report.ok, name
        assert any(
            violation.code == code and violation.invariant == invariant
            for violation in report.violations
        ), name
        observed.add(code)
    assert len(observed) == 8
