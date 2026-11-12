"""AC-FEAT-003-17 weekly limits and home-zone week rollover."""

from datetime import UTC, datetime

import pytest

from routepilot.compliance.eu561 import Eu561VanInternationalRules
from routepilot.compliance.pl_domestic import PlDomesticEmployeeRules
from routepilot.compliance.state import Infeasible, Ok
from tests.factories_rules import rules_state


@pytest.mark.ac("AC-FEAT-003-17")
@pytest.mark.parametrize(
    "rules",
    [PlDomesticEmployeeRules(), Eu561VanInternationalRules()],
)
def test_weekly_work_limit_is_infeasible(rules: PlDomesticEmployeeRules) -> None:
    assert rules.advance_drive(rules_state(work_week=3590), 30) == Infeasible(
        code="WEEKLY_LIMIT_REACHED"
    )


@pytest.mark.ac("AC-FEAT-003-17")
def test_561_two_week_driving_limit_is_infeasible() -> None:
    assert Eu561VanInternationalRules().advance_drive(
        rules_state(drive_week=3000, drive_prev_week=2390), 30
    ) == Infeasible(code="WEEKLY_LIMIT_REACHED")


@pytest.mark.ac("AC-FEAT-003-17")
def test_monday_boundary_rolls_driving_and_resets_week() -> None:
    before_monday = datetime(2026, 11, 15, 22, 50, tzinfo=UTC)
    outcome = Eu561VanInternationalRules().advance_drive(
        rules_state(t=before_monday, work_week=100, drive_week=80), 20
    )
    assert isinstance(outcome, Ok)
    assert outcome.state.drive_prev_week == 90
    assert outcome.state.work_week == 10
    assert outcome.state.drive_week == 10
