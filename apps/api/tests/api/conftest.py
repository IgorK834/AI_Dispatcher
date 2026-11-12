"""Persistent job and immutable result acceptance checks (no provider calls)."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command

from routepilot.optimization.jobs.service import JobCreate, JobService
from routepilot.routing.haversine import HaversineRoutingProvider
from routepilot.shared.clock import FixedClock
from routepilot.shared.db.engine import make_engine, migration_config


@pytest.fixture
def jobs(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'jobs.db'}"
    command.upgrade(migration_config(url), "head")
    engine = make_engine(url)
    service = JobService(
        engine, FixedClock(datetime(2026, 11, 11, tzinfo=UTC)), HaversineRoutingProvider()
    )
    user = uuid4()
    users = service.repository.table("users")
    with engine.begin() as connection:
        connection.execute(
            users.insert().values(
                id=str(user),
                version=1,
                created_at="2026-11-11T00:00:00+00:00",
                updated_at="2026-11-11T00:00:00+00:00",
                email="dispatcher@example.test",
                password_hash=str(uuid4()),
                role="dispatcher",
                locale="en",
                is_active=True,
                failed_logins=0,
            )
        )
    yield service, user
    engine.dispose()


@pytest.fixture
def routed_job(jobs):
    """One small deterministic synthetic route using the production fleet seed."""
    import asyncio
    from datetime import timedelta
    from uuid import NAMESPACE_URL, uuid5

    from routepilot.fleet.service import FleetService
    from routepilot.identity.repository.audit import SqlAuditWriter
    from routepilot.optimization.jobs.service import AssignmentService, PlanService

    service, user = jobs
    fleet = FleetService(service.repository.engine, service.clock)
    fleet.seed(42, service.clock.now())
    driver_id = uuid5(NAMESPACE_URL, "routepilot:MOCK-D1")
    snapshot = service.create(JobCreate(scope="driver", driver_ids=[driver_id], offer_ids=[]), user)
    initial = service.get_snapshot(snapshot.id)
    driver = initial.drivers[0]
    from routepilot.optimization.engine.models import Point

    delivery = Point(key="wroclaw", city="Wrocław", country="PL", lat=51.1079, lon=17.0385)
    offers, stops = (
        service.repository.table("freight_offers"),
        service.repository.table("freight_stops"),
    )
    now = service.clock.now().isoformat()
    offer_ids = []
    with service.repository.engine.begin() as connection:
        for index in range(2):
            offer_id = uuid4()
            offer_ids.append(offer_id)
            connection.execute(
                offers.insert().values(
                    id=str(offer_id),
                    version=1,
                    created_at=now,
                    updated_at=now,
                    source="mock",
                    source_offer_id=f"MOCK-JOB-{index}",
                    raw_record_id=None,
                    status="open",
                    is_synthetic=True,
                    description="Synthetic worker test fixture",
                    public_remark=None,
                    revenue_amount_minor=100000,
                    revenue_currency="EUR",
                    weight_kg=200,
                    pallet_count=2,
                    pallet_type="EUR_1200x800",
                    loading_length_mm=None,
                    required_body_types=["CURTAIN_SIDER"],
                    required_vehicle_types=["VEHICLE_UP_TO_3_5_T"],
                    completeness_score=1,
                    missing_fields=[],
                    quality_flags=[],
                    field_provenance={"palletCount": "generated_mock"},
                    retention_until=None,
                )
            )
            for sequence, point in enumerate((driver.position, delivery)):
                start = driver.available_from + timedelta(hours=sequence * 3)
                connection.execute(
                    stops.insert().values(
                        id=str(uuid4()),
                        offer_id=str(offer_id),
                        sequence=sequence,
                        stop_type="PICKUP" if sequence == 0 else "DELIVERY",
                        city=point.city or driver.home.city,
                        postal_code=None,
                        country_code="PL",
                        lat=point.lat,
                        lon=point.lon,
                        timezone="Europe/Warsaw",
                        window_start=start.isoformat(),
                        window_end=(start + timedelta(hours=8)).isoformat(),
                        service_minutes=30,
                        provenance={"serviceMinutes": "source"},
                    )
                )
    created = service.create(
        JobCreate(scope="driver", driver_ids=[driver_id], offer_ids=offer_ids), user
    )
    asyncio.run(service.run_one(created.id))
    result = service.result(created.id)
    if not result.per_driver[0].plans["profit"]:
        pytest.fail("Synthetic route fixture must create an optimized plan")
    plans = PlanService(service.repository.engine, service.clock, service.routing)
    assignments = AssignmentService(
        service.repository.engine,
        service.clock,
        SqlAuditWriter(service.repository.engine, service.clock),
    )
    yield service, plans, assignments, user, created.id


@pytest.fixture
def job_client(routed_job):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    from routepilot.optimization.jobs.api import create_jobs_router
    from routepilot.shared.auth import Principal
    from routepilot.shared.errors import DomainError
    from routepilot.shared.problem import problem

    service, plans, assignments, user, _job_id = routed_job
    app = FastAPI()

    @app.exception_handler(DomainError)
    async def handler(request: Request, error: DomainError):
        return problem(request, error.status, error.code, errors=error.errors)

    def actor():
        return Principal(id=user, role="dispatcher", locale="en", session_id=uuid4())

    app.include_router(create_jobs_router(service, plans, assignments, actor))
    with TestClient(app) as client:
        yield client, routed_job
