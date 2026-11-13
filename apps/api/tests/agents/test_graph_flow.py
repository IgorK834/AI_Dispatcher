"""The demo run: Dispatcher, three specialists in order, PlanValidator, then the approval wait."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from routepilot.agents.schemas import DispatcherDecision
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


def demo_scenario(env: ToolEnv, path: Path) -> Scenario:
    models = specialist_models(env)
    models["dispatcher"] = DynamicModel(
        script=[
            *dispatcher_script(request_approval(), decision("approve"), decision("finish")),
            final_answer,
        ]
    )
    return Scenario(env, path / "agents.db", models)


@pytest.mark.ac("AC-FEAT-006-01")
def test_demo_question_visits_the_agents_in_order_and_waits_for_approval(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path
) -> None:
    run = demo_scenario(worker_env, tmp_path)
    outcome = run.start()
    steps = run.steps()
    # A specialist turn makes several model calls (tool call, then report); count it once.
    visits = [step["agent"] for step in steps if step["type"] == "llm"]
    llm_agents = [
        agent for index, agent in enumerate(visits) if index == 0 or agent != visits[index - 1]
    ]
    # Every specialist turn is bracketed by Dispatcher turns: D, fleet, D, scout, D, planner, D.
    assert llm_agents[:6] == [
        "dispatcher",
        "fleet_compliance",
        "dispatcher",
        "freight_scout",
        "dispatcher",
        "route_planner",
    ]
    specialists = [agent for agent in llm_agents if agent != "dispatcher"]
    assert specialists == ["fleet_compliance", "freight_scout", "route_planner"]
    # Each specialist's structured report is in the state.
    state = outcome.state
    assert state["fleet_report"] == {"drivers": [], "warnings": []}
    assert state["scout_report"]["candidate_offer_ids"] and state["scout_report"]["notes"]
    assert state["planner_report"]["recommended"] == {
        "variant": "profit",
        "fleet_solution_id": "profit",
    }
    # PlanValidator ran after the Route Planner's last turn and before the approval wait.
    by_agent = {
        name: [step["seq"] for step in steps if step["agent"] == name]
        for name in ("route_planner", "PlanValidator", "ApprovalGate")
    }
    assert len(by_agent["PlanValidator"]) == 1
    assert (
        max(by_agent["route_planner"]) < by_agent["PlanValidator"][0] < by_agent["ApprovalGate"][0]
    )
    assert state["validated_plans"] and set(state["validated_plans"]) == set(state["plan_facts"])
    # The run is paused at the interrupt: waiting_approval, one pending request, no write yet.
    assert outcome.waiting
    row = run.store.get("agent_runs", run.run_id)
    assert row is not None and row["status"] == "waiting_approval"
    assert run.pending()["action"] == "assign_plan"
    assert run.assignments() == []
    assert [step["type"] for step in steps].count("interrupt") == 1


@pytest.mark.ac("AC-FEAT-006-01")
@pytest.mark.parametrize(
    "value", ["freight_scout", "fleet_compliance", "route_planner", "approve", "finish"]
)
def test_dispatcher_decision_accepts_exactly_the_five_routes(value: str) -> None:
    parsed = DispatcherDecision.model_validate(
        {"next": value, "task": "t", "rationale": "r", "assumptions": ["a"]}
    )
    assert parsed.next == value


@pytest.mark.ac("AC-FEAT-006-01")
@pytest.mark.parametrize(
    "payload",
    [
        {"next": "assign_plan", "task": "t", "rationale": "r", "assumptions": []},
        {"next": "finish", "task": "t", "rationale": "r"},
        {"next": "finish", "task": "t", "rationale": "r", "assumptions": [], "extra": 1},
        {"task": "t", "rationale": "r", "assumptions": []},
    ],
)
def test_dispatcher_decision_rejects_unknown_routes_and_extra_or_missing_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        DispatcherDecision.model_validate(payload)


@pytest.mark.ac("AC-FEAT-006-01")
def test_an_approve_decision_without_an_accepted_request_never_reaches_the_gate(
    worker_env: ToolEnv, generated_offers: object, tmp_path: Path
) -> None:
    models = specialist_models(worker_env)
    # The Dispatcher routes to the gate without calling request_approval first.
    models["dispatcher"] = DynamicModel(
        script=[*dispatcher_script(decision("approve"), decision("finish")), final_answer]
    )
    run = Scenario(worker_env, tmp_path / "agents.db", models)
    outcome = run.start()
    assert not outcome.waiting and "ApprovalGate" not in {step["agent"] for step in run.steps()}
    assert any("accepted request_approval" in note for note in outcome.state["notes"])
    assert run.assignments() == []
