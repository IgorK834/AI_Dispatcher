"""HTTP adapters; authorization and CSRF are injected by the composition root."""

from collections.abc import Callable
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status

from routepilot.optimization.jobs.service import AssignmentService, JobService, PlanService
from routepilot.optimization.jobs.service import JobCreate as JobCreate
from routepilot.optimization.jobs.service import domain as contracts
from routepilot.shared.auth import Principal
from routepilot.shared.pagination import Page


def create_jobs_router(
    jobs: JobService,
    plans: PlanService,
    assignments: AssignmentService,
    require_user: Callable[..., Principal],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["optimization"])
    actor_dependency = Depends(require_user)

    @router.post(
        "/optimization-jobs", status_code=status.HTTP_202_ACCEPTED, response_model=contracts.Job
    )
    def create_job(
        body: JobCreate,
        response: Response,
        actor: Principal = actor_dependency,
        idempotency_key: Annotated[
            str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
        ] = None,
    ) -> contracts.Job:
        job = jobs.create(body, actor.id, idempotency_key)
        response.headers["Location"] = f"/api/v1/optimization-jobs/{job.id}"
        return job

    @router.get("/optimization-jobs/{job_id}", response_model=contracts.Job)
    def get_job(job_id: UUID, actor: Principal = actor_dependency) -> contracts.Job:
        return jobs.get(job_id)

    @router.get("/optimization-jobs/{job_id}/result", response_model=contracts.JobResult)
    def get_result(job_id: UUID, actor: Principal = actor_dependency) -> contracts.JobResult:
        return jobs.result(job_id)

    @router.get("/route-plans/{plan_id}", response_model=contracts.RoutePlan)
    def get_plan(plan_id: UUID, actor: Principal = actor_dependency) -> contracts.RoutePlan:
        return plans.get(plan_id)

    @router.get("/assignments", response_model=Page[contracts.Assignment])
    def list_assignments(
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        cursor: str | None = None,
        driver_id: Annotated[UUID | None, Query(alias="driverId")] = None,
        assignment_status: Annotated[
            Literal["active", "cancelled"] | None, Query(alias="status")
        ] = None,
        actor: Principal = actor_dependency,
    ) -> Page[contracts.Assignment]:
        return assignments.list(
            limit=limit, cursor=cursor, driver_id=driver_id, status=assignment_status
        )

    @router.post(
        "/assignments", status_code=status.HTTP_201_CREATED, response_model=contracts.Assignment
    )
    def create_assignment(
        body: contracts.AssignmentCreate, response: Response, actor: Principal = actor_dependency
    ) -> contracts.Assignment:
        assignment = assignments.assign(body.route_plan_id, actor.id)
        response.headers["Location"] = f"/api/v1/assignments/{assignment.id}"
        return assignment

    @router.get("/assignments/{assignment_id}", response_model=contracts.Assignment)
    def get_assignment(
        assignment_id: UUID, actor: Principal = actor_dependency
    ) -> contracts.Assignment:
        return assignments.get(assignment_id)

    @router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
    def cancel_assignment(assignment_id: UUID, actor: Principal = actor_dependency) -> Response:
        assignments.cancel(assignment_id, actor.id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
