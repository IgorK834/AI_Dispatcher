"""Public international van implementation of the DriverRules port."""

from routepilot.compliance.pl_domestic import PlDomesticEmployeeRules
from routepilot.compliance.rules import Eu561Rules as _LegacyEu561Rules
from routepilot.compliance.state import ProfileId


class Eu561VanInternationalRules(PlDomesticEmployeeRules):
    """The versioned ``eu561_van_international_v1`` planning profile."""

    profile_id: ProfileId = "eu561_van_international_v1"

    def __init__(self, max_daily_work_min: int = 720) -> None:
        self._delegate = _LegacyEu561Rules(max_daily_work_min)


__all__ = ["Eu561VanInternationalRules"]
