"""Public services shared by manual HTTP operations and runtime agent tools."""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from concurrent.futures import ProcessPoolExecutor
from datetime import timedelta
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import UUID, uuid4

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult, Engine
from sqlalchemy.exc import IntegrityError

from routepilot.optimization.engine.models import (
    EngineParams,
    EngineResult,
    EngineSnapshot,
    Point,
    TravelMatrix,
    ValidationResult,
)
from routepilot.optimization.jobs import domain
from routepilot.optimization.jobs.domain import (
    Assignment,
    Calculation,
    Counters,
    Job,
    JobCreate,
    JobError,
    JobResult,
    Money,
    PlanStop,
    Progress,
    RoutePlan,
    Stats,
)
from routepilot.optimization.jobs.repository import (
    AssignmentRow,
    JobRow,
    JobsRepository,
    PlanRow,
    StopRow,
)
from routepilot.optimization.jobs.results import plan_summary, store_result
from routepilot.optimization.jobs.snapshots import build_snapshot
from routepilot.routing.domain import GeoPoint, RoutingFailure
from routepilot.routing.ports import RoutingProvider
from routepilot.shared.audit import AuditWriter
from routepilot.shared.clock import Clock
from routepilot.shared.errors import DomainError
from routepilot.shared.pagination import CursorCodec, Page

__all__ = ["AssignmentService", "JobCreate", "JobService", "PlanService", "domain"]


def _optimize(snapshot: EngineSnapshot) -> EngineResult:
    # The pure function, and only its ready snapshot, cross the process boundary.
    from routepilot.optimization.engine import optimize

    return optimize(snapshot)


def _job(row: JobRow) -> Job:
    return Job.model_validate(
        dict(
            id=row.id,
            status=row.status,
            scope=row.scope,
            objectives=row.objectives,
            progress=Progress.model_validate(row.progress),
            stats=Stats.model_validate(row.stats) if row.stats else None,
            error=JobError.model_validate(row.error) if row.error else None,
            requested_by=row.requested_by,
            created_at=row.created_at,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )
    )


