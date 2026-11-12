"""AC-FEAT-003-20 deterministic Decimal fuel and CO2 calculations."""

from decimal import Decimal

import pytest

from routepilot.optimization.engine.cost_model import VehicleSpec
from routepilot.optimization.engine.fuel import co2_kg, leg_fuel_l, speed_curve


@pytest.mark.ac("AC-FEAT-003-20")
def test_van_default_speed_curve() -> None:
    assert speed_curve("VAN_DEFAULT_V1", Decimal("60")) == Decimal("1.025")
    assert speed_curve("VAN_DEFAULT_V1", Decimal("40")) == Decimal("1.10")
    assert speed_curve("VAN_DEFAULT_V1", Decimal("140")) == Decimal("1.35")


@pytest.mark.ac("AC-FEAT-003-20")
def test_fuel_grows_with_load_and_zero_minute_leg_burns_none() -> None:
    vehicle = VehicleSpec(payload_kg=1000)
    light = leg_fuel_l(Decimal("100"), 100, 200, vehicle)
    heavy = leg_fuel_l(Decimal("100"), 100, 800, vehicle)
    assert heavy > light
    assert leg_fuel_l(Decimal("100"), 0, 800, vehicle) == Decimal("0.000")


@pytest.mark.ac("AC-FEAT-003-20")
def test_co2_rounds_half_up_once() -> None:
    assert co2_kg(Decimal("76.601"), Decimal("2.6")) == Decimal("199.16")
