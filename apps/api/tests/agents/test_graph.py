"""Full graph turns, persisted interrupt/resume and minimised tool facts."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from routepilot.agents.graph import GraphContext, build_graph, initial_state
from routepilot.agents.models import ModelPolicy, ModelRegistry
from routepilot.shared.auth import Principal
from routepilot.shared.clock import FixedClock
from routepilot.shared.config import Settings
from tests.agents.fakes import ScriptedModel, response
from tests.agents.memory_store import MemoryStore


class Tools:
    def prepare(self, state: dict[str, Any]) -> None:
        return None

    def __init__(self) -> None:
        self.writes: list[UUID] = []
        self.plan_id = uuid4()

    def schemas(self, role: str) -> list[dict[str, Any]]:
        return []

    def execute(
        self,
        role: str,
        name: str,
        args: dict[str, Any],
        state: dict[str, Any],
        model_call: Any = None,
    ) -> dict[str, Any]:
        allowed = {
            "fleet_compliance": ["list_drivers"],
            "freight_scout": ["search_offers"],
            "route_planner": ["optimize_fleet"],
            "dispatcher": ["request_approval"],
        }
        if name not in allowed.get(role, []):
            return {"error": {"code": "TOOL_NOT_ALLOWED", "message": "Tool unavailable"}}
        if name == "optimize_fleet":
            state["aliases"]["plans"] = {"PLAN-1a2b3c4d": str(self.plan_id)}
            state["plan_facts"] = {
                "PLAN-1a2b3c4d": {
                    "plan_ref": "PLAN-1a2b3c4d",
                    "driver_ref": "D1",
                    "variant": "profit",
                    "net_profit_eur": "323.54",
                    "finish_at": "2026-11-17T06:55:00Z",
                    "fuel_l": "76.601",
                    "co2_kg": "199.16",
                    "offer_ids": ["MOCK-000001"],
                }
            }
            return {"fleet": {"profit": {"plans": list(state["plan_facts"].values())}}}
        if name == "request_approval":
            state["pending_approval"] = {
                "plan_refs": ["PLAN-1a2b3c4d"],
                "plan_ids": [str(self.plan_id)],
                "payload": {
                    "plans": [
                        {
                            "planRef": "PLAN-1a2b3c4d",
                            "routePlanId": str(self.plan_id),
                            "driverRef": "D1",
                            "driverLabel": "Synthetic driver",
                            "offerIds": ["MOCK-000001"],
                            "variant": "profit",
                            "netProfit": {"amountMinor": 32354, "currency": "EUR"},
                            "finishAt": "2026-11-17T06:55:00Z",
                            "homeReached": True,
                        }
                    ],
                    "totals": {
                        "netProfit": {"amountMinor": 32354, "currency": "EUR"},
                        "fuelL": "76.601",
                        "co2Kg": "199.16",
                    },
                },
            }
            return {"accepted": True, "problems": []}
        return (
            {"drivers": [{"driver_ref": "D1"}]}
            if name == "list_drivers"
            else {"offers": [{"offer_id": "MOCK-000001"}]}
        )

    def validate_plans(self, state: dict[str, Any]) -> list[str]:
        state["validated_plans"] = ["PLAN-1a2b3c4d"]
        return []

    def assign(self, plan_ids: Any, actor: UUID, run_id: UUID) -> list[dict[str, Any]]:
        self.writes.extend(plan_ids)
        return [{"plan_ref": "PLAN-1a2b3c4d", "driver_ref": "D1", "status": "active"}]


def decision(next: str) -> Any:
    return response(
        tool="DispatcherDecision",
        args={
            "next": next,
            "task": "Plan using tools",
            "rationale": "Use deterministic services",
            "assumptions": [],
        },
    )


def scripted_registry() -> ModelRegistry:
    dispatcher = ScriptedModel(
        script=[
            decision("fleet_compliance"),
            decision("freight_scout"),
            decision("route_planner"),
            response(
                tool="request_approval",
                args={
                    "action": "assign_plan",
                    "plan_refs": ["PLAN-1a2b3c4d"],
                    "summary": "Proposed plan",
                },
            ),
            decision("approve"),
            decision("finish"),
            response(
                tool="AnswerText",
                args={"summary": "PLAN-1a2b3c4d profit €323.54.", "citedFacts": ["PLAN-1a2b3c4d"]},
            ),
        ]
    )
    fleet = ScriptedModel(
        script=[
            response(tool="list_drivers"),
            response(tool="FleetReport", args={"drivers": [], "warnings": []}),
        ]
    )
    scout = ScriptedModel(
        script=[
            response(tool="search_offers"),
            response(
                tool="ScoutReport",
                args={
                    "candidate_offer_ids": ["MOCK-000001"],
                    "excluded": [],
                    "data_issues": [],
                    "notes": "Synthetic offers",
                },
            ),
        ]
    )
    planner = ScriptedModel(
        script=[
            response(tool="optimize_fleet"),
            response(
                tool="PlannerReport",
                args={
                    "recommended": {"variant": "profit", "fleet_solution_id": "profit"},
                    "alternatives": [],
                    "tradeoffs": [],
                    "baseline_uplift": None,
                },
            ),
        ]
    )
    models = {
        "dispatcher": dispatcher,
        "fleet_compliance": fleet,
        "freight_scout": scout,
        "route_planner": planner,
    }
    policy = ModelPolicy.model_validate(
        {role: {"model": f"fake:{role}", "maxTokens": 30} for role in models}
    )
    settings = Settings(app_env="test", _env_file=None)
    return ModelRegistry(
        settings,
        policy,
        {f"fake:{role}": lambda model=model: model for role, model in models.items()},
    )


@pytest.mark.ac("AC-FEAT-006-01")
@pytest.mark.ac("AC-FEAT-006-03")
@pytest.mark.ac("AC-FEAT-006-04")
@pytest.mark.ac("AC-FEAT-006-06")
@pytest.mark.ac("AC-FEAT-006-07")
@pytest.mark.ac("AC-FEAT-006-22")
@pytest.mark.parametrize("decision_value", ["approve", "reject", "edit"])
@pytest.mark.ac("AC-FEAT-006-05")
def test_graph_durable_approval_is_the_only_write(tmp_path: Path, decision_value: str) -> None:
    registry, tools, store = scripted_registry(), Tools(), MemoryStore()
    user = Principal(id=uuid4(), role="dispatcher", locale="en", session_id=uuid4())
    run_id, thread_id = uuid4(), uuid4()
    clock = FixedClock(datetime(2026, 11, 12, tzinfo=UTC))
    store.create("agent_threads", {"id": thread_id, "user_id": user.id})
    store.create(
        "agent_runs",
        {
            "id": run_id,
            "thread_id": thread_id,
            "created_at": clock.now(),
            "status": "running",
            "tokens_in": 0,
            "tokens_out": 0,
        },
    )
    state = initial_state(run_id, user, "Find loads", "en")
    context = GraphContext(registry, tools, store, clock, registry.settings, user, run_id)
    config: Any = {"configurable": {"thread_id": str(thread_id)}, "recursion_limit": 100}
    with sqlite3.connect(tmp_path / "agents.db", check_same_thread=False) as connection:
        saver = SqliteSaver(connection)
        saver.setup()
        graph = build_graph(saver)
        interrupted = graph.invoke(state, config, context=context)
        assert interrupted["__interrupt__"]
        assert store.get("agent_runs", run_id)["status"] == "waiting_approval"
        assert tools.writes == []
    approval = store.find("approval_requests", run_id=run_id)[0]
    assert store.decide(approval["id"], user.id, decision_value, clock.now())
    # Rebuild the graph and checkpointer using the same file.
    with sqlite3.connect(tmp_path / "agents.db", check_same_thread=False) as connection:
        saver = SqliteSaver(connection)
        graph = build_graph(saver)
        resumed = graph.invoke(
            Command(resume={"decision": decision_value, "comment": "Owner decision"}),
            config,
            context=GraphContext(registry, tools, store, clock, registry.settings, user, run_id),
        )
    assert len(store.find("approval_requests", run_id=run_id)) == 1
    assert len(tools.writes) == (1 if decision_value == "approve" else 0)
    assert resumed["final_answer"]["grounded"] is True
    assert resumed["final_answer"]["source"] == "llm"
    steps = store.find("agent_steps", run_id=run_id)
    assert any(step["agent"] == "PlanValidator" for step in steps)
    assert all(
        len(step["inputSummary"]) <= 500 and len(step["outputSummary"]) <= 500 for step in steps
    )
    assert len([step for step in steps if step["type"] == "interrupt"]) == 1
