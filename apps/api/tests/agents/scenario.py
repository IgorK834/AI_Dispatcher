"""A full graph run on the real tool registry, the real SQL store and scripted chat models.

Plan references are random per run, so scripted Dispatcher answers are callables of the model's
input (they read the plan facts from the context message, as a real model would).
"""

import json
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from routepilot.agent_persistence import SqlAgentStore
from routepilot.agents.graph import GraphContext, build_graph, initial_state
from routepilot.agents.models import ModelPolicy, ModelRegistry
from routepilot.freight.service import FreightOfferCreate
from routepilot.shared.auth import Principal
from routepilot.shared.config import Settings
from tests.agents.conftest import FLEET_POOL, ToolEnv
from tests.agents.fakes import ScriptedModel, response

QUESTION = "Find the best loads for all vans for tomorrow; everyone must get home for the weekend."
PLAN_REF = re.compile(r"PLAN-[0-9a-f]{8}")


class DynamicModel(ScriptedModel):
    """A scripted model whose entries may be callables of the messages it receives."""

    script: list[Any]

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> Any:
        if self.script and callable(self.script[0]):
            self.script[0] = self.script[0](messages)
        return super()._generate(messages, *args, **kwargs)


Entry = AIMessage | Callable[[list[BaseMessage]], AIMessage]


def decision(next: str) -> AIMessage:
    return response(
        tool="DispatcherDecision",
        args={
            "next": next,
            "task": "Plan using tools",
            "rationale": "Use deterministic services",
            "assumptions": [],
        },
    )


def context_of(messages: list[BaseMessage]) -> dict[str, Any]:
    """The JSON context message the graph sends with every specialist and Dispatcher turn."""
    human = [message for message in messages if isinstance(message, HumanMessage)]
    return cast(dict[str, Any], json.loads(str(human[-1].content)))


def pick_plans(messages: list[BaseMessage], *, only_driver: str | None = None) -> list[str]:
    """Most profitable plan per driver without shared offers, skipping plans named in the notes."""
    context = context_of(messages)
    stale = set(PLAN_REF.findall(" ".join(context["notes"])))
    chosen: list[dict[str, Any]] = []
    # Specialist and Dispatcher turns send the plans as "plans"; the final answer call as "facts".
    plans = context.get("plans", context.get("facts", []))
    for plan in sorted(plans, key=lambda item: -Decimal(item["net_profit_eur"])):
        if plan["plan_ref"] in stale or (only_driver and plan["driver_ref"] != only_driver):
            continue
        if any(
            plan["driver_ref"] == other["driver_ref"]
            or set(plan["offer_ids"]) & set(other["offer_ids"])
            for other in chosen
        ):
            continue
        chosen.append(plan)
    return [plan["plan_ref"] for plan in chosen]


def same_driver_plans(messages: list[BaseMessage], driver: str, count: int) -> list[str]:
    plans = [plan for plan in context_of(messages)["plans"] if plan["driver_ref"] == driver]
    return [plan["plan_ref"] for plan in plans[:count]]


def request_approval(select: Callable[[list[BaseMessage]], list[str]] = pick_plans) -> Entry:
    return lambda messages: response(
        tool="request_approval",
        args={"action": "assign_plan", "plan_refs": select(messages), "summary": "Proposed plans"},
    )


def final_answer(messages: list[BaseMessage]) -> AIMessage:
    refs = pick_plans(messages)
    return response(
        tool="AnswerText",
        args={"summary": "Proposed plans: " + ", ".join(refs), "citedFacts": refs},
    )


def dispatcher_script(*after_planner: Entry) -> list[Entry]:
    return [
        decision("fleet_compliance"),
        decision("freight_scout"),
        decision("route_planner"),
        *after_planner,
    ]


def add_offer(env: ToolEnv, *, description: str, remark: str) -> Any:
    """A hand-made offer in the first driver's city, so the Scout's city search finds it."""
    window = env.driver.state.available_from
    return env.freight.create_offer(
        FreightOfferCreate(
            description=description,
            revenue={"amountMinor": 80000, "currency": "EUR"},
            weight_kg=100,
            pallet_count=1,
            pallet_type="EUR_1200x800",
            required_body_types=["CURTAIN_SIDER"],
            public_remark=remark,
            stops=[
                {
                    "stopType": "LOADING",
                    "city": env.driver.state.current_city,
                    "countryCode": "PL",
                    "lat": env.driver.state.current_lat,
                    "lon": env.driver.state.current_lon,
                    "windowStart": window,
                    "windowEnd": window + timedelta(hours=8),
                },
                {
                    "stopType": "UNLOADING",
                    "city": "Opole",
                    "countryCode": "PL",
                    "lat": 50.6751,
                    "lon": 17.9213,
                    "windowStart": window + timedelta(hours=1),
                    "windowEnd": window + timedelta(hours=16),
                },
            ],
        ),
        str(env.user),
    )


