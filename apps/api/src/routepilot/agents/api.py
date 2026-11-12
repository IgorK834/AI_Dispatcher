"""Owner-scoped agent REST endpoints and persisted SSE replay."""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sse_starlette import EventSourceResponse

from routepilot.agents.api_models import (
    Accepted,
    AgentStatus,
    RouteExplanation,
    Run,
    Thread,
    ThreadPage,
)
from routepilot.agents.explanations import ExplanationService
from routepilot.agents.schemas import ExplanationInput, MessageCreate, ResumeInput, ThreadCreate
from routepilot.agents.service import AgentService
from routepilot.shared.auth import Principal
from routepilot.shared.errors import DomainError
from routepilot.shared.pagination import CursorCodec


def thread_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "createdAt": row["created_at"],
        **({"messages": row["messages"], "runs": row["runs"]} if "messages" in row else {}),
    }


def create_agents_router(
    service: AgentService,
    explanations: ExplanationService,
    require_user: Callable[[Request], Principal],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["agents"])
    dependency = Depends(require_user)
    fallback_codec = CursorCodec()

    @router.get("/agent/status", response_model=AgentStatus)
    async def status(user: Annotated[Principal, dependency]) -> dict[str, Any]:
        return service.status(user)

    @router.post("/agent/threads", status_code=201, response_model=Thread)
    async def create_thread(
        body: ThreadCreate, response: Response, user: Annotated[Principal, dependency]
    ) -> dict[str, Any]:
        row = service.create_thread(user, body.title)
        response.headers["Location"] = f"/api/v1/agent/threads/{row['id']}"
        return thread_view(row)

    @router.get("/agent/threads", response_model=ThreadPage)
    async def threads(
        user: Annotated[Principal, dependency],
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        codec = (
            CursorCodec(service.settings.secret_key)
            if service.settings.secret_key
            else fallback_codec
        )
        filters = {"resource": "agent_threads", "user_id": str(user.id)}
        rows = sorted(service.threads(user), key=lambda row: str(row["id"]))
        if cursor:
            after = codec.decode(cursor, filters)
            rows = [row for row in rows if str(row["id"]) > str(after)]
        page = rows[:limit]
        return {
            "items": [thread_view(row) for row in page],
            "nextCursor": codec.encode(str(page[-1]["id"]), filters) if len(rows) > limit else None,
        }

    @router.get("/agent/threads/{thread_id}", response_model=Thread)
    async def thread(thread_id: UUID, user: Annotated[Principal, dependency]) -> dict[str, Any]:
        return thread_view(service.thread(user, thread_id))

    @router.post("/agent/threads/{thread_id}/messages", status_code=202, response_model=Accepted)
    async def message(
        thread_id: UUID,
        body: MessageCreate,
        response: Response,
        user: Annotated[Principal, dependency],
        idempotency_key: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        result = service.message(user, thread_id, body, idempotency_key)
        response.headers["Location"] = f"/api/v1/agent/runs/{result['runId']}"
        return result

    @router.get("/agent/runs/{run_id}", response_model=Run)
    async def run(run_id: UUID, user: Annotated[Principal, dependency]) -> dict[str, Any]:
        return service.get_run(user, run_id)

    @router.post("/agent/runs/{run_id}/resume", status_code=202, response_model=Run)
    async def resume(
        run_id: UUID, body: ResumeInput, user: Annotated[Principal, dependency]
    ) -> dict[str, Any]:
        return service.resume(user, run_id, body)

    @router.get("/agent/runs/{run_id}/events", response_class=EventSourceResponse)
    async def events(
        run_id: UUID,
        request: Request,
        user: Annotated[Principal, dependency],
        last_event_id: Annotated[str | None, Header()] = None,
    ) -> EventSourceResponse:
        service.get_run(user, run_id)
        try:
            after = int(last_event_id or "0")
            if after < 0:
                raise ValueError("Negative event id")
        except ValueError as error:
            raise DomainError("VALIDATION_ERROR", 422) from error

        async def stream() -> AsyncIterator[dict[str, str]]:
            nonlocal after
            idle = 0
            while not await request.is_disconnected():
                stored = service.events(user, run_id, after)
                for event in stored:
                    after = event["id"]
                    yield {
                        "id": str(after),
                        "event": event["event"],
                        "data": json.dumps(event["data"], default=str),
                    }
                    if event["event"] == "run_finished":
                        return
                if not stored and service.get_run(user, run_id)["status"] in {
                    "succeeded",
                    "failed",
                    "cancelled",
                }:
                    return
                idle = 0 if stored else idle + 1
                if idle >= 60:
                    yield {"event": "heartbeat", "data": "{}"}
                    idle = 0
                await asyncio.sleep(0.25)

        return EventSourceResponse(stream(), ping=15)

    @router.post(
        "/route-plans/{plan_id}/explanations", status_code=201, response_model=RouteExplanation
    )
    async def explain(
        plan_id: UUID, body: ExplanationInput, user: Annotated[Principal, dependency]
    ) -> dict[str, Any]:
        return await asyncio.to_thread(explanations.explain, plan_id, body.locale or user.locale)

    return router
