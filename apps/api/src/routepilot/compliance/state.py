"""Immutable value objects for the public FEAT-003 DriverRules port."""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Literal, cast

from routepilot.compliance.models import DriverState as _LegacyDriverState
from routepilot.compliance.models import Infeasible as _LegacyInfeasible
from routepilot.compliance.models import Outcome as _LegacyOutcome
from routepilot.compliance.models import Remaining as _LegacyRemaining
from routepilot.compliance.models import RuleActivity as _LegacyRuleActivity

ProfileId = Literal["pl_domestic_employee_v1", "eu561_van_international_v1"]
RuleEventKind = Literal["BREAK", "DAILY_REST"]


@dataclass(frozen=True)
class DriverState:
    t: datetime
    work_today: int = 0
    drive_today: int = 0
    work_since_break: int = 0
    drive_since_break: int = 0
    breaks_today: int = 0
    work_week: int = 0
    drive_week: int = 0
    drive_prev_week: int = 0
    day_start_at: datetime | None = None
    sleeper_cab: bool = False
    home_timezone: str = "Europe/Warsaw"


@dataclass(frozen=True)
class RuleEvent:
    kind: RuleEventKind
    start: datetime
    length: int
    reason: str

    @property
    def minutes(self) -> int:
        return self.length

    @property
    def end_at(self) -> datetime:
        return self.start + timedelta(minutes=self.length)


@dataclass(frozen=True)
class Ok:
    state: DriverState
    elapsed_min: int
    events: tuple[RuleEvent, ...] = ()


@dataclass(frozen=True)
class Infeasible:
    code: str


@dataclass(frozen=True)
class Remaining:
    work_break_min: int
    drive_break_min: int | None
    daily_work_min: int | None
    daily_drive_min: int | None
    span_min: int
    weekly_work_min: int
    weekly_drive_min: int | None
    two_week_drive_min: int | None


type Outcome = Ok | Infeasible


def _to_legacy_state(state: DriverState) -> _LegacyDriverState:
    return _LegacyDriverState.model_validate(asdict(state))


def _from_legacy_state(state: _LegacyDriverState) -> DriverState:
    return DriverState(**state.model_dump())


def _from_legacy_event(event: _LegacyRuleActivity) -> RuleEvent:
    return RuleEvent(
        kind=cast(RuleEventKind, event.kind),
        start=event.start_at,
        length=event.minutes,
        reason=event.reason,
    )


def _from_legacy_outcome(outcome: _LegacyOutcome) -> Outcome:
    if isinstance(outcome, _LegacyInfeasible):
        return Infeasible(code=outcome.code)
    return Ok(
        state=_from_legacy_state(outcome.state),
        elapsed_min=outcome.elapsed_min,
        events=tuple(_from_legacy_event(event) for event in outcome.events),
    )


def _from_legacy_remaining(remaining: _LegacyRemaining) -> Remaining:
    return Remaining(**remaining.model_dump())


__all__ = [
    "DriverState",
    "Infeasible",
    "Ok",
    "Outcome",
    "ProfileId",
    "Remaining",
    "RuleEvent",
]