def specialist_models(
    env: ToolEnv, *, scout_calls: list[AIMessage] | None = None
) -> dict[str, Any]:
    manual = f"OFF-{env.offer.id.hex[:8]}"
    offers = [*FLEET_POOL, manual]
    # Searching the drivers' city makes the hand-made offer known to this run's alias map.
    city = env.driver.state.current_city
    scout_calls = scout_calls or [response(tool="search_offers", args={"origin_city": city})]
    return {
        "fleet_compliance": DynamicModel(
            script=[
                response(tool="list_drivers"),
                response(tool="FleetReport", args={"drivers": [], "warnings": []}),
            ]
        ),
        "freight_scout": DynamicModel(
            script=[
                *scout_calls,
                response(
                    tool="ScoutReport",
                    args={
                        "candidate_offer_ids": offers,
                        "excluded": [],
                        "data_issues": [],
                        "notes": "Synthetic offers",
                    },
                ),
            ]
        ),
        "route_planner": DynamicModel(
            script=[
                response(tool="optimize_fleet", args={"offer_ids": offers}),
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
        ),
    }


@dataclass(frozen=True)
class Outcome:
    state: dict[str, Any]
    waiting: bool  # the graph is paused at an interrupt


@dataclass
class Scenario:
    env: ToolEnv
    path: Path
    models: dict[str, Any]
    store: SqlAgentStore = field(init=False)
    user: Principal = field(init=False)
    registry: ModelRegistry = field(init=False)
    run_id: UUID = field(default_factory=uuid4)
    thread_id: UUID = field(init=False)

    def __post_init__(self) -> None:
        env = self.env
        self.user = Principal(id=env.user, role="dispatcher", locale="en", session_id=uuid4())
        self.store = SqlAgentStore(env.freight.engine, env.clock)
        policy = ModelPolicy.model_validate(
            {role: {"model": f"fake:{role}", "maxTokens": 30} for role in self.models}
        )
        settings = Settings(
            app_env="test",
            _env_file=None,
            google_api_key="",
            anthropic_api_key="",
            openai_api_key="",
        )
        self.registry = ModelRegistry(
            settings,
            policy,
            {f"fake:{role}": lambda model=model: model for role, model in self.models.items()},
        )
        thread = self.store.create(
            "agent_threads",
            {
                "user_id": env.user,
                "title": "Synthetic",
                "created_at": env.clock.now(),
                "updated_at": env.clock.now(),
            },
        )
        self.thread_id = UUID(str(thread["id"]))
        self.store.create(
            "agent_runs",
            {
                "id": self.run_id,
                "thread_id": self.thread_id,
                "status": "running",
                "user_message": QUESTION,
                "model_policy": {},
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_estimate_minor": 0,
                "currency": "USD",
                "created_at": env.clock.now(),
            },
        )

    @property
    def config(self) -> Any:
        return {"configurable": {"thread_id": str(self.thread_id)}, "recursion_limit": 100}

    def _invoke(self, graph_input: Any) -> Outcome:
        """One process lifetime: a new connection, saver, graph and context on the same file."""
        context = GraphContext(
            self.registry,
            self.env.registry,
            self.store,
            self.env.clock,
            self.registry.settings,
            self.user,
            self.run_id,
        )
        with sqlite3.connect(self.path, check_same_thread=False) as connection:
            saver = SqliteSaver(connection)
            saver.setup()
            graph = build_graph(saver)
            graph.invoke(graph_input, self.config, context=context)
            snapshot = graph.get_state(self.config)
            return Outcome(dict(snapshot.values), bool(snapshot.next))

    def start(self, question: str = QUESTION) -> Outcome:
        return self._invoke(initial_state(self.run_id, self.user, question, "en"))

    def decide(self, decision_value: str, comment: str | None = None) -> Outcome:
        approval = self.pending()
        decided = self.store.decide(
            UUID(str(approval["id"])), self.user.id, decision_value, self.env.clock.now()
        )
        if not decided:
            raise AssertionError("the approval was not pending")
        return self._invoke(Command(resume={"decision": decision_value, "comment": comment}))

    def pending(self) -> dict[str, Any]:
        rows = self.store.find("approval_requests", run_id=self.run_id, status="pending")
        if len(rows) != 1:
            raise AssertionError(f"expected one pending approval, found {rows}")
        return rows[0]

    def steps(self) -> list[dict[str, Any]]:
        return self.store.find("agent_steps", run_id=self.run_id)

    def assignments(self) -> list[Any]:
        return self.env.assignments.list_assignments(limit=100).items

    def recorded(self) -> list[tuple[str, list[BaseMessage]]]:
        """Every model input of the run as (role, messages)."""
        return [
            (role, messages) for role, model in self.models.items() for messages in model.recorded
        ]