class JobService:
    def __init__(
        self,
        engine: Engine,
        clock: Clock,
        routing_provider: RoutingProvider,
        *,
        params: EngineParams | None = None,
        co2_factor_kg_per_l: Decimal = Decimal("2.6"),
        poll_interval_ms: int = 500,
        heartbeat_stale_s: int = 60,
    ) -> None:
        self.repository = JobsRepository(engine)
        self.clock, self.routing = clock, routing_provider
        self.params = params or EngineParams()
        self.co2 = co2_factor_kg_per_l
        self.poll_interval = poll_interval_ms / 1000
        self.heartbeat_stale_s = heartbeat_stale_s
        self._task: asyncio.Task[None] | None = None
        self._pool: ProcessPoolExecutor | None = None
        self._stopping = False
        self._create_lock = threading.Lock()
        self._completion: dict[UUID, asyncio.Event] = {}

    def create(
        self, body: JobCreate, requested_by: UUID, idempotency_key: str | None = None
    ) -> Job:
        document = body.model_dump(mode="json", by_alias=True)
        with self._create_lock, self.repository.session() as session:
            if idempotency_key:
                existing = session.scalar(
                    select(JobRow).where(JobRow.idempotency_key == idempotency_key)
                )
                if existing is not None:
                    if (
                        existing.request["body"] != document
                        or existing.requested_by != requested_by
                    ):
                        raise DomainError("IDEMPOTENCY_KEY_REUSED")
                    return _job(existing)
            now = self.clock.now()
            snapshot = build_snapshot(self.repository, session, body, now, self.params, self.co2)
            count = session.scalar(
                select(func.count())
                .select_from(JobRow)
                .where(
                    JobRow.requested_by == requested_by, JobRow.status.in_(["queued", "running"])
                )
            )
            if count is not None and count >= 3:
                raise DomainError("RATE_LIMITED", 429)
            payload = snapshot.model_dump(mode="json")
            digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            row = JobRow(
                id=uuid4(),
                created_at=now,
                updated_at=now,
                status="queued",
                scope=body.scope,
                objectives=body.objectives,
                idempotency_key=idempotency_key,
                input_sha256=digest,
                request={"body": document, "snapshot": payload},
                result=None,
                solver_version=snapshot.solver_version,
                progress=Progress(drivers_total=len(snapshot.drivers)).model_dump(by_alias=True),
                stats={},
                error=None,
                attempts=0,
                heartbeat_at=None,
                requested_by=requested_by,
                started_at=None,
                finished_at=None,
            )
            session.add(row)
            session.flush()
            structlog.get_logger().info("optimization_queued", job_id=str(row.id))
            return _job(row)

    def get(self, job_id: UUID) -> Job:
        with self.repository.session() as session:
            row = session.get(JobRow, job_id)
            if row is None:
                raise DomainError("NOT_FOUND", 404)
            return _job(row)

    def result(self, job_id: UUID) -> JobResult:
        with self.repository.session() as session:
            row = session.get(JobRow, job_id)
            if row is None or row.status in {"failed", "cancelled"}:
                raise DomainError("NOT_FOUND", 404)
            if row.status != "succeeded" or row.result is None:
                raise DomainError("JOB_NOT_FINISHED")
            return JobResult.model_validate(row.result["public"])

    def get_snapshot(self, job_id: UUID) -> EngineSnapshot:
        with self.repository.session() as session:
            row = session.get(JobRow, job_id)
            if row is None:
                raise DomainError("NOT_FOUND", 404)
            return EngineSnapshot.model_validate(row.request["snapshot"])

    def recover(self) -> None:
        now = self.clock.now()
        with self.repository.session() as session:
            rows = session.scalars(select(JobRow).where(JobRow.status == "running")).all()
            for row in rows:
                if row.heartbeat_at is not None and row.heartbeat_at >= now - timedelta(
                    seconds=self.heartbeat_stale_s
                ):
                    continue
                row.updated_at = now
                if row.attempts < 2:
                    row.status = "queued"
                    row.progress = Progress(
                        drivers_total=len(row.request["snapshot"]["drivers"])
                    ).model_dump(by_alias=True)
                else:
                    row.status, row.finished_at = "failed", now
                    row.error = {
                        "code": "WORKER_RESTARTED",
                        "message": "The worker stopped before this job finished.",
                    }
                structlog.get_logger().info(
                    "optimization_recovered", job_id=str(row.id), status=row.status
                )

    async def start(self) -> None:
        if self._task is not None:
            return
        self.recover()
        self._stopping = False
        self._pool = ProcessPoolExecutor(max_workers=1)
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopping = True
        if self._task is not None:
            await self._task
            self._task = None
        if self._pool is not None:
            await asyncio.to_thread(self._pool.shutdown, wait=True, cancel_futures=True)
            self._pool = None

    async def wait(self, job_id: UUID, *, timeout_s: float = 60) -> JobResult:
        async with asyncio.timeout(timeout_s):
            if self.get(job_id).status in {"queued", "running"}:
                await self._completion.setdefault(job_id, asyncio.Event()).wait()
        return self.result(job_id)

    async def _loop(self) -> None:
        while not self._stopping:
            with self.repository.session() as session:
                row = session.scalar(
                    select(JobRow)
                    .where(JobRow.status == "queued")
                    .order_by(JobRow.created_at, JobRow.id)
                    .limit(1)
                )
                job_id = row.id if row else None
            if job_id is None:
                await asyncio.sleep(self.poll_interval)
            else:
                await self.run_one(job_id)

    def _progress(self, job_id: UUID, phase: str) -> None:
        with self.repository.session() as session:
            row = session.get(JobRow, job_id)
            if row is not None and row.status == "running":
                row.heartbeat_at = row.updated_at = self.clock.now()
                row.progress = {**row.progress, "phase": phase}

    def _matrix(self, snapshot: EngineSnapshot) -> EngineSnapshot:
        points: dict[str, Point] = {}
        for driver in snapshot.drivers:
            for point in (driver.home, driver.position):
                if point.lat is not None and point.lon is not None:
                    points[point.key] = point
        for offer in snapshot.offers:
            for stop in offer.stops:
                if stop.point.lat is not None and stop.point.lon is not None:
                    points[stop.point.key] = stop.point
        ordered = [points[key] for key in sorted(points)]
        response = self.routing.matrix(
            [
                GeoPoint(lat=point.lat, lon=point.lon)
                for point in ordered
                if point.lat is not None and point.lon is not None
            ]
        )
        matrix = TravelMatrix(
            points=ordered,
            distance_km=response.distance_km,
            duration_min=response.duration_min,
            provider_id=response.provider_id,
            fallback=response.fallback,
        )
        return snapshot.model_copy(update={"matrix": matrix})

    async def run_one(self, job_id: UUID) -> None:
        """Process one queued job; the app's sole worker invokes this sequentially."""
        with self.repository.session() as session:
            row = session.get(JobRow, job_id)
            if row is None or row.status != "queued":
                return
            row.status = "running"
            row.attempts += 1
            row.started_at = row.heartbeat_at = row.updated_at = self.clock.now()
            snapshot = EngineSnapshot.model_validate(row.request["snapshot"])
            row.progress = {**row.progress, "phase": "routing"}
        log = structlog.get_logger().bind(job_id=str(job_id))
        log.info("optimization_started")
        try:
            snapshot = await asyncio.to_thread(self._matrix, snapshot)
            with self.repository.session() as session:
                row = session.get(JobRow, job_id)
                if row is None:
                    raise ValueError("Job disappeared")
                row.request = {**row.request, "snapshot": snapshot.model_dump(mode="json")}
            self._progress(job_id, "search")
            # run_one also supports a direct test invocation without a lifespan.
            own_pool = self._pool is None
            pool = self._pool or ProcessPoolExecutor(max_workers=1)
            try:
                future = asyncio.get_running_loop().run_in_executor(pool, _optimize, snapshot)
                while not future.done():
                    await asyncio.wait({future}, timeout=max(0.1, min(self.poll_interval, 5)))
                    self._progress(job_id, "search")
                result = await future
            finally:
                if own_pool:
                    await asyncio.to_thread(pool.shutdown, wait=True, cancel_futures=True)
            self._progress(job_id, "saving")
            with self.repository.session() as session:
                row = session.get(JobRow, job_id)
                if row is None:
                    raise ValueError("Job disappeared")
                store_result(session, row, result)
                row.status = "succeeded"
                row.finished_at = row.heartbeat_at = row.updated_at = self.clock.now()
                total = len(snapshot.drivers)
                row.progress = Progress(
                    phase="saving", drivers_done=total, drivers_total=total
                ).model_dump(by_alias=True)
            log.info("optimization_succeeded")
        except Exception as exc:
            # Provider/engine exception text can include external data, so the
            # persisted error and logs contain only safe classification.
            code = "ROUTING_ERROR" if isinstance(exc, RoutingFailure) else "ENGINE_ERROR"
            with self.repository.session() as session:
                row = session.get(JobRow, job_id)
                if row is not None:
                    row.status, row.finished_at, row.updated_at = (
                        "failed",
                        self.clock.now(),
                        self.clock.now(),
                    )
                    row.error = {"code": code, "message": "Optimization could not finish."}
            log.error("optimization_failed", error_code=code, exception_type=type(exc).__name__)
        finally:
            self._completion.setdefault(job_id, asyncio.Event()).set()


