"""Deterministic whole-plan working-time profile selection."""

from routepilot.compliance.eu561 import Eu561VanInternationalRules
from routepilot.compliance.pl_domestic import PlDomesticEmployeeRules
from routepilot.compliance.ports import DriverRules


def choose_profile(countries: set[str] | None, home_country: str) -> DriverRules:
    """Return PL only when every resolved plan point is in the home country."""
    if countries == {home_country}:
        return PlDomesticEmployeeRules()
    return Eu561VanInternationalRules()


__all__ = ["choose_profile"]
