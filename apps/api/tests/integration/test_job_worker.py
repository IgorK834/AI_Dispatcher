"""Real process-worker lifecycle, recovery, failure and event-loop responsiveness."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from alembic import command
from fastapi import FastAPI
from sqlalchemy import select
from structlog.testing import capture_logs

from routepilot.optimization.jobs.repository import JobRow
from routepilot.optimization.jobs.service import JobCreate, JobService
from routepilot.routing.haversine import HaversineRoutingProvider
from routepilot.shared.clock import FixedClock
from routepilot.shared.db.engine import make_engine, migration_config
from routepilot.shared.errors import DomainError


@pytest.fixture
def worker(tmp_path):
    url = f"sqlite:///{tmp_path / 'worker.db'}"
    command.upgrade(migration_config(url), "head")
    engine = make_engine(url)
    clock = FixedClock(datetime(2026, 11, 16, tzinfo=UTC))
    service = JobService(engine, clock, HaversineRoutingProvider(), poll_interval_ms=10)
    user = uuid4()
    table = service.repository.table("users")
    with engine.begin() as connection:
        connection.execute(
            table.insert().values(
                id=str(user),
                version=1,
                created_at=clock.now().isoformat(),
                updated_at=clock.now().isoformat(),
                email="worker@example.test",
                password_hash=str(uuid4()),
                role="dispatcher",
                locale="en",
                is_active=True,
                failed_logins=0,
            )
        )
    yield service, user
    engine.dispose()


@pytest.mark.integration
@pytest.mark.ac("AC-FEAT-004-11", "AC-FEAT-004-15")
def test_single_real_process_worker_keeps_api_responsive(worker):
    service, user = worker
    first = service.create(JobCreate(scope="fleet"), user)
    second = service.create(JobCreate(scope="fleet"), user)
    running_counts = []

    class SlowRouting(HaversineRoutingProvider):
        def matrix(self, points):
            with service.repository.session() as session:
                running_counts.append(
                    len(session.scalars(select(JobRow).where(JobRow.status == "running")).all())
                )
            time.sleep(0.1)
            return super().matrix(points)

    service.routing = SlowRouting()
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    async def scenario():
        await service.start()
        try:
            for _ in range(100):
                if service.get(first.id).status == "running":
                    break
                await asyncio.sleep(0.01)
            assert service.get(first.id).status == "running"
            assert service.get(second.id).status == "queued"
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://test"
            ) as client:
                began = time.perf_counter()
                response = await client.get("/health")
                assert response.status_code == 200 and time.perf_counter() - began < 0.2
            await service.wait(first.id)
            await service.wait(second.id)
        finally:
            await service.stop()

    with capture_logs() as events:
        asyncio.run(scenario())
    assert running_counts == [1, 1]
    assert service.get(first.id).status == service.get(second.id).status == "succeeded"
    assert events and all(
        event.get("job_id") in {str(first.id), str(second.id)} for event in events
    )
    started = [event["job_id"] for event in events if event["event"] == "optimization_started"]
    assert started == [str(first.id), str(second.id)]


@pytest.mark.integration
@pytest.mark.ac("AC-FEAT-004-14", "AC-FEAT-004-13")
def test_recovery_requeues_once_then_exposes_restart_failure(worker):
    service, user = worker
    jobs = [service.create(JobCreate(scope="fleet"), user) for _ in range(3)]
    with service.repository.session() as session:
        for index, job in enumerate(jobs):
            row = session.get(JobRow, job.id)
            row.status = "running"
            row.attempts = 2 if index == 1 else 1
            row.heartbeat_at = (
                service.clock.now() - timedelta(seconds=61) if index < 2 else service.clock.now()
            )
    service.recover()
    assert service.get(jobs[0].id).status == "queued"
    assert service.get(jobs[1].id).error.code == "WORKER_RESTARTED"
    assert service.get(jobs[2].id).status == "running"
    with pytest.raises(DomainError, match="NOT_FOUND"):
        service.result(jobs[1].id)
    asyncio.run(service.run_one(jobs[0].id))
    assert service.get(jobs[0].id).status == "succeeded"
    assert service.result(jobs[0].id).baselines.baseline_single.assignments == []


def fail_engine(snapshot):
    raise RuntimeError("untrusted provider text must not enter stored error")


@pytest.mark.integration
@pytest.mark.ac("AC-FEAT-004-13")
def test_engine_failure_is_persisted_without_exception_text(worker, monkeypatch):
    from routepilot.optimization.jobs import service as module

    service, user = worker
    job = service.create(JobCreate(scope="fleet"), user)
    monkeypatch.setattr(module, "_optimize", fail_engine)
    # Real process execution is covered above; a thread permits deterministic
    # injection of this failure without modifying the pure engine.
    monkeypatch.setattr(module, "ProcessPoolExecutor", ThreadPoolExecutor)
    asyncio.run(service.run_one(job.id))
    failed = service.get(job.id)
    assert failed.status == "failed" and failed.error.code == "ENGINE_ERROR"
    assert "untrusted" not in failed.error.message
    with pytest.raises(DomainError, match="NOT_FOUND"):
        service.result(job.id)
