"""Public PL domestic implementation of the DriverRules port."""

from routepilot.compliance.rules import PlDomesticRules as _LegacyPlDomesticRules
from routepilot.compliance.state import (
    DriverState,
    Outcome,
    ProfileId,
    Remaining,
    _from_legacy_outcome,
    _from_legacy_remaining,
    _to_legacy_state,
)


class PlDomesticEmployeeRules:
    """The versioned ``pl_domestic_employee_v1`` planning profile."""

    profile_id: ProfileId = "pl_domestic_employee_v1"

    def __init__(self, max_daily_work_min: int = 720) -> None:
        self._delegate = _LegacyPlDomesticRules(max_daily_work_min)

    def advance_drive(self, s: DriverState, minutes: int) -> Outcome:
        return _from_legacy_outcome(self._delegate.advance_drive(_to_legacy_state(s), minutes))

    def advance_work(self, s: DriverState, minutes: int) -> Outcome:
        return _from_legacy_outcome(self._delegate.advance_work(_to_legacy_state(s), minutes))

    def advance_wait(self, s: DriverState, minutes: int) -> Outcome:
        return _from_legacy_outcome(self._delegate.advance_wait(_to_legacy_state(s), minutes))

    def remaining(self, s: DriverState) -> Remaining:
        return _from_legacy_remaining(self._delegate.remaining(_to_legacy_state(s)))


__all__ = ["PlDomesticEmployeeRules"]
