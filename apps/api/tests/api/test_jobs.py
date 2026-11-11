"""Persistent job and immutable result acceptance checks (no provider calls)."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import select

from routepilot.optimization.jobs.service import JobCreate, JobService
from routepilot.routing.haversine import HaversineRoutingProvider
from routepilot.shared.clock import FixedClock
from routepilot.shared.db.engine import make_engine, migration_config
from routepilot.shared.errors import DomainError


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


@pytest.mark.ac("AC-FEAT-004-09", "AC-FEAT-004-10", "AC-FEAT-004-13", "AC-FEAT-004-20")
def test_creation_idempotency_queue_limit_and_unfinished_result(jobs):
    service, user = jobs
    body = JobCreate(scope="fleet")
    first = service.create(body, user, idempotency_key="K")
    assert first.status == "queued"
    assert first.objectives == ["profit", "fastest", "fuel"]
    assert service.create(body, user, idempotency_key="K").id == first.id
    with pytest.raises(DomainError, match="IDEMPOTENCY_KEY_REUSED"):
        service.create(JobCreate(scope="fleet", objectives=["fuel"]), user, idempotency_key="K")
    with pytest.raises(DomainError, match="JOB_NOT_FINISHED"):
        service.result(first.id)
    service.create(body, user)
    service.create(body, user)
    with pytest.raises(DomainError, match="RATE_LIMITED"):
        service.create(body, user)
    with pytest.raises(DomainError, match="NOT_FOUND"):
        service.create(JobCreate(scope="driver", driver_ids=[uuid4()]), uuid4())
    with service.repository.session() as session:
        assert len(session.scalars(select(service.repository.Job)).all()) == 3
