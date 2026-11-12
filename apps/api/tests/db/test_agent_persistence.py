"""Existing-schema agent records and ordered event replay survive adapter rebuilds."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command

from routepilot.agent_persistence import SqlAgentStore
from routepilot.agents.schemas import TraceStep
from routepilot.identity.service import IdentityService
from routepilot.shared.clock import FixedClock
from routepilot.shared.config import Settings
from routepilot.shared.db.engine import make_engine, migration_config


@pytest.mark.ac("AC-FEAT-006-16")
@pytest.mark.ac("AC-FEAT-006-22")
def test_persisted_events_and_trace(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(migration_config(url), "head")
    engine = make_engine(url)
    clock = FixedClock(datetime(2026, 11, 12, tzinfo=UTC))
    identity = IdentityService(engine, Settings(app_env="test", _env_file=None), clock)
    identity.seed_accounts()
    with engine.connect() as connection:
        user_id = UUID(connection.exec_driver_sql("SELECT id FROM users LIMIT 1").scalar_one())
    store = SqlAgentStore(engine, clock)
    thread = store.create(
        "agent_threads",
        {
            "user_id": user_id,
            "title": "Synthetic",
            "created_at": clock.now(),
            "updated_at": clock.now(),
        },
    )
    run = store.create(
        "agent_runs",
        {
            "thread_id": thread["id"],
            "status": "running",
            "user_message": "Question",
            "model_policy": {},
            "tokens_in": 20,
            "tokens_out": 5,
            "cost_estimate_minor": 0,
            "currency": "USD",
            "created_at": clock.now(),
        },
    )
    run_id = UUID(str(run["id"]))
    store.emit(run_id, "run_started", {"runId": str(run_id)})
    step = TraceStep(seq=0, agent="dispatcher", type="llm", inputSummary="Model call")
    step_id = store.start_step(run_id, step)
    step.outputSummary = "Finished"
    store.finish_step(step_id, step)
    rebuilt = SqlAgentStore(engine, clock)
    assert [event["event"] for event in rebuilt.events(run_id)] == [
        "run_started",
        "step_started",
        "step_finished",
    ]
    assert [event["id"] for event in rebuilt.events(run_id, 1)] == [2, 3]
    assert rebuilt.find("agent_steps", run_id=run_id)[0]["seq"] == 1
    assert rebuilt.daily_usage(user_id, "2026-11-12") == 25
    engine.dispose()
