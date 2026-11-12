"""FEAT-001 fleet service rules, optimistic versions and filter-bound pagination."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from pydantic import ValidationError

from routepilot.fleet.service import (
    CostProfileCreate,
    DriverCreate,
    DriverStateCreate,
    DriverUpdate,
    FleetService,
    VehicleCreate,
)
from routepilot.shared.clock import FixedClock
from routepilot.shared.db.engine import make_engine, migration_config
from routepilot.shared.errors import DomainError


@pytest.fixture
def fleet(tmp_path):
    url = f"sqlite:///{tmp_path / 'fleet.db'}"
    command.upgrade(migration_config(url), "head")
    engine = make_engine(url)
    service = FleetService(engine, FixedClock(datetime(2026, 11, 16, tzinfo=UTC)))
    yield service
    engine.dispose()


def profile() -> CostProfileCreate:
    return CostProfileCreate(
        name="Fixture costs",
        currency="EUR",
        fuel_price_minor_per_l=181,
        driver_cost_minor_per_hour=1400,
        vehicle_cost_minor_per_km=12,
        accommodation_minor=5500,
        per_diem={"PL": 1059},
        tolls={"perKm": {}, "annualVignettes": []},
        fx_rates={"PLN": "4.25"},
        min_profit_minor=0,
        min_margin_pct="0",
    )


def driver(name: str = "Driver fixture") -> DriverCreate:
    return DriverCreate(
        name=name, home_city="Katowice", home_country="PL", home_lat=50.2649, home_lon=19.0238
    )


@pytest.mark.ac(
    "AC-FEAT-001-04", "AC-FEAT-001-05", "AC-FEAT-001-06", "AC-FEAT-001-07", "AC-FEAT-001-08"
)
def test_driver_crud_cursor_versions_and_state(fleet) -> None:
    actor = str(uuid4())
    created = [fleet.create_driver(driver(f"Driver fixture {i}"), actor) for i in range(7)]
    assert all(row.version == 1 for row in created)
    cursor = None
    seen = []
    for expected in (3, 3, 1):
        page = fleet.list_drivers(limit=3, cursor=cursor, home_city="Katowice")
        assert len(page.items) == expected
        seen.extend(row.id for row in page.items)
        cursor = page.next_cursor
    assert len(set(seen)) == 7 and cursor is None
    first = fleet.list_drivers(limit=3)
    with pytest.raises(DomainError, match="VALIDATION_ERROR"):
        fleet.list_drivers(cursor=first.next_cursor, home_city="other")
    changed = fleet.update_driver(
        created[0].id, DriverUpdate(version=1, name="Changed fixture"), actor
    )
    assert changed.name == "Changed fixture" and changed.version == 2
    with pytest.raises(DomainError, match="VERSION_CONFLICT"):
        fleet.update_driver(created[0].id, DriverUpdate(version=1, name="stale"), actor)
    state = DriverStateCreate(
        current_lat=50,
        current_lon=19,
        available_from=fleet.clock.now(),
        work_today_min=0,
        drive_today_min=0,
        work_since_break_min=0,
        drive_since_break_min=0,
        work_week_min=0,
        drive_week_min=0,
        drive_prev_week_min=0,
    )
    fleet.add_state(created[0].id, state, actor)
    assert fleet.get_driver(created[0].id).state is not None
    fleet.delete_driver(created[0].id, actor)
    with pytest.raises(DomainError, match="NOT_FOUND"):
        fleet.get_driver(created[0].id)


@pytest.mark.ac("AC-FEAT-001-10", "AC-FEAT-001-11")
def test_vehicle_profile_references_and_strict_money(fleet) -> None:
    actor = str(uuid4())
    costs = fleet.create_cost_profile(profile(), actor)
    body = VehicleCreate(
        label="Fixture van",
        vehicle_type="VEHICLE_UP_TO_3_5_T",
        body_type="CURTAIN_SIDER",
        pallet_places=8,
        layout_template="DECLARED_ONLY",
        side_access="BOTH",
        payload_kg=1000,
        gvw_kg=3500,
        sleeper_cab=False,
        fuel={"lPer100kmEmptyAt90": "11", "lPer100kmFullAt90": "13"},
        cost_profile_id=costs.id,
    )
    van = fleet.create_vehicle(body, actor)
    with pytest.raises(DomainError, match="COST_PROFILE_IN_USE"):
        fleet.delete_cost_profile(costs.id, actor)
    assigned = fleet.create_driver(driver().model_copy(update={"vehicle_id": van.id}), actor)
    with pytest.raises(DomainError, match="VEHICLE_ASSIGNED_TO_DRIVER"):
        fleet.delete_vehicle(van.id, actor)
    fleet.delete_driver(assigned.id, actor)
    fleet.delete_vehicle(van.id, actor)
    fleet.delete_cost_profile(costs.id, actor)
    data = profile().model_dump()
    data["fuel_price_minor_per_l"] = 1.5
    with pytest.raises(ValidationError):
        CostProfileCreate.model_validate(data)


@pytest.mark.ac("AC-FEAT-002-15")
def test_seed_idempotent(fleet: FleetService) -> None:
    from datetime import date

    assert fleet.seed(20261109, date(2026, 11, 16))["drivers"] == 5
    ids = [d.id for d in fleet.list_drivers().items]
    fleet.seed(20261109, date(2026, 11, 16))
    assert [d.id for d in fleet.list_drivers().items] == ids
    assert all(d.state and d.vehicle and d.is_synthetic for d in fleet.list_drivers().items)


@pytest.mark.ac("AC-FEAT-001-08")
@pytest.mark.ac("AC-FEAT-006-29")
@pytest.mark.ac("AC-FEAT-006-30")
def test_active_historical_usage_and_query_helpers(fleet: FleetService) -> None:
    from uuid import UUID

    class Usage:
        answer = "active"

        def assignment_usage(self, driver_id: UUID):
            return self.answer

    usage = Usage()
    fleet.usage_checker = usage
    item = fleet.create_driver(driver(), "test")
    assert fleet.has_active_assignment(item.id)
    assert fleet.list_active()[0].id == item.id
    with pytest.raises(DomainError, match="NOT_FOUND"):
        fleet.latest_state(item.id)
    with pytest.raises(DomainError, match="DRIVER_HAS_ACTIVE_ASSIGNMENT"):
        fleet.delete_driver(item.id, "test")
    usage.answer = "historical"
    fleet.delete_driver(item.id, "test")
    assert not fleet.list_active()
    with pytest.raises(DomainError, match="NOT_FOUND"):
        fleet.get_driver(item.id)
