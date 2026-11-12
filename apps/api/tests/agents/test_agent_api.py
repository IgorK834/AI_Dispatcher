"""HTTP contracts, anonymous/foreign ownership and complete SSE replay."""

import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver

from routepilot.agents.api import create_agents_router
from routepilot.agents.api_models import EVENT_SCHEMAS
from routepilot.agents.explanations import ExplanationService
from routepilot.agents.service import AgentService
from routepilot.shared.auth import Principal
from routepilot.shared.clock import FixedClock
from routepilot.shared.errors import DomainError
from routepilot.shared.problem import problem
from tests.agents.memory_store import MemoryStore
from tests.agents.test_graph import Tools, scripted_registry


def parse_events(text: str) -> list[dict[str, Any]]:
    events = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        fields = dict(
            line.split(": ", 1)
            for line in block.splitlines()
            if ": " in line and not line.startswith(":")
        )
        if "event" in fields:
            events.append(
                {
                    "id": int(fields["id"]),
                    "event": fields["event"],
                    "data": json.loads(fields["data"]),
                }
            )
    return events


@pytest.mark.ac("AC-FEAT-006-15")
@pytest.mark.ac("AC-FEAT-006-16")
@pytest.mark.ac("AC-FEAT-006-23")
def test_agent_http_contract_and_sse_replay(tmp_path: Path) -> None:
    registry, tools, store = scripted_registry(), Tools(), MemoryStore()
    clock = FixedClock(datetime(2026, 11, 12, tzinfo=UTC))
    user = Principal(id=uuid4(), role="dispatcher", locale="en", session_id=uuid4())
    with sqlite3.connect(tmp_path / "agent.db", check_same_thread=False) as connection:
        service = AgentService(
            store, registry, tools, clock, registry.settings, SqliteSaver(connection)
        )
        explanations = ExplanationService(
            store, registry, clock, registry.settings, lambda id: {"plan_ref": "PLAN-1a2b3c4d"}
        )

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> Any:
            yield
            await service.stop()

        app = FastAPI(lifespan=lifespan)

        @app.exception_handler(DomainError)
        async def error(request: Request, exc: DomainError) -> Any:
            return problem(request, exc.status, exc.code)

        def require_user(request: Request) -> Principal:
            id = request.headers.get("X-Test-User")
            if id is None:
                raise DomainError("UNAUTHENTICATED", 401)
            return user.model_copy(update={"id": UUID(id)})

        app.include_router(create_agents_router(service, explanations, require_user))
        headers = {"X-Test-User": str(user.id)}
        with TestClient(app) as client:
            assert client.get("/api/v1/agent/status").status_code == 401
            assert client.get("/api/v1/agent/status", headers=headers).json()["aiEnabled"]
            created = client.post("/api/v1/agent/threads", json={}, headers=headers)
            assert created.status_code == 201
            path = created.headers["Location"]
            assert client.get(path, headers={"X-Test-User": str(uuid4())}).status_code == 404
            accepted = client.post(
                path + "/messages", json={"content": "Find loads"}, headers=headers
            )
            assert accepted.status_code == 202
            run_id = UUID(accepted.json()["runId"])
            client.portal.call(service.wait, run_id)
            run_path = accepted.headers["Location"]
            pending = client.get(run_path, headers=headers).json()
            assert pending["status"] == "waiting_approval"
            resumed = client.post(
                run_path + "/resume",
                json={"approvalId": pending["pendingApproval"]["approvalId"], "decision": "reject"},
                headers=headers,
            )
            assert resumed.status_code == 202
            client.portal.call(service.wait, run_id)
            events = parse_events(client.get(run_path + "/events", headers=headers).text)
            assert events[0]["event"] == "run_started"
            assert events[-1]["event"] == "run_finished"
            assert [event["id"] for event in events] == list(range(1, len(events) + 1))
            for event in events:
                EVENT_SCHEMAS[event["event"]].model_validate(event["data"])
            assert {e["data"]["seq"] for e in events if e["event"] == "step_started"} == {
                e["data"]["seq"] for e in events if e["event"] == "step_finished"
            }
            replay = parse_events(
                client.get(run_path + "/events", headers={**headers, "Last-Event-ID": "4"}).text
            )
            assert replay == events[4:]
            assert (
                client.get(
                    run_path + "/events", headers={**headers, "Last-Event-ID": "bad"}
                ).status_code
                == 422
            )
            assert (
                client.get("/api/v1/agent/threads?limit=1", headers=headers).json()["items"][0][
                    "id"
                ]
                == created.json()["id"]
            )
