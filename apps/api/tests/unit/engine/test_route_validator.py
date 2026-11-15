"""Independent route validation for AC-FEAT-003-25."""

import signal
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from routepilot.optimization.engine.models import EngineSnapshot, RoutePlan
from routepilot.optimization.engine.validators import RouteValidator
from tests.fixtures.engine.plan_mutators import T, route_mutations, valid_international_plan


def shifted(value: Any, delta: timedelta) -> Any:
    """The same structure with every timestamp moved by `delta`."""
    if isinstance(value, datetime):
        return value + delta
    if isinstance(value, dict):
        return {key: shifted(item, delta) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return type(value)(shifted(item, delta) for item in value)
    return value


@contextmanager
def finishes_within(seconds: int) -> Iterator[None]:
    """Fail instead of hanging when the code under test does not return."""

    def expired(signum: int, frame: Any) -> None:
        raise TimeoutError(f"no result after {seconds} s")

    previous = signal.signal(signal.SIGALRM, expired)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


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


@pytest.mark.ac("AC-FEAT-003-25")
@pytest.mark.parametrize("seconds_before", [30, 150])
def test_an_activity_that_reaches_the_week_boundary_between_two_minutes_is_validated(
    seconds_before: int,
) -> None:
    """The plan starts 30 s (or 2 min 30 s) before Monday 00:00 in the driver's zone, so a segment
    starts less than a minute before the boundary. The whole-minute step to the boundary was 0 and
    the validator looped for ever (it hung the offline evaluation at such a wall-clock time)."""
    snapshot, plan = valid_international_plan()
    boundary = datetime(2026, 11, 22, 23, tzinfo=UTC)  # Monday 2026-11-23 00:00 in Warsaw
    delta = boundary - timedelta(seconds=seconds_before) - T
    moved_snapshot = EngineSnapshot.model_validate(shifted(snapshot.model_dump(), delta))
    moved_plan = RoutePlan.model_validate(shifted(plan.model_dump(), delta))
    with finishes_within(20):
        report = RouteValidator().validate(moved_snapshot, moved_plan)
    # The fixture's recorded weekly counters know nothing of a new week, so the independent replay
    # (which resets them at the boundary) disagrees with them: a verdict, not a hang.
    assert report.errors == ["COUNTERS_INVALID"]
