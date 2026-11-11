"""Versioned simplified working-time profiles from approved FEAT-003 FR-1-9."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from routepilot.compliance.models import (
    DriverState,
    Infeasible,
    Ok,
    Outcome,
    ProfileId,
    Remaining,
    RuleActivity,
    minutes_between,
)


def choose_profile(home_country: str, countries: list[str | None]) -> ProfileId:
    if any(country is None or country != home_country for country in countries):
        return "eu561_van_international_v1"
    return "pl_domestic_employee_v1"


def next_week_boundary(s: DriverState) -> datetime:
    zone = ZoneInfo(s.home_timezone)
    local = s.t.astimezone(zone)
    monday = local.date() + timedelta(days=7 - local.weekday())
    return datetime.combine(monday, time.min, zone).astimezone(UTC)


def advance_clock(s: DriverState, minutes: int, *, work: bool, driving: bool) -> DriverState:
    """Charge each minute to its home-zone week, including a boundary within an activity."""
    end = s.t + timedelta(minutes=minutes)
    current = s
    while current.t < end:
        boundary = next_week_boundary(current)
        until = min(end, boundary)
        duration = minutes_between(current.t, until)
        updates = {
            "t": until,
            "work_today": current.work_today + (duration if work else 0),
            "drive_today": current.drive_today + (duration if driving else 0),
            "work_since_break": current.work_since_break + (duration if work else 0),
            "drive_since_break": current.drive_since_break + (duration if driving else 0),
            "work_week": current.work_week + (duration if work else 0),
            "drive_week": current.drive_week + (duration if driving else 0),
        }
        current = current.model_copy(update=updates)
        if until == boundary:
            current = current.model_copy(
                update={"drive_prev_week": current.drive_week, "drive_week": 0, "work_week": 0}
            )
    return current


class PlDomesticRules:
    profile_id: ProfileId = "pl_domestic_employee_v1"
    international = False

    def __init__(self, max_daily_work_min: int = 720) -> None:
        self.max_daily_work_min = max_daily_work_min

    def remaining(self, s: DriverState) -> Remaining:
        span = 780 - minutes_between(s.day_start_at, s.t) if s.day_start_at else 780
        return Remaining(
            work_break_min=max(0, 360 - s.work_since_break),
            drive_break_min=max(0, 270 - s.drive_since_break) if self.international else None,
            daily_work_min=None
            if self.international
            else max(0, self.max_daily_work_min - s.work_today),
            daily_drive_min=max(0, 540 - s.drive_today) if self.international else None,
            span_min=max(0, span),
            weekly_work_min=max(0, 3600 - s.work_week),
            weekly_drive_min=max(0, 3360 - s.drive_week) if self.international else None,
            two_week_drive_min=max(0, 5400 - s.drive_week - s.drive_prev_week)
            if self.international
            else None,
        )

    def _break_length(self, s: DriverState) -> int:
        if self.international:
            return 45
        if s.work_since_break >= 360:
            return max(30, 45 - s.breaks_today) if s.work_today >= 540 else 30
        return max(0, 45 - s.breaks_today) if s.work_today >= 540 else 0

    def _pause(self, s: DriverState, length: int, rest: bool) -> tuple[DriverState, RuleActivity]:
        event = RuleActivity(
            kind="DAILY_REST" if rest else "BREAK",
            start_at=s.t,
            end_at=s.t + timedelta(minutes=length),
            reason="DAILY_LIMIT_REACHED" if rest else "BREAK_LIMIT_REACHED",
        )
        state = advance_clock(s, length, work=False, driving=False)
        if rest:
            state = state.model_copy(
                update={
                    "work_today": 0,
                    "drive_today": 0,
                    "work_since_break": 0,
                    "drive_since_break": 0,
                    "breaks_today": 0,
                    "day_start_at": None,
                }
            )
        else:
            state = state.model_copy(
                update={
                    "breaks_today": state.breaks_today + length,
                    "work_since_break": 0 if length >= 30 else state.work_since_break,
                    "drive_since_break": 0 if self.international else state.drive_since_break,
                }
            )
        return state, event

    def _active(self, s: DriverState) -> DriverState:
        return s if s.day_start_at is not None else s.model_copy(update={"day_start_at": s.t})

    def _weekly_failure(self, s: DriverState, driving: bool) -> bool:
        if s.work_week >= 3600:
            return True
        return (
            driving
            and self.international
            and (s.drive_week >= 3360 or s.drive_week + s.drive_prev_week >= 5400)
        )

    def _daily_due(self, s: DriverState, driving: bool) -> bool:
        r = self.remaining(s)
        return r.span_min == 0 or r.daily_work_min == 0 or (driving and r.daily_drive_min == 0)

    def advance_drive(self, s: DriverState, minutes: int) -> Outcome:
        return self._splittable(s, minutes, driving=True, wait=False)

    def advance_wait(self, s: DriverState, minutes: int) -> Outcome:
        if minutes < 0:
            return Infeasible(code="INVALID_ACTIVITY")
        if minutes >= 660:
            state, event = self._pause(s, minutes, True)
            return Ok(state=state, elapsed_min=minutes, events=[event], activities=[event])
        return self._splittable(s, minutes, driving=False, wait=True)

    def _splittable(self, s: DriverState, minutes: int, *, driving: bool, wait: bool) -> Outcome:
        if minutes < 0:
            return Infeasible(code="INVALID_ACTIVITY")
        state, remaining = s, minutes
        activities: list[RuleActivity] = []
        events: list[RuleActivity] = []
        wait_end = s.t + timedelta(minutes=minutes)
        while remaining > 0:
            state = self._active(state)
            if self._weekly_failure(state, driving):
                return Infeasible(code="WEEKLY_LIMIT_REACHED")
            if self._daily_due(state, driving):
                state, event = self._pause(state, 660, True)
                events.append(event)
                activities.append(event)
                if wait:
                    remaining = max(0, minutes_between(state.t, wait_end))
                continue
            r = self.remaining(state)
            limits = [
                r.work_break_min,
                r.span_min,
                r.weekly_work_min,
                minutes_between(state.t, next_week_boundary(state)),
            ]
            if not self.international:
                limits.append(r.daily_work_min or 0)
                if state.breaks_today < 45:
                    limits.append(max(0, 540 - state.work_today))
            if driving and self.international:
                limits.extend(
                    value
                    for value in (
                        r.drive_break_min,
                        r.daily_drive_min,
                        r.weekly_drive_min,
                        r.two_week_drive_min,
                    )
                    if value is not None
                )
            step = min(remaining, *limits)
            if step == 0:
                length = self._break_length(state)
                if not length:
                    return Infeasible(code="INVALID_ACTIVITY")
                state, event = self._pause(
                    state,
                    660 if length > self.remaining(state).span_min else length,
                    length > self.remaining(state).span_min,
                )
                events.append(event)
                activities.append(event)
                if wait:
                    remaining = max(0, minutes_between(state.t, wait_end))
                continue
            start = state.t
            state = advance_clock(state, step, work=True, driving=driving)
            activities.append(
                RuleActivity(kind="DRIVE" if driving else "WAIT", start_at=start, end_at=state.t)
            )
            remaining -= step
        return Ok(
            state=state,
            elapsed_min=minutes_between(s.t, state.t),
            events=events,
            activities=activities,
        )

    def advance_work(self, s: DriverState, minutes: int) -> Outcome:
        if minutes < 0 or minutes > 360:
            return Infeasible(code="INVALID_ACTIVITY")
        if minutes == 0:
            return Ok(state=s, elapsed_min=0)
        state = self._active(s)
        in_week = min(minutes, minutes_between(state.t, next_week_boundary(state)))
        if state.work_week + in_week > 3600:
            return Infeasible(code="WEEKLY_LIMIT_REACHED")
        events: list[RuleActivity] = []
        if (not self.international and state.work_today + minutes > self.max_daily_work_min) or (
            self.remaining(state).span_min < minutes
        ):
            state, event = self._pause(state, 660, True)
            events.append(event)
            state = self._active(state)
        if state.work_since_break + minutes > 360:
            length = (
                45
                if self.international
                else (max(30, 45 - state.breaks_today) if state.work_today + minutes > 540 else 30)
            )
            rest = length + minutes > self.remaining(state).span_min
            state, event = self._pause(state, 660 if rest else length, rest)
            events.append(event)
            state = self._active(state)
        elif (
            not self.international
            and state.breaks_today < 45
            and (state.work_today >= 540 or state.work_today < 540 < state.work_today + minutes)
        ):
            length = 45 - state.breaks_today
            rest = length + minutes > self.remaining(state).span_min
            state, event = self._pause(state, 660 if rest else length, rest)
            events.append(event)
            state = self._active(state)
        # A preceding break can itself leave too little duty span for atomic service.
        if self.remaining(state).span_min < minutes:
            state, event = self._pause(state, 660, True)
            events.append(event)
            state = self._active(state)
        start = state.t
        state = advance_clock(state, minutes, work=True, driving=False)
        work = RuleActivity(kind="WORK", start_at=start, end_at=state.t)
        return Ok(
            state=state,
            elapsed_min=minutes_between(s.t, state.t),
            events=events,
            activities=[*events, work],
        )


class Eu561Rules(PlDomesticRules):
    profile_id: ProfileId = "eu561_van_international_v1"
    international = True


def rules_for_profile(profile: ProfileId, max_daily_work_min: int = 720) -> PlDomesticRules:
    return (
        Eu561Rules(max_daily_work_min)
        if profile == "eu561_van_international_v1"
        else (PlDomesticRules(max_daily_work_min))
    )
