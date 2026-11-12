"""FEAT-004 assignment conflicts, atomic approval and cancellation."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from routepilot.identity.repository.models import AuditEvent
from routepilot.optimization.jobs.repository import AssignmentRow
from routepilot.optimization.jobs.service import AssignmentService
from routepilot.shared.errors import DomainError


def profit_id(service, job_id):
    return service.result(job_id).fleet["profit"].assignments[0].route_plan_id


@pytest.mark.ac("AC-FEAT-004-18", "AC-FEAT-004-19")
def test_human_assignment_and_cancellation_http(job_client):
    client, (service, _plans, assignments, _user, job_id) = job_client
    plan_id = profit_id(service, job_id)
    created = client.post("/api/v1/assignments", json={"routePlanId": str(plan_id)})
    assert created.status_code == 201
    assert created.headers["Location"].endswith(created.json()["id"])
    assert created.json()["agentRunId"] is None
    driver_id = UUID(created.json()["driverId"])
    assert assignments.assignment_usage(driver_id) == "active"
    assert client.get(created.headers["Location"]).json() == created.json()
    assert client.get(
        "/api/v1/assignments", params={"driverId": str(driver_id), "status": "active"}
    ).json()["items"] == [created.json()]
    again = client.post("/api/v1/assignments", json={"routePlanId": str(plan_id)})
    assert again.status_code == 409 and again.json()["code"] == "PLAN_NOT_ASSIGNABLE"
    offers = service.repository.table("freight_offers")
    with service.repository.session() as session:
        assert set(session.scalars(select(offers.c.status)).all()) == {"assigned"}
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "assignment.created")
            )
            == 1
        )
    assert client.delete(created.headers["Location"]).status_code == 204
    assert assignments.assignment_usage(driver_id) == "historical"
    with service.repository.session() as session:
        assert set(session.scalars(select(offers.c.status)).all()) == {"open"}
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "assignment.cancelled")
            )
            == 1
        )
    assert client.delete(created.headers["Location"]).status_code == 404
    assert client.get(f"/api/v1/assignments/{uuid4()}").status_code == 404


@pytest.mark.ac("AC-FEAT-004-18")
def test_stale_baseline_and_conflicting_sets_leave_no_partial_writes(routed_job):
    service, _plans, assignments, user, job_id = routed_job
    result = service.result(job_id)
    plan_id = profit_id(service, job_id)
    baseline = result.baselines.baseline_single.assignments[0].route_plan_id
    assert assignments.check_assignable([plan_id]).valid
    assert not assignments.check_assignable([plan_id, baseline]).valid
    with pytest.raises(DomainError, match="PLAN_NOT_ASSIGNABLE"):
        assignments.assign_many([plan_id, baseline], user)
    with service.repository.session() as session:
        assert session.scalar(select(func.count()).select_from(AssignmentRow)) == 0
    offers = service.repository.table("freight_offers")
    with service.repository.engine.begin() as connection:
        connection.execute(update(offers).values(version=offers.c.version + 1))
    assert not assignments.check_assignable([plan_id]).valid
    with pytest.raises(DomainError, match="PLAN_NOT_ASSIGNABLE") as failure:
        assignments.assign(plan_id, user)
    assert any(error["code"] == "OFFER_CHANGED" for error in failure.value.errors)
    with service.repository.session() as session:
        assert set(session.scalars(select(offers.c.status)).all()) == {"open"}
        assert session.scalar(select(func.count()).select_from(AssignmentRow)) == 0


@pytest.mark.ac("AC-FEAT-004-18")
def test_concurrent_tabs_only_create_one_assignment(routed_job):
    service, _plans, assignments, user, job_id = routed_job
    plan_id = profit_id(service, job_id)

    def assign():
        try:
            return assignments.assign(plan_id, user).status
        except DomainError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: assign(), range(2)))
    assert sorted(results) == ["PLAN_NOT_ASSIGNABLE", "active"]
    with service.repository.session() as session:
        assert session.scalar(select(func.count()).select_from(AssignmentRow)) == 1


@pytest.mark.ac("AC-FEAT-004-18")
def test_audit_failure_rolls_back_offer_updates_and_assignment(routed_job):
    service, _plans, _assignments, user, job_id = routed_job

    class BrokenAudit:
        def record(self, *args, **kwargs):
            raise RuntimeError("offline audit failure")

    assignments = AssignmentService(service.repository.engine, service.clock, BrokenAudit())
    with pytest.raises(RuntimeError, match="audit failure"):
        assignments.assign(profit_id(service, job_id), user)
    offers = service.repository.table("freight_offers")
    with service.repository.session() as session:
        assert session.scalar(select(func.count()).select_from(AssignmentRow)) == 0
        assert set(session.scalars(select(offers.c.status)).all()) == {"open"}
