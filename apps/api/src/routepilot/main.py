"""Application composition, health endpoints and middleware."""

import asyncio
import secrets
import sqlite3
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal
from uuid import uuid4

import structlog
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import JSON, Column, MetaData, Table, Text, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import Response

from routepilot.agent_persistence import SqlAgentStore
from routepilot.agents.api import create_agents_router
from routepilot.agents.explanations import ExplanationService
from routepilot.agents.models import ModelRegistry
from routepilot.agents.service import AgentService
from routepilot.agents.tools import ToolRegistry
from routepilot.bootstrap import DemoDataService, GenerateInput
from routepilot.fleet.api.routes import create_fleet_router
from routepilot.fleet.service import FleetService
from routepilot.freight.api.routes import create_freight_router
from routepilot.freight.geocoding import city_table
from routepilot.freight.service import FreightService, ImportService, OfferQueryService
from routepilot.identity.api.routes import create_identity_router, require_role, require_user
from routepilot.identity.ports import CaptchaVerifier
from routepilot.identity.service import IdentityService
from routepilot.integrations.timocom.mapper import TimocomV3Mapper
from routepilot.optimization.jobs.api import create_jobs_router
from routepilot.optimization.jobs.service import AssignmentService, JobService, PlanService
from routepilot.routing.cache import RoutingCache
from routepilot.routing.composite import CompositeRoutingProvider
from routepilot.routing.haversine import HaversineRoutingProvider
from routepilot.routing.matrix_file import MatrixFileRoutingProvider
from routepilot.routing.ors import OrsRoutingProvider
from routepilot.shared.auth import Principal
from routepilot.shared.clock import Clock, SystemClock
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import make_engine, migration_config
from routepilot.shared.db.types import UtcDateTime
from routepilot.shared.errors import DomainError
from routepilot.shared.logging import configure_logging
from routepilot.shared.pagination import CursorCodec
from routepilot.shared.problem import Problem, problem


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ready"]
    migration: str


