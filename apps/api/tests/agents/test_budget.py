"""BudgetGuard through the whole run: step, tool-call, token and time limits, daily usage.

Every run goes through `AgentService` (so the stored run status and error are the ones a client
sees) on scripted fake models; the limits are set on the settings of the registry.
"""

import asyncio
import sqlite3
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langgraph.checkpoint.sqlite import SqliteSaver

from routepilot.agent_persistence import SqlAgentStore
from routepilot.agents.models import ModelPolicy, ModelRegistry
from routepilot.agents.schemas import MessageCreate, ResumeInput
from routepilot.agents.service import AgentService
from routepilot.identity.service import IdentityService
from routepilot.shared.auth import Principal
from routepilot.shared.clock import FixedClock
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import make_engine, migration_config
from tests.agents.fakes import ScriptedModel, response
from tests.agents.memory_store import MemoryStore
from tests.agents.test_graph import Tools, decision, scripted_registry

NOW = datetime(2026, 11, 12, 8, tzinfo=UTC)
FLEET_REPORT = response(tool="FleetReport", args={"drivers": [], "warnings": []})


def registry_of(models: dict[str, ScriptedModel], **limits: Any) -> ModelRegistry:
    policy = ModelPolicy.model_validate(
        {role: {"model": f"fake:{role}", "maxTokens": 30} for role in models}
    )
    return ModelRegistry(
        Settings(app_env="test", _env_file=None, **limits),
        policy,
        {f"fake:{role}": lambda model=model: model for role, model in models.items()},
    )


def looping_models() -> dict[str, ScriptedModel]:
    """A Dispatcher that keeps asking the Fleet agent, which keeps answering: it never ends."""
    return {
        "dispatcher": ScriptedModel(script=[decision("fleet_compliance")] * 40),
        "fleet_compliance": ScriptedModel(
            script=[response(tool="list_drivers"), FLEET_REPORT] * 40
        ),
    }


class Harness:
    """One `AgentService` on an in-memory store; `ask` posts a message and waits for the run."""

    def __init__(self, registry: ModelRegistry, path: Path, role: str = "dispatcher") -> None:
        self.store = MemoryStore()
        self.tools = Tools()
        self.registry = registry
        self.user = Principal(id=uuid4(), role=role, locale="en", session_id=uuid4())  # type: ignore[arg-type]
        self.connection = sqlite3.connect(path / "agent.db", check_same_thread=False)
        self.service = AgentService(
            self.store,
            registry,
            self.tools,
            FixedClock(NOW),
            registry.settings,
            SqliteSaver(self.connection),
        )
        self.thread = self.service.create_thread(self.user, None)

    def post(self, text: str = "Find loads") -> UUID:
        run = self.service.message(self.user, self.thread["id"], MessageCreate(content=text), None)
        return UUID(str(run["runId"]))

    async def finish(self, run_id: UUID, patience: float = 30) -> dict[str, Any]:
        await asyncio.wait_for(self.service.wait(run_id), patience)
        return self.service.get_run(self.user, run_id)

    def steps(self, run_id: UUID) -> list[dict[str, Any]]:
        return self.store.find("agent_steps", run_id=run_id)

    def guard_reasons(self, run_id: UUID) -> list[str]:
        """The reasons of the guard steps that stopped the run (status "rejected")."""
        return [
            step["outputSummary"]
            for step in self.steps(run_id)
            if step["type"] == "guard" and step["status"] == "rejected"
        ]

    async def close(self) -> None:
        await self.service.stop()
        self.connection.close()


def calls_of(models: dict[str, ScriptedModel]) -> int:
    return sum(len(model.recorded) for model in models.values())


@pytest.mark.ac("AC-FEAT-006-11")
def test_step_limit_stops_a_looping_run_without_a_recommendation(tmp_path: Path) -> None:
    async def scenario() -> None:
        models = looping_models()
        harness = Harness(registry_of(models, agent_recursion_limit=5), tmp_path)
        run_id = harness.post()
        run = await harness.finish(run_id)
        assert run["status"] == "failed"
        assert run["error"]["code"] == "BUDGET_EXCEEDED"
        assert run["finalAnswer"]["source"] == "template"
        assert run["finalAnswer"]["proposals"] == []
        assert harness.guard_reasons(run_id) == ["STEP_LIMIT"]
        assert calls_of(models) == 5  # the limit is honoured exactly, not exceeded
        events = harness.store.events(run_id)
        assert events[-1]["event"] == "run_finished"
        assert events[-1]["data"]["error"]["code"] == "BUDGET_EXCEEDED"
        await harness.close()

    asyncio.run(scenario())