class PlanService:
    def __init__(self, engine: Engine, clock: Clock, routing_provider: RoutingProvider) -> None:
        self.repository = JobsRepository(engine)
        self.clock, self.routing = clock, routing_provider

    def resolve_ref(self, reference: str) -> UUID:
        try:
            return UUID(reference)
        except ValueError:
            prefix = reference.removeprefix("PLAN-").lower()
            if len(prefix) != 8 or any(char not in "0123456789abcdef" for char in prefix):
                raise DomainError("NOT_FOUND", 404) from None
            with self.repository.session() as session:
                ids = session.scalars(select(PlanRow.id)).all()
                matching = [value for value in ids if value.hex.startswith(prefix)]
                if len(matching) != 1:
                    raise DomainError("NOT_FOUND", 404) from None
                return matching[0]

    def get(self, plan_id: UUID) -> RoutePlan:
        with self.repository.session() as session:
            row = session.get(PlanRow, plan_id)
            if row is None:
                raise DomainError("NOT_FOUND", 404)
            stops = session.scalars(
                select(StopRow).where(StopRow.route_plan_id == plan_id).order_by(StopRow.sequence)
            ).all()
            if row.geometry is None and stops:
                response = self.routing.route(
                    [GeoPoint(lat=stop.lat, lon=stop.lon) for stop in stops], variant="FASTEST"
                )
                row.geometry = response.geometry
                if response.approximate and "GEOMETRY_APPROXIMATE" not in row.warnings:
                    row.warnings = [*row.warnings, "GEOMETRY_APPROXIMATE"]
            calc = row.calculation
            return RoutePlan(
                **plan_summary(row).model_dump(),
                revenue=Money(amount_minor=row.revenue_minor),
                cost_total=Money(amount_minor=row.cost_total_minor),
                calculation=Calculation(
                    **{
                        key: Money(amount_minor=calc[key])
                        for key in (
                            "fuel",
                            "toll",
                            "driver",
                            "per_diem",
                            "accommodation",
                            "vehicle",
                        )
                    },
                    parameters=calc["parameters"],
                ),
                work_min=row.work_min,
                drive_min=row.drive_min,
                wait_min=row.wait_min,
                stops=[
                    PlanStop(
                        sequence=stop.sequence,
                        kind=stop.kind,
                        offer_id=stop.offer_id,
                        label=stop.label,
                        lat=stop.lat,
                        lon=stop.lon,
                        arrival_at=stop.arrival_at,
                        wait_min=stop.wait_min,
                        service_start_at=stop.service_start_at,
                        departure_at=stop.departure_at,
                        leg_km=Decimal(stop.leg_m) / 1000,
                        leg_drive_min=stop.leg_drive_min,
                        load_pallet_eq_after=Decimal(stop.load_pallet_eq_after),
                        load_kg_after=stop.load_kg_after,
                        counters=Counters(
                            work_today=stop.work_today_min,
                            drive_today=stop.drive_today_min,
                            work_since_break=stop.work_since_break_min,
                            drive_since_break=stop.drive_since_break_min,
                        ),
                    )
                    for stop in stops
                ],
                geometry=row.geometry,
            )

    def validate(self, plan_id: UUID) -> ValidationResult:
        from routepilot.optimization.engine.validators import RouteValidator

        with self.repository.session() as session:
            row = session.get(PlanRow, plan_id)
            if row is None:
                raise DomainError("NOT_FOUND", 404)
            job = session.get(JobRow, row.job_id)
            if job is None or job.result is None:
                raise DomainError("NOT_FOUND", 404)
            snapshot = EngineSnapshot.model_validate(job.request["snapshot"])
            result = EngineResult.model_validate(job.result["engine"])
            ref = next(
                key for key, value in job.result["plan_ids"].items() if value == str(plan_id)
            )
            plans = [
                plan
                for variants in result.per_driver.values()
                for items in variants.values()
                for plan in items
            ] + result.baseline_plans
            plan = next(plan for plan in plans if plan.plan_ref == ref)
            return RouteValidator().validate(snapshot, plan)

    def compare(self, plan_ids: list[UUID]) -> dict[str, Any]:
        if not 2 <= len(plan_ids) <= 3:
            raise DomainError("VALIDATION_ERROR", 422)
        plans = [self.get(plan_id) for plan_id in plan_ids]
        base = plans[0]
        return {
            "plans": [plan.model_dump(mode="json", by_alias=True) for plan in plans],
            "deltas": [
                {
                    "routePlanId": str(plan.id),
                    "netProfitMinor": plan.net_profit.amount_minor - base.net_profit.amount_minor,
                    "fuelL": str(plan.fuel_l - base.fuel_l),
                    "co2Kg": str(plan.co2_kg - base.co2_kg),
                    "distanceKm": str(plan.distance_km - base.distance_km),
                    "durationMin": plan.duration_min - base.duration_min,
                }
                for plan in plans[1:]
            ],
        }

    def plan_facts(self, plan_id: UUID) -> RoutePlan:
        return self.get(plan_id)