def create_app(
    settings: Settings | None = None,
    *,
    clock: Clock | None = None,
    model_registry: ModelRegistry | None = None,
    captcha: CaptchaVerifier | None = None,
) -> FastAPI:
    settings = settings or Settings()
    if settings.app_env != "test" and (model_registry is not None or captcha is not None):
        raise ValueError("Injected model and captcha adapters are test-only")
    clock = clock or SystemClock()
    configure_logging()
    logger = structlog.get_logger()
    engine = make_engine(settings.database_url)
    scripts = ScriptDirectory.from_config(migration_config(settings.database_url))

    identity = IdentityService(engine, settings, clock, captcha)
    assignments = AssignmentService(engine, clock, identity.audit)
    fleet = FleetService(engine, clock, identity.audit, assignments, settings.secret_key)
    freight = FreightService(engine, clock, identity.audit, settings.secret_key)
    imports = ImportService(engine, clock, TimocomV3Mapper(), identity.audit)
    offers = OfferQueryService(freight, fx_rates={"PLN": Decimal("4.25")})
    repository_root = Path(__file__).resolve().parents[4]
    matrix_path = Path(settings.routing_matrix_path)
    if not matrix_path.is_absolute() and not matrix_path.exists():
        matrix_path = repository_root / matrix_path
    routing = CompositeRoutingProvider(
        MatrixFileRoutingProvider(
            matrix_path, cities=city_table()["cities"], van_speed_factor=settings.van_speed_factor
        ),
        OrsRoutingProvider(
            api_key=settings.ors_api_key,
            cache=RoutingCache(engine, clock),
            base_url=settings.ors_base_url,
            van_speed_factor=settings.van_speed_factor,
        ),
        HaversineRoutingProvider(settings.van_speed_factor),
    )
    jobs = JobService(
        engine,
        clock,
        routing,
        poll_interval_ms=settings.worker_poll_interval_ms,
        heartbeat_stale_s=settings.job_heartbeat_stale_s,
    )
    plans = PlanService(engine, clock, routing)
    demo_data = DemoDataService(engine, clock, settings, fleet, imports, identity.audit)
    registry = model_registry or ModelRegistry(settings)
    store = SqlAgentStore(engine, clock)
    agents_path = Path(settings.agents_db_path)
    agents_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_connection = sqlite3.connect(str(agents_path), check_same_thread=False)
    from langgraph.checkpoint.sqlite import SqliteSaver

    checkpointer = SqliteSaver(checkpoint_connection)
    tools = ToolRegistry(
        fleet=fleet, freight=freight, offers=offers, jobs=jobs, plans=plans, assignments=assignments
    )
    explanations = ExplanationService(store, registry, clock, settings, tools.explanation_facts)
    tools.explain_callback = explanations.explain
    agents = AgentService(store, registry, tools, clock, settings, checkpointer)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if settings.app_env == "local" and not settings.secret_key:
            if inspect(engine).has_table("app_meta"):
                meta = Table(
                    "app_meta",
                    MetaData(),
                    Column("key", Text, primary_key=True),
                    Column("value", JSON),
                    Column("updated_at", UtcDateTime()),
                )
                with engine.begin() as connection:
                    stored = connection.execute(
                        select(meta.c.value).where(meta.c.key == "secret_key")
                    ).scalar_one_or_none()
                    settings.secret_key = str(stored) if stored else secrets.token_urlsafe(48)
                    if not stored:
                        connection.execute(
                            meta.insert().values(
                                key="secret_key",
                                value=settings.secret_key,
                                updated_at=clock.now(),
                            )
                        )
            else:
                settings.secret_key = secrets.token_urlsafe(48)
                logger.warning("local_secret_in_memory_until_migrations_applied")
        fleet.cursors = CursorCodec(settings.secret_key)
        freight.cursors = CursorCodec(settings.secret_key)
        assignments.cursors = CursorCodec(settings.secret_key)
        migrated = inspect(engine).has_table("app_meta")
        if migrated:
            identity.seed_accounts()
            demo_data.ensure_seed()
            checkpointer.setup()
            tools.loop = asyncio.get_running_loop()
            await jobs.start()
        try:
            yield
        finally:
            await agents.stop()
            if migrated:
                await jobs.stop()
            identity.close()
            checkpoint_connection.close()
            engine.dispose()

    application = FastAPI(title="RoutePilot AI", version="0.1.0", lifespan=lifespan)

    application.state.engine = engine
    application.state.services = SimpleNamespace(
        identity=identity,
        fleet=fleet,
        freight=freight,
        imports=imports,
        offers=offers,
        jobs=jobs,
        plans=plans,
        assignments=assignments,
        routing=routing,
        registry=registry,
        store=store,
        demo_data=demo_data,
        tools=tools,
        agents=agents,
        explanations=explanations,
    )
    user_dependency = require_user(identity)
    admin_dependency = require_role(identity, "admin")
    application.include_router(create_identity_router(identity, settings))
    application.include_router(create_fleet_router(fleet, user_dependency, admin_dependency))
    application.include_router(create_freight_router(freight, user_dependency))
    application.include_router(create_jobs_router(jobs, plans, assignments, user_dependency))
    application.include_router(create_agents_router(agents, explanations, user_dependency))

    admin = Depends(admin_dependency)

    @application.post("/api/v1/admin/demo-data/generate", tags=["admin"])
    async def generate_demo_data(body: GenerateInput, actor: Principal = admin) -> dict[str, Any]:
        return demo_data.generate(body, str(actor.id))

    @application.post("/api/v1/admin/demo-data/reset", tags=["admin"])
    async def reset_demo_data(actor: Principal = admin) -> dict[str, Any]:
        await agents.stop()
        await jobs.stop()
        try:
            checkpoint_connection.execute("DELETE FROM writes")
            checkpoint_connection.execute("DELETE FROM checkpoints")
            checkpoint_connection.commit()
            return demo_data.reset(str(actor.id))
        finally:
            await jobs.start()

    @application.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
        tokens = structlog.contextvars.bind_contextvars(request_id=request.state.request_id)
        try:
            try:
                if (
                    request.url.path.startswith("/api/v1/")
                    and request.method in {"POST", "PATCH", "PUT", "DELETE"}
                    and request.url.path != "/api/v1/auth/login"
                ):
                    if request.headers.get("Origin") not in settings.origins:
                        raise DomainError("ORIGIN_NOT_ALLOWED", 403)
                    principal = identity.require_user(request.cookies.get("rp_session"))
                    identity.validate_csrf(
                        principal,
                        request.cookies.get("rp_csrf"),
                        request.headers.get("X-CSRF-Token"),
                    )
                response = await call_next(request)
            except DomainError as error:
                response = problem(
                    request, error.status, error.code, headers=error.headers, errors=error.errors
                )
            except Exception:
                logger.error("request_failed", exc_info=settings.app_env == "local")
                response = problem(request, 500, "INTERNAL_ERROR")
            response.headers["X-Request-ID"] = request.state.request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
                "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
                "img-src 'self' data:; frame-ancestors 'none'"
                if request.url.path in {"/docs", "/redoc"}
                else "default-src 'none'; frame-ancestors 'none'"
            )
            logger.info(
                "request_finished",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
            )
            return response
        finally:
            structlog.contextvars.reset_contextvars(**tokens)

    @application.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError) -> JSONResponse:
        return problem(
            request, error.status, error.code, errors=error.errors, headers=error.headers
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        return problem(
            request,
            422,
            "VALIDATION_ERROR",
            errors=[
                {
                    "field": ".".join(str(part) for part in detail["loc"]),
                    "message": "Invalid value",
                    "code": str(detail["type"]),
                }
                for detail in error.errors()
            ],
        )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        response = problem(
            request, error.status_code, "NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR"
        )
        response.headers.update(error.headers or {})
        return response

    @application.get("/health", operation_id="health", response_model=HealthResponse)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get(
        "/ready",
        operation_id="ready",
        response_model=ReadyResponse,
        responses={
            503: {
                "description": "Database is not ready",
                "content": {
                    "application/problem+json": {"schema": Problem.model_json_schema(by_alias=True)}
                },
            }
        },
    )
    def ready(request: Request) -> Response:
        try:
            with engine.connect() as connection:
                heads = MigrationContext.configure(connection).get_current_heads()
            if set(heads) != set(scripts.get_heads()):
                return problem(request, 503, "NOT_READY")
        except SQLAlchemyError:
            return problem(request, 503, "NOT_READY")
        return JSONResponse({"status": "ready", "migration": heads[0] if heads else "base"})

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Idempotency-Key", "X-CSRF-Token", "X-Request-ID"],
    )
    return application


app = create_app()