@pytest.mark.ac("AC-FEAT-006-11")
def test_step_limit_after_a_recommendation_ends_with_a_template_answer(tmp_path: Path) -> None:
    async def scenario() -> None:
        # The scripted flow needs 9 model calls up to the validated plan; the 10th is refused.
        registry = scripted_registry()
        registry.settings.agent_recursion_limit = 9
        harness = Harness(registry, tmp_path)
        run_id = harness.post()
        run = await harness.finish(run_id)
        assert run["status"] == "succeeded"
        assert run["error"]["code"] == "BUDGET_EXCEEDED"
        answer = run["finalAnswer"]
        assert answer["source"] == "template"
        assert [item["planRef"] for item in answer["proposals"]] == ["PLAN-1a2b3c4d"]
        assert "323.54" in answer["summary"]
        assert harness.guard_reasons(run_id) == ["STEP_LIMIT"]
        assert harness.tools.writes == []
        await harness.close()

    asyncio.run(scenario())


@pytest.mark.ac("AC-FEAT-006-11")
def test_tool_call_limit_per_agent_stops_the_run_with_a_guard_step(tmp_path: Path) -> None:
    async def scenario() -> None:
        models = {
            "dispatcher": ScriptedModel(script=[decision("freight_scout")] * 10),
            "freight_scout": ScriptedModel(script=[response(tool="search_offers")] * 10),
        }
        harness = Harness(registry_of(models, agent_max_tool_calls=2), tmp_path)
        run_id = harness.post()
        run = await harness.finish(run_id)
        assert run["status"] == "failed"
        assert run["error"]["code"] == "BUDGET_EXCEEDED"
        assert run["finalAnswer"]["source"] == "template"
        tools = [step for step in harness.steps(run_id) if step["type"] == "tool"]
        assert len(tools) == 2  # the third call is refused before it runs
        assert harness.guard_reasons(run_id) == ["TOOL_CALL_LIMIT"]
        await harness.close()

    asyncio.run(scenario())


@pytest.mark.ac("AC-FEAT-006-11")
def test_run_token_budget_below_the_scripted_usage_stops_the_run(tmp_path: Path) -> None:
    async def scenario() -> None:
        # One call reserves 55 tokens (20 counted + 5 margin + 30 output cap) and uses 25.
        models = looping_models()
        harness = Harness(registry_of(models, agent_run_token_budget=100), tmp_path)
        run_id = harness.post()
        run = await harness.finish(run_id)
        assert run["status"] == "failed"
        assert run["error"]["code"] == "BUDGET_EXCEEDED"
        assert run["finalAnswer"]["source"] == "template"
        assert harness.guard_reasons(run_id) == ["TOKEN_BUDGET"]
        assert calls_of(models) == 2  # the third request is never sent
        assert run["tokensIn"] + run["tokensOut"] <= 100
        await harness.close()

    asyncio.run(scenario())


class BlockingModel(ScriptedModel):
    """A model that does not answer until the test lets it."""

    entered: threading.Event
    release: threading.Event

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> ChatResult:
        self.entered.set()
        self.release.wait(30)
        return super()._generate(messages, *args, **kwargs)


