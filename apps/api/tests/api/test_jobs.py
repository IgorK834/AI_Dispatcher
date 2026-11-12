"""Persistent job and immutable result acceptance checks (no provider calls)."""

from uuid import uuid4

import pytest
from sqlalchemy import select, update

from routepilot.optimization.jobs.service import JobCreate
from routepilot.shared.errors import DomainError


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


@pytest.mark.ac("AC-FEAT-004-11", "AC-FEAT-004-12", "AC-FEAT-004-17", "AC-FEAT-004-03")
def test_offline_worker_persists_readable_schedules(routed_job):
    service, plans, _assignments, _user, job_id = routed_job
    job = service.get(job_id)
    assert job.status == "succeeded"
    assert job.progress.drivers_done == job.progress.drivers_total == 1
    assert job.stats is not None and job.stats.nodes > 0
    assert job.stats.runtime_ms > 0
    result = service.result(job_id)
    assert set(result.fleet) == {"profit", "fastest", "fuel"}
    assert result.disclaimer.endswith("It does not certify legal compliance.")
    for solution in [
        *result.fleet.values(),
        result.baselines.baseline_single,
        result.baselines.baseline_greedy,
    ]:
        for assignment in solution.assignments:
            plan = plans.get(assignment.route_plan_id)
            assert plan.id == assignment.route_plan_id
            assert plan.stops == sorted(plan.stops, key=lambda stop: stop.sequence)
            assert plan.stops[0].counters.work_today >= 0
            assert plan.calculation.parameters
            assert plan.fuel_l > 0 and plan.co2_kg > 0
            assert "ROUTING_FALLBACK" in plan.warnings
            assert "GEOMETRY_APPROXIMATE" in plan.warnings
            assert plan.geometry["type"] == "LineString"
            assert plans.validate(plan.id).valid
            assert plans.check_plan_rules(plan.id).valid


@pytest.mark.ac(
    "AC-FEAT-004-09", "AC-FEAT-004-10", "AC-FEAT-004-12", "AC-FEAT-004-13", "AC-FEAT-004-20"
)
def test_jobs_http_contract(job_client):
    client, (_service, _plans, _assignments, _user, job_id) = job_client
    result = client.get(f"/api/v1/optimization-jobs/{job_id}/result")
    assert result.status_code == 200 and result.json()["disclaimer"]
    assert client.get(f"/api/v1/optimization-jobs/{job_id}").json()["stats"]["nodes"] > 0
    body = {"scope": "fleet", "driverIds": []}
    first = client.post(
        "/api/v1/optimization-jobs", json=body, headers={"Idempotency-Key": "http-K"}
    )
    assert first.status_code == 202 and first.json()["status"] == "queued"
    assert first.headers["Location"].endswith(first.json()["id"])
    repeat = client.post(
        "/api/v1/optimization-jobs", json=body, headers={"Idempotency-Key": "http-K"}
    )
    assert repeat.status_code == 202 and repeat.json()["id"] == first.json()["id"]
    assert client.get(first.headers["Location"] + "/result").json()["code"] == "JOB_NOT_FINISHED"
    reused = client.post(
        "/api/v1/optimization-jobs",
        json={**body, "objectives": ["fuel"]},
        headers={"Idempotency-Key": "http-K"},
    )
    assert reused.status_code == 409 and reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    invalid = client.post(
        "/api/v1/optimization-jobs",
        json={"scope": "driver", "driverIds": [str(uuid4()), str(uuid4())]},
    )
    assert invalid.status_code == 422
    unknown = client.post(
        "/api/v1/optimization-jobs", json={"scope": "driver", "driverIds": [str(uuid4())]}
    )
    assert unknown.status_code == 404
    client.post("/api/v1/optimization-jobs", json=body)
    fourth = client.post("/api/v1/optimization-jobs", json=body)
    assert fourth.status_code == 429 and fourth.json()["code"] == "RATE_LIMITED"


@pytest.mark.ac("AC-FEAT-004-09")
def test_invalid_scope_unknown_ids_and_deleted_driver_are_refused(job_client):
    client, (service, _plans, _assignments, _user, _job_id) = job_client
    drivers = service.repository.table("drivers")
    with service.repository.session() as session:
        driver_id = session.scalars(select(drivers.c.id).order_by(drivers.c.id)).first()
    url = "/api/v1/optimization-jobs"
    duplicate = str(uuid4())
    with service.repository.session() as session:
        before = len(session.scalars(select(service.repository.Job)).all())
    for body in (
        {"scope": "driver", "driverIds": []},
        {"scope": "driver", "driverIds": [driver_id, driver_id]},
        {"scope": "fleet", "objectives": []},
        {"scope": "fleet", "objectives": ["profit", "profit"]},
        {"scope": "fleet", "objectives": ["cheapest"]},
        {"scope": "fleet", "offerIds": [duplicate, duplicate]},
    ):
        assert client.post(url, json=body).status_code == 422, body
    unknown_offer = client.post(url, json={"scope": "fleet", "offerIds": [str(uuid4())]})
    assert unknown_offer.status_code == 404 and unknown_offer.json()["code"] == "NOT_FOUND"
    with service.repository.engine.begin() as connection:
        connection.execute(
            update(drivers)
            .where(drivers.c.id == driver_id)
            .values(deleted_at="2026-11-11T00:00:00")
        )
    deleted = client.post(url, json={"scope": "driver", "driverIds": [driver_id]})
    assert deleted.status_code == 404, "a soft-deleted driver is unknown to the optimizer"
    assert client.get(f"{url}/{uuid4()}").status_code == 404
    with service.repository.session() as session:
        after = len(session.scalars(select(service.repository.Job)).all())
    assert after == before, "a refused request queues nothing"


@pytest.mark.ac("AC-FEAT-004-09")
def test_objective_subset_and_fleet_scope_cover_all_active_drivers(job_client):
    client, (service, _plans, _assignments, _user, _job_id) = job_client
    drivers = service.repository.table("drivers")
    with service.repository.session() as session:
        active = len(
            session.scalars(select(drivers.c.id).where(drivers.c.deleted_at.is_(None))).all()
        )
    created = client.post(
        "/api/v1/optimization-jobs",
        json={"scope": "fleet", "driverIds": [], "objectives": ["fuel"]},
    )
    assert created.status_code == 202
    body = created.json()
    assert body["objectives"] == ["fuel"]
    assert body["status"] == "queued" and body["progress"]["phase"] == "queued"
    assert body["progress"]["driversDone"] == 0
    assert body["progress"]["driversTotal"] == active > 1, "an empty list means every active driver"
    assert body["requestedBy"] and body["createdAt"] and body["startedAt"] is None
    assert created.headers["Location"] == f"/api/v1/optimization-jobs/{body['id']}"


@pytest.mark.ac("AC-FEAT-004-13")
def test_failed_job_shows_its_error_code_and_has_no_result(job_client):
    client, (service, _plans, _assignments, user, _job_id) = job_client
    job = service.create(JobCreate(scope="fleet"), user)
    with service.repository.session() as session:
        row = session.get(service.repository.Job, job.id)
        row.status = "failed"
        row.error = {"code": "ENGINE_ERROR", "message": "The optimization failed."}
    shown = client.get(f"/api/v1/optimization-jobs/{job.id}")
    assert shown.status_code == 200 and shown.json()["status"] == "failed"
    assert shown.json()["error"]["code"] == "ENGINE_ERROR"
    assert client.get(f"/api/v1/optimization-jobs/{job.id}/result").status_code == 404
