"""A waiting run survives a restart: graph and checkpointer are rebuilt from the same agents.db."""

import sqlite3
from pathlib import Path

import pytest

from tests.agents.conftest import ToolEnv
from tests.agents.scenario import (
    DynamicModel,
    Scenario,
    decision,
    dispatcher_script,
    final_answer,
    request_approval,
    specialist_models,
)
from tests.agents.test_graph_flow import demo_scenario


def tables(path: Path) -> set[str]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {name for (name,) in rows}


@pytest.mark.ac("AC-FEAT-006-07")
def test_resume_after_rebuilding_graph_and_checkpointer_completes_the_run(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path
) -> None:
    run = demo_scenario(worker_env, tmp_path)
    first = run.start()
    assert first.waiting and run.assignments() == []
    # The first "process" is gone: only the checkpoint file and the database remain.
    checkpoint_file = tmp_path / "agents.db"
    assert {"checkpoints", "writes"} <= tables(checkpoint_file)
    plans = run.pending()["payload"]["plans"]
    outcome = run.decide("approve")
    assert not outcome.waiting, "the run continued from the interrupt and completed"
    assert outcome.state["final_answer"]["source"] == "llm"
    assert outcome.state["assigned"] is True
    assert len(run.assignments()) == len(plans)
    # The work before the interrupt was not repeated after the restart.
    llm_agents = [step["agent"] for step in run.steps() if step["type"] == "llm"]
    assert llm_agents.count("route_planner") == 2 and llm_agents.count("fleet_compliance") == 2


@pytest.mark.ac("AC-FEAT-006-07")
def test_checkpoints_live_in_their_own_file_not_in_the_application_database(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path
) -> None:
    run = demo_scenario(worker_env, tmp_path)
    run.start()
    application_tables = (
        set(worker_env.freight.engine.table_names())
        if hasattr(worker_env.freight.engine, "table_names")
        else set()
    )
    with worker_env.freight.engine.connect() as connection:
        application_tables = {
            name
            for (name,) in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert "checkpoints" not in application_tables and "approval_requests" in application_tables
    assert "approval_requests" not in tables(tmp_path / "agents.db")


@pytest.mark.ac("AC-FEAT-006-07")
def test_a_rejected_run_also_resumes_after_a_restart(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path
) -> None:
    models = specialist_models(worker_env)
    models["dispatcher"] = DynamicModel(
        script=[
            *dispatcher_script(request_approval(), decision("approve"), decision("finish")),
            final_answer,
        ]
    )
    run = Scenario(worker_env, tmp_path / "agents.db", models)
    assert run.start().waiting
    outcome = run.decide("reject", "Not today")
    assert not outcome.waiting and run.assignments() == []