@pytest.mark.ac("AC-FEAT-006-12")
def test_a_model_that_blocks_past_the_timeout_ends_the_run_with_budget_exceeded(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        model = BlockingModel(
            script=[decision("fleet_compliance")],
            entered=threading.Event(),
            release=threading.Event(),
        )
        harness = Harness(registry_of({"dispatcher": model}, agent_run_timeout_s=1), tmp_path)
        run_id = harness.post()
        started = time.monotonic()
        try:
            run = await harness.finish(run_id, patience=10)
            elapsed = time.monotonic() - started
            assert model.entered.is_set()
            assert 1 <= elapsed < 4  # the timeout plus a small margin, not the model's 30 s
            assert run["status"] == "failed"
            assert run["error"]["code"] == "BUDGET_EXCEEDED"
            assert run["finalAnswer"]["source"] == "template"
            events = harness.store.events(run_id)
            assert events[-1]["event"] == "run_finished"
            assert events[-1]["data"]["error"]["code"] == "BUDGET_EXCEEDED"
            ended = len(events)
        finally:
            model.release.set()  # let the abandoned worker thread finish
        # The abandoned worker must not write anything after `run_finished`.
        await asyncio.sleep(1.5)
        after = harness.store.events(run_id)
        assert len(after) == ended
        assert after[-1]["event"] == "run_finished"
        assert harness.service.get_run(harness.user, run_id)["status"] == "failed"
        await harness.close()

    asyncio.run(scenario())


@pytest.mark.ac("AC-FEAT-006-12")
def test_time_waiting_for_approval_does_not_count_against_the_timeout(tmp_path: Path) -> None:
    async def scenario() -> None:
        registry = scripted_registry()
        registry.settings.agent_run_timeout_s = 1
        harness = Harness(registry, tmp_path)
        run_id = harness.post()
        run = await harness.finish(run_id)
        assert run["status"] == "waiting_approval"
        await asyncio.sleep(1.6)  # longer than the whole run timeout
        approval = harness.store.find("approval_requests", run_id=run_id)[0]
        harness.service.resume(
            harness.user, run_id, ResumeInput(approvalId=approval["id"], decision="reject")
        )
        run = await harness.finish(run_id)
        assert run["status"] == "succeeded"
        assert run["error"] is None
        assert run["finalAnswer"] is not None
        assert harness.guard_reasons(run_id) == []
        assert harness.tools.writes == []
        await harness.close()

    asyncio.run(scenario())


@pytest.mark.ac("AC-FEAT-006-11")
def test_daily_usage_is_summed_per_user_and_utc_day_in_the_sql_store(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'app.db'}"
    from alembic import command

    command.upgrade(migration_config(url), "head")
    engine = make_engine(url)
    clock = FixedClock(NOW)
    IdentityService(engine, Settings(app_env="test", _env_file=None), clock).seed_accounts()
    with engine.connect() as connection:
        users = [UUID(row[0]) for row in connection.exec_driver_sql("SELECT id FROM users")]
    assert len(users) >= 2
    store = SqlAgentStore(engine, clock)

    def run_for(user: UUID, day: datetime, tokens_in: int, tokens_out: int) -> None:
        thread = store.create(
            "agent_threads",
            {"user_id": user, "title": "Synthetic", "created_at": day, "updated_at": day},
        )
        store.create(
            "agent_runs",
            {
                "thread_id": thread["id"],
                "status": "succeeded",
                "user_message": "Question",
                "model_policy": {},
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_estimate_minor": 0,
                "currency": "USD",
                "created_at": day,
            },
        )

    first, second = users[0], users[1]
    run_for(first, NOW, 20, 5)
    run_for(first, NOW + timedelta(hours=10), 30, 7)
    run_for(first, NOW - timedelta(days=1), 1000, 1000)  # yesterday: not counted
    run_for(second, NOW, 700, 300)  # another user: not counted
    assert store.daily_usage(first, "2026-11-12") == 62
    assert store.daily_usage(second, "2026-11-12") == 1000
    assert store.daily_usage(first, "2026-11-11") == 2000
    assert store.daily_usage(first, "2026-11-13") == 0
    engine.dispose()


@pytest.mark.ac("AC-FEAT-006-11")
def test_status_reports_usage_against_the_limit_of_the_role(tmp_path: Path) -> None:
    registry = scripted_registry()
    for role, limit in (("dispatcher", 500000), ("demo", 100000), ("admin", 500000)):
        harness = Harness(
            registry, tmp_path / role if (tmp_path / role).mkdir() is None else tmp_path, role
        )
        thread = harness.thread
        harness.store.create(
            "agent_runs",
            {
                "thread_id": thread["id"],
                "status": "succeeded",
                "tokens_in": 60,
                "tokens_out": 15,
                "created_at": NOW,
            },
        )
        status = harness.service.status(harness.user)
        assert status["dailyBudget"] == {"usedTokens": 75, "limitTokens": limit}
        harness.connection.close()


@pytest.mark.ac("AC-FEAT-006-11")
@pytest.mark.parametrize("limit", [10, 11])
def test_a_limit_reached_at_the_approval_gate_ends_the_run_gracefully(
    tmp_path: Path, limit: int
) -> None:
    """A real model needs many steps before it asks for approval; if the step limit is reached
    exactly there, the run ends with a template answer and BUDGET_EXCEEDED, not INTERNAL_ERROR."""

    async def scenario() -> None:
        registry = scripted_registry()
        registry.settings.agent_recursion_limit = limit
        harness = Harness(registry, tmp_path)
        run_id = harness.post()
        run = await harness.finish(run_id)
        assert run["status"] == "succeeded", run  # a validated plan exists, so the answer stands
        assert run["error"]["code"] == "BUDGET_EXCEEDED"
        assert run["finalAnswer"]["source"] == "template"
        assert [item["planRef"] for item in run["finalAnswer"]["proposals"]] == ["PLAN-1a2b3c4d"]
        assert harness.guard_reasons(run_id) == ["STEP_LIMIT"]
        assert harness.store.find("approval_requests", run_id=run_id) == []
        assert harness.tools.writes == []
        await harness.close()

    asyncio.run(scenario())
