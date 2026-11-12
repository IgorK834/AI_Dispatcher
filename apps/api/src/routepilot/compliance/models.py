"""Pure working-time state and inserted activity records (FEAT-003 FR-1-9)."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

ProfileId = Literal["pl_domestic_employee_v1", "eu561_van_international_v1"]


class RulesModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DriverState(RulesModel):
    t: AwareDatetime
    work_today: int = Field(default=0, ge=0)
    drive_today: int = Field(default=0, ge=0)
    work_since_break: int = Field(default=0, ge=0)
    drive_since_break: int = Field(default=0, ge=0)
    breaks_today: int = Field(default=0, ge=0)
    work_week: int = Field(default=0, ge=0)
    drive_week: int = Field(default=0, ge=0)
    drive_prev_week: int = Field(default=0, ge=0)
    day_start_at: AwareDatetime | None = None
    sleeper_cab: bool = False
    home_timezone: str = "Europe/Warsaw"


class RuleActivity(RulesModel):
    kind: Literal["DRIVE", "WORK", "WAIT", "BREAK", "DAILY_REST"]
    start_at: AwareDatetime
    end_at: AwareDatetime
    reason: str = ""

    @property
    def minutes(self) -> int:
        return int((self.end_at - self.start_at).total_seconds() // 60)


class Ok(RulesModel):
    state: DriverState
    elapsed_min: int
    events: list[RuleActivity] = Field(default_factory=list)
    activities: list[RuleActivity] = Field(default_factory=list)


class Infeasible(RulesModel):
    code: Literal["WEEKLY_LIMIT_REACHED", "DAILY_LIMIT_REACHED", "INVALID_ACTIVITY"]


class Remaining(RulesModel):
    work_break_min: int
    drive_break_min: int | None
    daily_work_min: int | None
    daily_drive_min: int | None
    span_min: int
    weekly_work_min: int
    weekly_drive_min: int | None
    two_week_drive_min: int | None


Outcome = Ok | Infeasible


def minutes_between(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)
