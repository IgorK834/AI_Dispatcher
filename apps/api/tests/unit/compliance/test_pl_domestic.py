"""AC-FEAT-003-15 examples for the simplified PL profile."""

from datetime import timedelta

import pytest

from routepilot.compliance.pl_domestic import PlDomesticEmployeeRules
from routepilot.compliance.state import Ok
from tests.factories_rules import RULES_START, rules_state


@pytest.mark.ac("AC-FEAT-003-15")
def test_pl_break_top_up_and_daily_rest() -> None:
    rules = PlDomesticEmployeeRules()
    service = rules.advance_work(rules_state(), 30)
    assert isinstance(service, Ok)

    drive = rules.advance_drive(service.state, 568)
    assert isinstance(drive, Ok)
    assert isinstance(drive.events, tuple)
    assert [(event.kind, event.minutes) for event in drive.events] == [
        ("BREAK", 30),
        ("BREAK", 15),
    ]
    assert [event.start for event in drive.events] == [
        RULES_START + timedelta(minutes=360),
        RULES_START + timedelta(minutes=570),
    ]
    assert drive.elapsed_min == 613
    assert drive.state.work_today == 598

    to_limit = rules.advance_drive(drive.state, 122)
    assert isinstance(to_limit, Ok)
    assert to_limit.state.work_today == 720

    next_minute = rules.advance_drive(to_limit.state, 1)
    assert isinstance(next_minute, Ok)
    assert [(event.kind, event.minutes) for event in next_minute.events] == [("DAILY_REST", 660)]
    assert next_minute.state.work_today == 1
    assert next_minute.state.drive_today == 1


@pytest.mark.ac("AC-FEAT-003-15")
def test_daily_rest_replaces_break_due_at_the_same_minute() -> None:
    outcome = PlDomesticEmployeeRules().advance_drive(
        rules_state(work_today=720, work_since_break=360), 1
    )
    assert isinstance(outcome, Ok)
    assert [event.kind for event in outcome.events] == ["DAILY_REST"]
