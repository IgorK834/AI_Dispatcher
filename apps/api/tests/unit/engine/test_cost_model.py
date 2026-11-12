"""AC-FEAT-003-19 GOLD-CP-1 component reconstruction."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from routepilot.compliance.models import DriverState, RuleActivity
from routepilot.optimization.engine.cost_model import CostModel, Timeline, VehicleSpec
from routepilot.optimization.engine.models import (
    DriverSnapshot,
    OfferSnapshot,
    PlanActivity,
    PlanLeg,
    Point,
    Stop,
)
from tests.fixtures.engine.gold_cp_1 import gold_cp_1

T = datetime(2026, 11, 16, 7, tzinfo=UTC)


def foreign_timeline() -> tuple[Timeline, VehicleSpec]:
    home = Point(key="HOME", city="Katowice", country="PL")
    destination = Point(key="FR-STOP", city="Strasbourg", country="FR")
    vehicle = VehicleSpec(payload_kg=1000, sleeper_cab=False)
    driver = DriverSnapshot(
        id="D1",
        home=home,
        position=home,
        available_from=T,
        vehicle=vehicle,
        cost_profile=gold_cp_1(),
        rules_state=DriverState(t=T),
    )
    pickup = Stop(point=home, window_start=T, window_end=T + timedelta(days=1))
    delivery = Stop(point=destination, window_start=T, window_end=T + timedelta(days=1))
    offer = OfferSnapshot(
        id="O1",
        weight_kg=500,
        pallet_count=3,
        revenue_minor=30000,
        stops=(pickup, delivery),
    )
    leg = PlanLeg(
        start=home,
        end=destination,
        distance_km=Decimal("100.00"),
        drive_min=100,
        load_kg=500,
        load_pallet_eq=Decimal("3"),
        departed_at=T,
        arrived_at=T + timedelta(minutes=100),
    )
    activities = (
        PlanActivity(
            activity=RuleActivity(kind="DRIVE", start_at=T, end_at=T + timedelta(minutes=100)),
            leg_index=0,
        ),
        PlanActivity(
            activity=RuleActivity(
                kind="WAIT",
                start_at=T + timedelta(minutes=100),
                end_at=T + timedelta(minutes=120),
            ),
            point_key=destination.key,
        ),
        PlanActivity(
            activity=RuleActivity(
                kind="WORK",
                start_at=T + timedelta(minutes=120),
                end_at=T + timedelta(minutes=150),
            ),
            point_key=destination.key,
        ),
        PlanActivity(
            activity=RuleActivity(
                kind="DAILY_REST",
                start_at=T + timedelta(minutes=150),
                end_at=T + timedelta(minutes=810),
            ),
            point_key=destination.key,
        ),
    )
    return (
        Timeline(
            driver=driver,
            offers=(offer,),
            legs=(leg,),
            activities=activities,
            departure_at=T,
            finish_at=T + timedelta(minutes=810),
        ),
        vehicle,
    )


@pytest.mark.ac("AC-FEAT-003-19")
def test_gold_cp_1_components_match_hand_calculation() -> None:
    timeline, vehicle = foreign_timeline()
    result = CostModel().breakdown(timeline, gold_cp_1(), vehicle)

    assert result.fuel_l == Decimal("12.300")
    assert result.co2_kg == Decimal("31.98")
    assert result.calculation.fuel == 2226
    assert result.calculation.toll == 1200
    assert result.calculation.driver == 3500
    assert result.calculation.per_diem == 0
    assert result.calculation.accommodation == 5500
    assert result.calculation.vehicle == 1200
    assert result.calculation.total == 13626
    assert result.net_profit_minor == 16374
    assert result.margin_pct == Decimal("54.58")
    assert result.calculation.parameters["driver_cost_minor_per_hour"]["provenance"] == (
        "assumption"
    )


@pytest.mark.ac("AC-FEAT-003-19")
def test_changing_driver_assumption_changes_only_driver_component() -> None:
    timeline, vehicle = foreign_timeline()
    baseline = CostModel().breakdown(timeline, gold_cp_1(), vehicle)
    changed_profile = gold_cp_1().model_copy(update={"driver_cost_minor_per_hour": 1500})
    changed = CostModel().breakdown(timeline, changed_profile, vehicle)

    assert changed.calculation.driver == 3750
    assert changed.calculation.driver != baseline.calculation.driver
    assert changed.calculation.fuel == baseline.calculation.fuel
    assert changed.calculation.toll == baseline.calculation.toll
    assert changed.calculation.per_diem == baseline.calculation.per_diem
    assert changed.calculation.accommodation == baseline.calculation.accommodation
    assert changed.calculation.vehicle == baseline.calculation.vehicle
