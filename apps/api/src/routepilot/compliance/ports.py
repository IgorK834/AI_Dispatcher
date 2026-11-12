"""The pure DriverRules port from FEAT-003."""

from typing import Protocol

from routepilot.compliance.state import DriverState, Outcome, ProfileId, Remaining


class DriverRules(Protocol):
    profile_id: ProfileId

    def advance_drive(self, s: DriverState, minutes: int) -> Outcome: ...

    def advance_work(self, s: DriverState, minutes: int) -> Outcome: ...

    def advance_wait(self, s: DriverState, minutes: int) -> Outcome: ...

    def remaining(self, s: DriverState) -> Remaining: ...
