"""Public Decimal-only fuel and CO2 functions from FEAT-003 FR-10/11."""

from decimal import Decimal

from routepilot.optimization.engine.costs import CostModel as _CostModel
from routepilot.optimization.engine.costs import speed_curve as _speed_curve
from routepilot.optimization.engine.models import VehicleSnapshot

DEFAULT_CO2_FACTOR_KG_PER_L = Decimal("2.6")  # assumption: FEAT-003 FR-11 default.


def speed_curve(name: str, v_kmh: Decimal) -> Decimal:
    if name != "VAN_DEFAULT_V1":
        raise ValueError(f"unsupported speed curve: {name}")
    return _speed_curve(v_kmh)


def leg_fuel_l(
    distance_km: Decimal,
    drive_min: int,
    load_kg: int,
    vehicle: VehicleSnapshot,
) -> Decimal:
    return _CostModel().leg_fuel(vehicle, distance_km, drive_min, load_kg)


def co2_kg(
    fuel_l: Decimal,
    factor_kg_per_l: Decimal = DEFAULT_CO2_FACTOR_KG_PER_L,
) -> Decimal:
    return _CostModel(factor_kg_per_l).co2(fuel_l)


__all__ = ["co2_kg", "leg_fuel_l", "speed_curve"]
