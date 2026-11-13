"""FEAT-006 FR-26 / OQ-006-06: GET /agent/status shows the AI-enabled rule and daily budget."""

import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver

from routepilot.agents.api import create_agents_router
from routepilot.agents.explanations import ExplanationService
from routepilot.agents.models import ModelPolicy, ModelRegistry
from routepilot.agents.service import AgentService
from routepilot.shared.auth import Principal
from routepilot.shared.clock import FixedClock
from routepilot.shared.config import Settings
from routepilot.shared.errors import DomainError
from routepilot.shared.problem import problem
from tests.agents.fakes import ScriptedModel
from tests.agents.memory_store import MemoryStore
from tests.agents.test_graph import Tools

NOW = datetime(2026, 11, 12, 9, tzinfo=UTC)
NO_KEYS = {"google_api_key": "", "anthropic_api_key": "", "openai_api_key": ""}


@contextmanager
def build_client(
    tmp_path: Path, registry: ModelRegistry, store: MemoryStore, role: str
) -> Iterator[tuple[TestClient, dict[str, str], UUID]]:
    user = Principal.model_validate(
        {"id": uuid4(), "role": role, "locale": "en", "session_id": uuid4()}
    )
    clock = FixedClock(NOW)
    with sqlite3.connect(tmp_path / "agents.db", check_same_thread=False) as connection:
        service = AgentService(
            store, registry, Tools(), clock, registry.settings, SqliteSaver(connection)
        )
        explanations = ExplanationService(store, registry, clock, registry.settings, lambda id: {})

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> Any:
            yield
            await service.stop()

        app = FastAPI(lifespan=lifespan)

        @app.exception_handler(DomainError)
        async def error(request: Request, exc: DomainError) -> Any:
            return problem(request, exc.status, exc.code)

        def require_user(request: Request) -> Principal:
            if request.headers.get("X-Test-User") is None:
                raise DomainError("UNAUTHENTICATED", 401)
            return user

        app.include_router(create_agents_router(service, explanations, require_user))
        with TestClient(app) as client:
            yield client, {"X-Test-User": str(user.id)}, user.id


def disabled_registry() -> ModelRegistry:
    settings = Settings(app_env="test", _env_file=None, **NO_KEYS)
    return ModelRegistry(
        settings, ModelPolicy.model_validate({"default": {"model": "google_genai:fake-model"}})
    )


@pytest.mark.parametrize(("role", "limit"), [("dispatcher", 500_000), ("demo", 100_000)])
def test_status_without_keys_reports_ai_off_and_the_role_budget(
    tmp_path: Path, role: str, limit: int
) -> None:
    store = MemoryStore()
    with build_client(tmp_path, disabled_registry(), store, role) as (client, headers, user_id):
        assert client.get("/api/v1/agent/status").status_code == 401
        # Usage of today (UTC) counts; usage of another day does not.
        thread = store.create("agent_threads", {"user_id": user_id})
        for created_at, used in [(NOW, 700), (datetime(2026, 11, 11, 23, tzinfo=UTC), 9_999)]:
            store.create(
                "agent_runs",
                {
                    "thread_id": thread["id"],
                    "created_at": created_at,
                    "tokens_in": used - 100,
                    "tokens_out": 100,
                },
            )
        body = client.get("/api/v1/agent/status", headers=headers).json()
        assert body == {
            "aiEnabled": False,
            "reason": "AI_UNAVAILABLE",
            "dailyBudget": {"usedTokens": 700, "limitTokens": limit},
        }


def test_status_with_a_dispatcher_provider_key_reports_ai_on(tmp_path: Path) -> None:
    name = "google_genai:fake-model"
    settings = Settings(app_env="test", _env_file=None, **{**NO_KEYS, "google_api_key": "k"})
    registry = ModelRegistry(
        settings,
        ModelPolicy.model_validate({"default": {"model": name}}),
        {name: lambda: ScriptedModel(script=[])},
    )
    with build_client(tmp_path, registry, MemoryStore(), "dispatcher") as (client, headers, _):
        body = client.get("/api/v1/agent/status", headers=headers).json()
        assert body["aiEnabled"] is True and body["reason"] is None
        assert body["dailyBudget"] == {"usedTokens": 0, "limitTokens": 500_000}
