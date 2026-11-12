"""AC-FEAT-003-16 examples for the simplified 561 profile."""

from datetime import timedelta

import pytest

from routepilot.compliance.eu561 import Eu561VanInternationalRules
from routepilot.compliance.state import Ok
from tests.factories_rules import RULES_START, rules_state


@pytest.mark.ac("AC-FEAT-003-16")
def test_561_break_after_270_driving_minutes() -> None:
    outcome = Eu561VanInternationalRules().advance_drive(rules_state(), 288)
    assert isinstance(outcome, Ok)
    assert [(event.kind, event.minutes) for event in outcome.events] == [("BREAK", 45)]
    assert outcome.events[0].start == RULES_START + timedelta(minutes=270)
    assert outcome.elapsed_min == 333


@pytest.mark.ac("AC-FEAT-003-16")
def test_561_break_then_daily_rest() -> None:
    outcome = Eu561VanInternationalRules().advance_drive(
        rules_state(drive_today=499, drive_since_break=259), 126
    )
    assert isinstance(outcome, Ok)
    assert [(event.kind, event.minutes) for event in outcome.events] == [
        ("BREAK", 45),
        ("DAILY_REST", 660),
    ]
    assert outcome.events[0].start == RULES_START + timedelta(minutes=11)
    assert outcome.events[1].start - outcome.events[0].end_at == timedelta(minutes=30)


@pytest.mark.ac("AC-FEAT-003-16")
def test_561_work_break_can_bind_before_driving_break() -> None:
    outcome = Eu561VanInternationalRules().advance_drive(rules_state(work_since_break=331), 60)
    assert isinstance(outcome, Ok)
    assert outcome.events[0].kind == "BREAK"
    assert outcome.events[0].start == RULES_START + timedelta(minutes=29)
