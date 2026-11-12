"""Thread ownership, idempotency, daily limits and approval expiry."""

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from routepilot.agents.schemas import MessageCreate, ResumeInput
from routepilot.agents.service import AgentService
from routepilot.shared.auth import Principal
from routepilot.shared.clock import FixedClock
from routepilot.shared.errors import DomainError
from tests.agents.memory_store import MemoryStore
from tests.agents.test_graph import Tools, scripted_registry


@pytest.mark.ac("AC-FEAT-006-23")
@pytest.mark.ac("AC-FEAT-006-24")
@pytest.mark.ac("AC-FEAT-006-15")
def test_run_service_ownership_idempotency_and_budget(tmp_path: Path) -> None:
    async def scenario() -> None:
        store, registry, tools = MemoryStore(), scripted_registry(), Tools()
        user = Principal(id=uuid4(), role="dispatcher", locale="en", session_id=uuid4())
        other = user.model_copy(update={"id": uuid4()})
        clock = FixedClock(datetime(2026, 11, 12, tzinfo=UTC))
        with sqlite3.connect(tmp_path / "agent.db", check_same_thread=False) as connection:
            service = AgentService(
                store, registry, tools, clock, registry.settings, SqliteSaver(connection)
            )
            thread = service.create_thread(user, None)
            run = service.message(user, thread["id"], MessageCreate(content="Find loads"), "same")
            assert (
                service.message(user, thread["id"], MessageCreate(content="Find loads"), "same")
                == run
            )
            with pytest.raises(DomainError, match="RUN_IN_PROGRESS"):
                service.message(user, thread["id"], MessageCreate(content="Another question"), None)
            await service.wait(run["runId"])
            assert service.get_run(user, run["runId"])["status"] == "waiting_approval"
            with pytest.raises(DomainError, match="NOT_FOUND"):
                service.get_run(other, run["runId"])
            with pytest.raises(DomainError, match="APPROVAL_NOT_PENDING"):
                service.resume(
                    user, run["runId"], ResumeInput(approvalId=uuid4(), decision="approve")
                )
            events = service.events(user, run["runId"])
            assert events[0]["event"] == "run_started"
            assert [event["id"] for event in events] == list(range(1, len(events) + 1))
            approval = store.find("approval_requests", run_id=run["runId"])[0]
            service.resume(
                user, run["runId"], ResumeInput(approvalId=approval["id"], decision="reject")
            )
            await service.wait(run["runId"])
            assert service.events(user, run["runId"])[-1]["event"] == "run_finished"
            assert tools.writes == []
            with pytest.raises(DomainError, match="APPROVAL_NOT_PENDING"):
                service.resume(
                    user, run["runId"], ResumeInput(approvalId=approval["id"], decision="approve")
                )
            store.update("agent_runs", run["runId"], {"tokens_in": 500001})
            with pytest.raises(DomainError, match="AI_BUDGET_EXCEEDED"):
                service.message(user, thread["id"], MessageCreate(content="Next"), None)
            await service.stop()

    asyncio.run(scenario())


@pytest.mark.ac("AC-FEAT-006-23")
def test_pending_approval_expires_without_write(tmp_path: Path) -> None:
    async def scenario() -> None:
        store, registry, tools = MemoryStore(), scripted_registry(), Tools()
        user = Principal(id=uuid4(), role="demo", locale="en", session_id=uuid4())
        clock = FixedClock(datetime(2026, 11, 12, tzinfo=UTC))
        with sqlite3.connect(tmp_path / "agent.db", check_same_thread=False) as connection:
            service = AgentService(
                store, registry, tools, clock, registry.settings, SqliteSaver(connection)
            )
            thread = service.create_thread(user, None)
            run = service.message(user, thread["id"], MessageCreate(content="Find loads"), None)
            await service.wait(run["runId"])
            service.clock = FixedClock(clock.now() + timedelta(minutes=31))
            assert service.get_run(user, run["runId"])["status"] == "cancelled"
            assert store.find("approval_requests")[0]["status"] == "expired"
            assert tools.writes == []
            await service.stop()

    asyncio.run(scenario())
