"""A tool call outside the caller's allowlist is not run, is traced as rejected, and is answered."""

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.messages import ToolMessage
from sqlalchemy import func, select

from routepilot.optimization.jobs.repository import JobRow
from tests.agents.conftest import ToolEnv
from tests.agents.fakes import response
from tests.agents.scenario import DynamicModel, Scenario, decision, final_answer, specialist_models

ASSIGN = {"plan_id": str(uuid4()), "approval_id": str(uuid4())}
REPORTS: dict[str, tuple[str, dict[str, Any]]] = {
    "fleet_compliance": ("FleetReport", {"drivers": [], "warnings": []}),
    "freight_scout": (
        "ScoutReport",
        {"candidate_offer_ids": [], "excluded": [], "data_issues": [], "notes": "none"},
    ),
    "route_planner": (
        "PlannerReport",
        {"recommended": None, "alternatives": [], "tradeoffs": [], "baseline_uplift": None},
    ),
}


def rejected(run: Scenario, agent: str) -> list[dict[str, Any]]:
    return [
        step
        for step in run.steps()
        if step["agent"] == agent and step["type"] == "tool" and step["status"] == "rejected"
    ]


def tool_replies(model: Any) -> list[str]:
    """The tool results this model received, as text, over all of its calls."""
    seen: list[str] = []
    for messages in model.recorded:
        seen.extend(str(m.content) for m in messages if isinstance(m, ToolMessage))
    return seen


def job_count(env: ToolEnv) -> int:
    with env.jobs.repository.session() as session:
        return int(session.scalar(select(func.count()).select_from(JobRow)) or 0)


@pytest.mark.ac("AC-FEAT-006-02")
def test_freight_scout_calling_optimize_fleet_is_rejected_and_never_executed(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path
) -> None:
    models = specialist_models(
        worker_env, scout_calls=[response(tool="optimize_fleet", args={"offer_ids": []})]
    )
    models["dispatcher"] = DynamicModel(
        script=[decision("freight_scout"), decision("finish"), final_answer]
    )
    run = Scenario(worker_env, tmp_path / "agents.db", models)
    outcome = run.start()
    (step,) = rejected(run, "freight_scout")
    assert step["tool_name"] == "optimize_fleet" and step["status"] == "rejected"
    # The tool did not run: no optimisation job exists and the Scout got an error, not a result.
    assert job_count(worker_env) == 0
    replies = tool_replies(models["freight_scout"])
    assert len(replies) == 1 and json.loads(replies[0])["error"]["code"] == "TOOL_NOT_ALLOWED"
    assert outcome.state["scout_report"]["notes"] == "Synthetic offers"
    assert not outcome.state["plan_facts"]


@pytest.mark.ac("AC-FEAT-006-02")
@pytest.mark.parametrize(
    "role", ["dispatcher", "fleet_compliance", "freight_scout", "route_planner"]
)
def test_a_model_calling_assign_plan_is_rejected_and_nothing_is_written(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path, role: str
) -> None:
    models = specialist_models(worker_env)
    attempt = response(tool="assign_plan", args=ASSIGN)
    if role == "dispatcher":
        script = [attempt, decision("finish"), final_answer]
    else:
        report, args = REPORTS[role]
        models[role] = DynamicModel(script=[attempt, response(tool=report, args=args)])
        script = [decision(role), decision("finish"), final_answer]
    models["dispatcher"] = DynamicModel(script=script)
    run = Scenario(worker_env, tmp_path / "agents.db", models)
    run.start()
    (step,) = rejected(run, role)
    assert step["tool_name"] == "assign_plan"
    assert run.assignments() == [] and job_count(worker_env) == 0
    reply = json.loads(tool_replies(models[role])[0])
    assert reply["error"]["code"] == "TOOL_NOT_ALLOWED"
    assert run.store.find("approval_requests", run_id=run.run_id) == []