class AssignmentService:
    def __init__(self, engine: Engine, clock: Clock, audit: AuditWriter) -> None:
        self.repository = JobsRepository(engine)
        self.clock, self.audit = clock, audit
        self._lock = threading.Lock()
        self.cursors = CursorCodec()

    @staticmethod
    def _view(row: AssignmentRow) -> Assignment:
        return Assignment.model_validate(
            dict(
                id=row.id,
                route_plan_id=row.route_plan_id,
                driver_id=row.driver_id,
                status=row.status,
                approved_by=row.approved_by,
                approved_at=row.approved_at,
                agent_run_id=row.agent_run_id,
                created_at=row.created_at,
            )
        )

    def assignment_usage(self, driver_id: UUID) -> Literal["none", "active", "historical"]:
        with self.repository.session() as session:
            statuses = session.scalars(
                select(AssignmentRow.status).where(AssignmentRow.driver_id == driver_id)
            ).all()
            return "active" if "active" in statuses else "historical" if statuses else "none"

    def get(self, assignment_id: UUID) -> Assignment:
        with self.repository.session() as session:
            row = session.get(AssignmentRow, assignment_id)
            if row is None:
                raise DomainError("NOT_FOUND", 404)
            return self._view(row)

    def list_assignments(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        driver_id: UUID | None = None,
        status: Literal["active", "cancelled"] | None = None,
    ) -> Page[Assignment]:
        if not 1 <= limit <= 100:
            raise DomainError("VALIDATION_ERROR", 422)
        filters = {
            "resource": "assignments",
            "driverId": str(driver_id) if driver_id else None,
            "status": status,
        }
        last = self.cursors.decode(cursor, filters)
        with self.repository.session() as session:
            query = select(AssignmentRow).order_by(AssignmentRow.id)
            if last:
                query = query.where(AssignmentRow.id > UUID(last))
            if driver_id:
                query = query.where(AssignmentRow.driver_id == driver_id)
            if status:
                query = query.where(AssignmentRow.status == status)
            rows = session.scalars(query.limit(limit + 1)).all()
            return Page(
                items=[self._view(row) for row in rows[:limit]],
                nextCursor=self.cursors.encode(str(rows[limit - 1].id), filters)
                if len(rows) > limit
                else None,
            )

    def assign(
        self, plan_id: UUID, approved_by: UUID, agent_run_id: UUID | None = None
    ) -> Assignment:
        return self.assign_many([plan_id], approved_by, agent_run_id)[0]

    def assign_many(
        self, plan_ids: list[UUID], approved_by: UUID, agent_run_id: UUID | None = None
    ) -> list[Assignment]:
        if not plan_ids or len(set(plan_ids)) != len(plan_ids):
            raise DomainError("PLAN_NOT_ASSIGNABLE", errors=[{"code": "CONFLICTING_PLANS"}])
        try:
            with self._lock, self.repository.session() as session:
                plans = []
                used_drivers: set[UUID] = set()
                used_offers: set[str] = set()
                drivers, offers = (
                    self.repository.table("drivers"),
                    self.repository.table("freight_offers"),
                )
                for plan_id in plan_ids:
                    plan = session.get(PlanRow, plan_id)
                    if plan is None:
                        raise DomainError("NOT_FOUND", 404)
                    errors: list[dict[str, Any]] = []
                    if plan.kind != "optimized":
                        errors.append({"code": "BASELINE_PLAN"})
                    if plan.driver_id in used_drivers or used_offers.intersection(plan.offer_ids):
                        errors.append({"code": "CONFLICTING_PLANS"})
                    driver = session.execute(
                        select(drivers.c.deleted_at).where(drivers.c.id == str(plan.driver_id))
                    ).first()
                    if driver is None or driver[0] is not None:
                        errors.append({"code": "DRIVER_UNAVAILABLE"})
                    if session.scalar(
                        select(AssignmentRow.id).where(
                            AssignmentRow.driver_id == plan.driver_id,
                            AssignmentRow.status == "active",
                        )
                    ):
                        errors.append({"code": "DRIVER_ALREADY_ASSIGNED"})
                    job = session.get(JobRow, plan.job_id)
                    expected = (
                        {
                            offer["id"]: offer["version"]
                            for offer in job.request["snapshot"]["offers"]
                        }
                        if job
                        else {}
                    )
                    for offer_id in plan.offer_ids:
                        actual = session.execute(
                            select(offers.c.status, offers.c.version).where(offers.c.id == offer_id)
                        ).first()
                        if (
                            actual is None
                            or actual.status != "open"
                            or actual.version != expected.get(offer_id)
                        ):
                            errors.append({"code": "OFFER_CHANGED", "offerId": offer_id})
                    if errors:
                        raise DomainError("PLAN_NOT_ASSIGNABLE", errors=errors)
                    used_drivers.add(plan.driver_id)
                    used_offers.update(plan.offer_ids)
                    plans.append((plan, expected))
                created = []
                now = self.clock.now()
                for plan, expected in plans:
                    for offer_id in plan.offer_ids:
                        changed = session.execute(
                            update(offers)
                            .where(
                                offers.c.id == offer_id,
                                offers.c.status == "open",
                                offers.c.version == expected[offer_id],
                            )
                            .values(status="assigned")
                        )
                        if cast(CursorResult[Any], changed).rowcount != 1:
                            raise DomainError(
                                "PLAN_NOT_ASSIGNABLE",
                                errors=[{"code": "OFFER_CHANGED", "offerId": offer_id}],
                            )
                    row = AssignmentRow(
                        id=uuid4(),
                        version=1,
                        created_at=now,
                        updated_at=now,
                        route_plan_id=plan.id,
                        driver_id=plan.driver_id,
                        approved_by=approved_by,
                        approved_at=now,
                        agent_run_id=agent_run_id,
                        status="active",
                    )
                    session.add(row)
                    session.flush()
                    self.audit.record(
                        str(approved_by),
                        "assignment.created",
                        "assignment",
                        str(row.id),
                        {
                            "routePlanId": str(plan.id),
                            "driverId": str(plan.driver_id),
                            "offerIds": plan.offer_ids,
                        },
                        transaction=session,
                    )
                    created.append(self._view(row))
                return created
        except IntegrityError:
            raise DomainError(
                "PLAN_NOT_ASSIGNABLE", errors=[{"code": "CONCURRENT_ASSIGNMENT"}]
            ) from None

    def cancel(self, assignment_id: UUID, actor: UUID) -> None:
        with self._lock, self.repository.session() as session:
            row = session.get(AssignmentRow, assignment_id)
            if row is None or row.status != "active":
                raise DomainError("NOT_FOUND", 404)
            plan = session.get(PlanRow, row.route_plan_id)
            if plan is None:
                raise DomainError("NOT_FOUND", 404)
            offers = self.repository.table("freight_offers")
            session.execute(
                update(offers).where(offers.c.id.in_(plan.offer_ids)).values(status="open")
            )
            row.status, row.updated_at = "cancelled", self.clock.now()
            row.version += 1
            self.audit.record(
                str(actor),
                "assignment.cancelled",
                "assignment",
                str(row.id),
                {"routePlanId": str(plan.id)},
                transaction=session,
            )

    list = list_assignments
