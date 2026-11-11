"""Application composition, health endpoints and middleware."""

import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Literal
from uuid import uuid4

import structlog
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import JSON, Column, MetaData, Table, Text, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import Response

from routepilot.shared.clock import SystemClock
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import make_engine, migration_config
from routepilot.shared.db.types import UtcDateTime
from routepilot.shared.errors import DomainError
from routepilot.shared.logging import configure_logging
from routepilot.shared.problem import Problem, problem


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ready"]
    migration: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging()
    logger = structlog.get_logger()
    engine = make_engine(settings.database_url)
    scripts = ScriptDirectory.from_config(migration_config(settings.database_url))

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
                                updated_at=SystemClock().now(),
                            )
                        )
            else:
                settings.secret_key = secrets.token_urlsafe(48)
                logger.warning("local_secret_in_memory_until_migrations_applied")
        yield
        engine.dispose()

    application = FastAPI(title="RoutePilot AI", version="0.1.0", lifespan=lifespan)

    @application.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
        tokens = structlog.contextvars.bind_contextvars(request_id=request.state.request_id)
        try:
            try:
                response = await call_next(request)
            except Exception:
                logger.error("request_failed", exc_info=settings.app_env == "local")
                response = problem(request, 500, "INTERNAL_ERROR")
            response.headers["X-Request-ID"] = request.state.request_id
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
