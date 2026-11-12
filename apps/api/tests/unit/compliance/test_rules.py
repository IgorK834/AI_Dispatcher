"""FEAT-003 FR-1-9 working-time examples (planning estimates, not legal certification)."""

from datetime import UTC, datetime, timedelta

import pytest

from routepilot.compliance.models import DriverState, Infeasible, Ok
from routepilot.compliance.rules import Eu561Rules, PlDomesticRules, choose_profile

T = datetime(2026, 11, 16, 7, tzinfo=UTC)


@pytest.mark.ac("AC-FEAT-003-14")
def test_profile_is_whole_plan_and_unknown_start_is_foreign() -> None:
    assert choose_profile("PL", ["PL", "PL"]) == "pl_domestic_employee_v1"
    assert choose_profile("PL", ["PL", "DE"]) == "eu561_van_international_v1"
    assert choose_profile("PL", ["CZ", "PL"]) == "eu561_van_international_v1"
    assert choose_profile("PL", [None, "PL"]) == "eu561_van_international_v1"


@pytest.mark.ac("AC-FEAT-003-15")
def test_pl_break_top_up_and_daily_rest() -> None:
    rules = PlDomesticRules()
    service = rules.advance_work(DriverState(t=T), 30)
    assert isinstance(service, Ok)
    drive = rules.advance_drive(service.state, 568)
    assert isinstance(drive, Ok)
    assert [e.minutes for e in drive.events] == [30, 15]
    assert [int((e.start_at - T).total_seconds() // 60) for e in drive.events] == [360, 570]
    assert drive.elapsed_min == 613 and drive.state.work_today == 598
    remainder = rules.advance_drive(drive.state, 122)
    assert isinstance(remainder, Ok) and remainder.state.work_today == 720
    next_day = rules.advance_drive(remainder.state, 1)
    assert isinstance(next_day, Ok)
    assert [e.kind for e in next_day.events] == ["DAILY_REST"]
    assert next_day.events[0].minutes == 660 and next_day.state.work_today == 1


@pytest.mark.ac("AC-FEAT-003-16")
def test_eu_breaks_daily_driving_and_work_break() -> None:
    rules = Eu561Rules()
    result = rules.advance_drive(DriverState(t=T), 288)
    assert isinstance(result, Ok)
    assert [e.minutes for e in result.events] == [45] and result.elapsed_min == 333
    state = DriverState(t=T, drive_today=499, drive_since_break=259)
    result = rules.advance_drive(state, 126)
    assert isinstance(result, Ok)
    assert [e.kind for e in result.events] == ["BREAK", "DAILY_REST"]
    assert result.events[0].start_at == T + timedelta(minutes=11)
    assert result.events[1].start_at == T + timedelta(minutes=86)
    result = rules.advance_drive(DriverState(t=T, work_since_break=331), 60)
    assert isinstance(result, Ok) and result.events[0].start_at == T + timedelta(minutes=29)


@pytest.mark.ac("AC-FEAT-003-17")
@pytest.mark.parametrize("rules", [PlDomesticRules(), Eu561Rules()])
def test_weekly_limits_and_base_timezone_rollover(rules: PlDomesticRules) -> None:
    assert rules.advance_drive(DriverState(t=T, work_week=3590), 30) == Infeasible(
        code="WEEKLY_LIMIT_REACHED"
    )
    before_monday = datetime(2026, 11, 15, 22, 50, tzinfo=UTC)
    result = rules.advance_drive(DriverState(t=before_monday, work_week=100, drive_week=80), 20)
    assert isinstance(result, Ok)
    assert result.state.drive_prev_week == 90
    assert result.state.work_week == 10 and result.state.drive_week == 10


@pytest.mark.ac("AC-FEAT-003-17")
def test_eu_two_week_limit() -> None:
    outcome = Eu561Rules().advance_drive(
        DriverState(t=T, drive_week=3000, drive_prev_week=2390), 30
    )
    assert outcome == Infeasible(code="WEEKLY_LIMIT_REACHED")


@pytest.mark.ac("AC-FEAT-003-18")
def test_atomic_service_and_wait_semantics() -> None:
    rules = PlDomesticRules()
    service = rules.advance_work(DriverState(t=T, work_since_break=350), 30)
    assert isinstance(service, Ok)
    assert service.events[0].start_at == T and service.events[0].minutes == 30
    assert service.activities[-1].kind == "WORK" and service.activities[-1].minutes == 30
    long_wait = rules.advance_wait(DriverState(t=T), 700)
    assert isinstance(long_wait, Ok)
    assert len(long_wait.events) == 1 and long_wait.events[0].minutes == 700
    assert long_wait.state.work_today == 0
    wait = rules.advance_wait(DriverState(t=T), 120)
    assert isinstance(wait, Ok) and wait.state.work_today == 120
    assert wait.elapsed_min == 120


@pytest.mark.ac("AC-FEAT-003-18")
def test_atomic_service_rest_and_wait_extension() -> None:
    from routepilot.compliance.ports import DriverRules

    rules: DriverRules = PlDomesticRules()
    for operation in (rules.advance_work, rules.advance_wait, rules.advance_drive):
        assert operation(DriverState(t=T), -1) == Infeasible(code="INVALID_ACTIVITY")
    assert rules.advance_work(DriverState(t=T), 361) == Infeasible(code="INVALID_ACTIVITY")
    assert rules.advance_work(DriverState(t=T), 0).state.t == T
    daily = rules.advance_work(DriverState(t=T, work_today=710), 30)
    assert isinstance(daily, Ok)
    assert daily.events[0].kind == "DAILY_REST"
    assert daily.state.work_today == 30
    # Only 10 minutes of the full 30-minute break overlap the remaining nominal wait.
    waiting = rules.advance_wait(DriverState(t=T, work_since_break=350), 20)
    assert isinstance(waiting, Ok)
    assert waiting.elapsed_min == 40
    assert waiting.state.work_today == 10
    span = rules.advance_drive(
        DriverState(t=T, work_since_break=360, day_start_at=T - timedelta(minutes=770)), 1
    )
    assert isinstance(span, Ok)
    assert span.events[0].kind == "DAILY_REST"


@pytest.mark.ac("AC-FEAT-003-18")
def test_top_up_precedes_atomic_service_crossing_nine_hours() -> None:
    state = DriverState(t=T, work_today=530, work_since_break=170, breaks_today=30)
    outcome = PlDomesticRules().advance_work(state, 30)
    assert isinstance(outcome, Ok)
    assert [(e.kind, e.minutes) for e in outcome.events] == [("BREAK", 15)]
    assert outcome.activities[-1].kind == "WORK"
    assert outcome.state.work_today == 560
