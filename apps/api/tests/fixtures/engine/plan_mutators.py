"""Hand-built FEAT-003 validator fixture and AC-25 plan mutations."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from routepilot.compliance.models import DriverState, RuleActivity
from routepilot.optimization.engine.models import (
    Action,
    Calculation,
    CostProfile,
    DriverSnapshot,
    EngineSnapshot,
    OfferSnapshot,
    PlanActivity,
    PlanLeg,
    PlanStop,
    Point,
    RoutePlan,
    Stop,
    TravelMatrix,
    VehicleSnapshot,
)

T = datetime(2026, 11, 16, 5, tzinfo=UTC)


def _state(
    minutes: int,
    *,
    work_today: int = 0,
    drive_today: int = 0,
    work_since_break: int = 0,
    drive_since_break: int = 0,
    breaks_today: int = 0,
    work_week: int = 0,
    drive_week: int = 0,
    day_start_min: int | None = None,
) -> DriverState:
    return DriverState(
        t=T + timedelta(minutes=minutes),
        work_today=work_today,
        drive_today=drive_today,
        work_since_break=work_since_break,
        drive_since_break=drive_since_break,
        breaks_today=breaks_today,
        work_week=work_week,
        drive_week=drive_week,
        day_start_at=T + timedelta(minutes=day_start_min) if day_start_min is not None else None,
    )


def valid_international_plan() -> tuple[EngineSnapshot, RoutePlan]:
    home = Point(key="A", city="Katowice", country="PL", lat=50.2649, lon=19.0238)
    foreign = Point(key="B", city="Dresden", country="DE", lat=51.0504, lon=13.7373)
    vehicle = VehicleSnapshot(payload_kg=1000, pallet_places=8, sleeper_cab=False)
    profile = CostProfile()
    driver = DriverSnapshot(
        id="D1",
        home=home,
        position=home,
        available_from=T,
        home_by=T + timedelta(days=2),
        vehicle=vehicle,
        cost_profile=profile,
        rules_state=_state(0),
    )
    offer = OfferSnapshot(
        id="O1",
        weight_kg=100,
        pallet_count=1,
        revenue_minor=100000,
        stops=(
            Stop(point=home, window_start=T, window_end=T + timedelta(hours=1)),
            Stop(point=foreign, window_start=T, window_end=T + timedelta(days=1)),
        ),
    )
    matrix = TravelMatrix(
        points=[home, foreign],
        distance_km=[
            [Decimal("0.00"), Decimal("300.00")],
            [Decimal("300.00"), Decimal("0.00")],
        ],
        duration_min=[[0, 300], [300, 0]],
    )
    snapshot = EngineSnapshot(
        reference_time=T,
        drivers=[driver],
        offers=[offer],
        matrix=matrix,
    )
    pickup_state = _state(
        30,
        work_today=30,
        work_since_break=30,
        work_week=30,
        day_start_min=0,
    )
    break_state = _state(
        345,
        work_today=300,
        drive_today=270,
        breaks_today=45,
        work_week=300,
        drive_week=270,
        day_start_min=0,
    )
    delivery_state = _state(
        405,
        work_today=360,
        drive_today=300,
        work_since_break=60,
        drive_since_break=30,
        breaks_today=45,
        work_week=360,
        drive_week=300,
        day_start_min=0,
    )
    rest_state = _state(1305, work_week=600, drive_week=540)
    end_state = _state(
        1365,
        work_today=60,
        drive_today=60,
        work_since_break=60,
        drive_since_break=60,
        work_week=660,
        drive_week=600,
        day_start_min=1305,
    )
    activities = [
        PlanActivity(
            activity=RuleActivity(kind="WORK", start_at=T, end_at=T + timedelta(minutes=30)),
            point_key="A",
        ),
        PlanActivity(
            activity=RuleActivity(
                kind="DRIVE", start_at=T + timedelta(minutes=30), end_at=T + timedelta(minutes=300)
            ),
            leg_index=1,
        ),
        PlanActivity(
            activity=RuleActivity(
                kind="BREAK",
                start_at=T + timedelta(minutes=300),
                end_at=T + timedelta(minutes=345),
                reason="DRIVING_BREAK",
            ),
            point_key="B",
            leg_index=1,
        ),
        PlanActivity(
            activity=RuleActivity(
                kind="DRIVE", start_at=T + timedelta(minutes=345), end_at=T + timedelta(minutes=375)
            ),
            leg_index=1,
        ),
        PlanActivity(
            activity=RuleActivity(
                kind="WORK", start_at=T + timedelta(minutes=375), end_at=T + timedelta(minutes=405)
            ),
            point_key="B",
        ),
        PlanActivity(
            activity=RuleActivity(
                kind="DRIVE", start_at=T + timedelta(minutes=405), end_at=T + timedelta(minutes=645)
            ),
            leg_index=2,
        ),
        PlanActivity(
            activity=RuleActivity(
                kind="DAILY_REST",
                start_at=T + timedelta(minutes=645),
                end_at=T + timedelta(minutes=1305),
                reason="DAILY_DRIVING_LIMIT",
            ),
            point_key="B",
            leg_index=2,
        ),
        PlanActivity(
            activity=RuleActivity(
                kind="DRIVE",
                start_at=T + timedelta(minutes=1305),
                end_at=T + timedelta(minutes=1365),
            ),
            leg_index=2,
        ),
    ]
    stops = [
        PlanStop(
            sequence=0,
            kind="START",
            point=home,
            arrival_at=T,
            service_start_at=T,
            departure_at=T,
            counters=_state(0),
        ),
        PlanStop(
            sequence=1,
            kind="PICKUP",
            offer_id="O1",
            point=home,
            arrival_at=T,
            service_start_at=T,
            departure_at=T + timedelta(minutes=30),
            service_min=30,
            load_pallet_eq_after=Decimal("1"),
            load_kg_after=100,
            counters=pickup_state,
        ),
        PlanStop(
            sequence=2,
            kind="BREAK",
            arrival_at=T + timedelta(minutes=300),
            service_start_at=T + timedelta(minutes=300),
            departure_at=T + timedelta(minutes=345),
            counters=break_state,
        ),
        PlanStop(
            sequence=3,
            kind="DELIVERY",
            offer_id="O1",
            point=foreign,
            arrival_at=T + timedelta(minutes=375),
            service_start_at=T + timedelta(minutes=375),
            departure_at=T + timedelta(minutes=405),
            service_min=30,
            leg_km=Decimal("300.00"),
            leg_drive_min=300,
            counters=delivery_state,
        ),
        PlanStop(
            sequence=4,
            kind="DAILY_REST",
            point=foreign,
            arrival_at=T + timedelta(minutes=645),
            service_start_at=T + timedelta(minutes=645),
            departure_at=T + timedelta(minutes=1305),
            counters=rest_state,
        ),
        PlanStop(
            sequence=5,
            kind="END",
            point=home,
            arrival_at=T + timedelta(minutes=1365),
            service_start_at=T + timedelta(minutes=1365),
            departure_at=T + timedelta(minutes=1365),
            leg_km=Decimal("300.00"),
            leg_drive_min=300,
            counters=end_state,
        ),
    ]
    legs = [
        PlanLeg(
            start=home,
            end=home,
            distance_km=Decimal("0.00"),
            drive_min=0,
            load_kg=0,
            load_pallet_eq=Decimal("0"),
            departed_at=T,
            arrived_at=T,
        ),
        PlanLeg(
            start=home,
            end=foreign,
            distance_km=Decimal("300.00"),
            drive_min=300,
            load_kg=100,
            load_pallet_eq=Decimal("1"),
            departed_at=T + timedelta(minutes=30),
            arrived_at=T + timedelta(minutes=375),
        ),
        PlanLeg(
            start=foreign,
            end=home,
            distance_km=Decimal("300.00"),
            drive_min=300,
            load_kg=0,
            load_pallet_eq=Decimal("0"),
            departed_at=T + timedelta(minutes=405),
            arrived_at=T + timedelta(minutes=1365),
        ),
    ]
    calculation = Calculation(
        fuel=12356,
        toll=0,
        driver=15400,
        per_diem=0,
        accommodation=5500,
        vehicle=7200,
        parameters={
            "fuel_price_minor_per_l": {"value": "181", "provenance": "source"},
            "driver_cost_minor_per_hour": {"value": "1400", "provenance": "assumption"},
            "vehicle_cost_minor_per_km": {"value": "12", "provenance": "assumption"},
            "accommodation_minor": {"value": "5500", "provenance": "assumption"},
            "co2_factor_kg_per_l": {"value": "2.6", "provenance": "assumption"},
            "fuel_consumption": {"value": "11.0/13.0", "provenance": "assumption"},
        },
    )
    plan = RoutePlan(
        plan_ref="D1:O1",
        driver_id="D1",
        offer_ids=["O1"],
        actions=[Action(kind="PICKUP", offer_id="O1"), Action(kind="DELIVERY", offer_id="O1")],
        rules_profile="eu561_van_international_v1",
        departure_at=T,
        finish_at=T + timedelta(minutes=1365),
        home_reached=True,
        revenue_minor=100000,
        cost_total_minor=40456,
        net_profit_minor=59544,
        margin_pct=Decimal("59.54"),
        calculation=calculation,
        distance_km=Decimal("600.00"),
        empty_km=Decimal("300.00"),
        fuel_l=Decimal("68.265"),
        co2_kg=Decimal("177.49"),
        duration_min=1365,
        work_min=660,
        drive_min=600,
        service_min=60,
        wait_min=0,
        warnings=["LOADING_ORDER_NOT_MODELLED", "SERVICE_TIME_DEFAULTED"],
        stops=stops,
        legs=legs,
        activities=activities,
    )
    return snapshot, plan


def route_mutations(plan: RoutePlan) -> tuple[tuple[str, RoutePlan, str, int], ...]:
    stops = list(plan.stops)
    pickup = next(index for index, stop in enumerate(stops) if stop.kind == "PICKUP")
    delivery = next(index for index, stop in enumerate(stops) if stop.kind == "DELIVERY")
    high_load = list(stops)
    high_load[pickup] = high_load[pickup].model_copy(update={"load_kg_after": 1001})
    late = list(stops)
    late[delivery] = late[delivery].model_copy(update={"service_start_at": T + timedelta(days=2)})
    return (
        ("load", plan.model_copy(update={"stops": high_load}), "CAPACITY_INVALID", 1),
        (
            "order",
            plan.model_copy(
                update={
                    "actions": [
                        Action(kind="DELIVERY", offer_id="O1"),
                        Action(kind="PICKUP", offer_id="O1"),
                    ]
                }
            ),
            "ACTION_ORDER_INVALID",
            2,
        ),
        ("window", plan.model_copy(update={"stops": late}), "WINDOW_MISSED", 4),
        (
            "break",
            plan.model_copy(update={"stops": [stop for stop in stops if stop.kind != "BREAK"]}),
            "BREAK_OR_LIMIT_INVALID",
            6,
        ),
        (
            "profit",
            plan.model_copy(update={"net_profit_minor": plan.net_profit_minor + 1}),
            "PROFIT_INVALID",
            7,
        ),
        (
            "co2",
            plan.model_copy(update={"co2_kg": plan.co2_kg + Decimal(".01")}),
            "CO2_INVALID",
            17,
        ),
        (
            "home",
            plan.model_copy(update={"stops": [stop for stop in stops if stop.kind != "END"]}),
            "HOME_END_MISSING",
            13,
        ),
        (
            "profile",
            plan.model_copy(update={"rules_profile": "pl_domestic_employee_v1"}),
            "WRONG_PROFILE",
            14,
        ),
    )
