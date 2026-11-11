"""Hand-checkable cost calculations from GOLD-009 and FEAT-003 FR-10-14."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from routepilot.compliance.models import DriverState, RuleActivity
from routepilot.optimization.engine.costs import CostModel, revenue_in_profile_currency, speed_curve
from routepilot.optimization.engine.models import (
    CostProfile,
    DriverSnapshot,
    OfferSnapshot,
    PlanActivity,
    PlanLeg,
    Point,
    Stop,
    VehicleSnapshot,
)

T = datetime(2026, 11, 16, 7, tzinfo=UTC)


@pytest.mark.ac("AC-FEAT-003-20")
def test_speed_interpolation_fuel_and_co2() -> None:
    assert speed_curve(Decimal("60")) == Decimal("1.025")
    assert speed_curve(Decimal("40")) == Decimal("1.10")
    assert speed_curve(Decimal("140")) == Decimal("1.35")
    model = CostModel()
    vehicle = VehicleSnapshot()
    assert model.leg_fuel(vehicle, Decimal("100"), 100, 800) > model.leg_fuel(
        vehicle, Decimal("100"), 100, 200
    )
    assert model.leg_fuel(vehicle, Decimal("100"), 0, 800) == 0
    assert model.co2(Decimal("76.601")) == Decimal("199.16")


@pytest.mark.ac("AC-FEAT-003-19")
def test_gold009_costs_and_parameter_provenance() -> None:
    kat = Point(key="Katowice", country="PL")
    opole = Point(key="Opole", country="PL")
    driver = DriverSnapshot(
        id="D1",
        home=kat,
        position=kat,
        available_from=T,
        vehicle=VehicleSnapshot(),
        cost_profile=CostProfile(),
        rules_state=DriverState(t=T),
    )
    stop = Stop(point=kat, window_start=T, window_end=T + timedelta(hours=8), service_min=30)
    offer = OfferSnapshot(
        id="Y",
        weight_kg=800,
        pallet_count=6,
        revenue_minor=19000,
        stops=(stop, stop.model_copy(update={"point": opole})),
    )
    finish = T + timedelta(minutes=173)
    leg = PlanLeg(
        start=kat,
        end=opole,
        distance_km=Decimal("112.98"),
        drive_min=113,
        load_kg=800,
        load_pallet_eq=Decimal("6"),
        departed_at=T + timedelta(minutes=30),
        arrived_at=T + timedelta(minutes=143),
    )
    activities = [
        PlanActivity(
            activity=RuleActivity(kind="WORK", start_at=T, end_at=T + timedelta(minutes=30)),
            point_key=kat.key,
        ),
        PlanActivity(
            activity=RuleActivity(kind="DRIVE", start_at=leg.departed_at, end_at=leg.arrived_at),
            leg_index=0,
        ),
        PlanActivity(
            activity=RuleActivity(kind="WORK", start_at=leg.arrived_at, end_at=finish),
            point_key=opole.key,
        ),
    ]
    result = CostModel().calculate(driver, [offer], [leg], activities, T, finish)
    assert result.fuel_l == Decimal("14.447")
    assert result.co2_kg == Decimal("37.56")
    assert result.calculation.fuel == 2615 and result.calculation.driver == 4037
    assert result.calculation.vehicle == 1356 and result.calculation.total == 8008
    assert result.net_profit_minor == 10992
    changed = driver.model_copy(
        update={
            "cost_profile": driver.cost_profile.model_copy(
                update={"driver_cost_minor_per_hour": 1500}
            )
        }
    )
    again = CostModel().calculate(changed, [offer], [leg], activities, T, finish)
    assert again.calculation.driver != result.calculation.driver
    assert again.calculation.fuel == result.calculation.fuel


@pytest.mark.ac("AC-FEAT-003-19")
def test_domestic_per_diem_foreign_exemption_and_currency_conversion() -> None:
    model = CostModel()
    assert model.per_diem_multiplier(479) == 0
    assert model.per_diem_multiplier(480) == Decimal("0.5")
    assert model.per_diem_multiplier(720) == Decimal("0.5")
    assert model.per_diem_multiplier(721) == 1
    assert model.per_diem_multiplier(1440) == 1
    assert model.per_diem_multiplier(1441) == Decimal("1.5")
    assert model.per_diem_multiplier(1921) == 2
    assert revenue_in_profile_currency(42500, "PLN", CostProfile(fx_rates={"PLN": "4.25"})) == 10000
