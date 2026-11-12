"""AC-FEAT-003-18 atomic service and waiting semantics."""

import pytest

from routepilot.compliance.pl_domestic import PlDomesticEmployeeRules
from routepilot.compliance.state import Ok
from tests.factories_rules import RULES_START, rules_state


@pytest.mark.ac("AC-FEAT-003-18")
def test_break_precedes_atomic_service() -> None:
    outcome = PlDomesticEmployeeRules().advance_work(rules_state(work_since_break=350), 30)
    assert isinstance(outcome, Ok)
    assert [(event.kind, event.start, event.minutes) for event in outcome.events] == [
        ("BREAK", RULES_START, 30)
    ]
    assert outcome.elapsed_min == 60
    assert outcome.state.work_today == 30


@pytest.mark.ac("AC-FEAT-003-18")
def test_long_wait_is_one_daily_rest() -> None:
    outcome = PlDomesticEmployeeRules().advance_wait(rules_state(), 700)
    assert isinstance(outcome, Ok)
    assert [(event.kind, event.minutes) for event in outcome.events] == [("DAILY_REST", 700)]
    assert outcome.elapsed_min == 700
    assert outcome.state.work_today == 0


@pytest.mark.ac("AC-FEAT-003-18")
def test_short_wait_grows_all_work_counters() -> None:
    outcome = PlDomesticEmployeeRules().advance_wait(
        rules_state(work_today=10, work_since_break=20, work_week=30), 120
    )
    assert isinstance(outcome, Ok)
    assert outcome.state.work_today == 130
    assert outcome.state.work_since_break == 140
    assert outcome.state.work_week == 150
    assert outcome.state.drive_today == 0
    assert outcome.elapsed_min == 120
