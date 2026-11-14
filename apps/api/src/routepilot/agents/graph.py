"""Custom LangGraph supervisor, deterministic guards and durable approval gate."""

import json
import re
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from threading import Event, Lock
from time import monotonic
from typing import Any, TypedDict, cast
from uuid import UUID

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from pydantic import BaseModel, ValidationError

from routepilot.agents.guards import BudgetExceeded, TokenBudget, grounding_violations
from routepilot.agents.models import ModelRegistry, ModelResult, ProviderFailure, Role
from routepilot.agents.ports import AgentStore, ToolExecutor
from routepilot.agents.prompt_loader import Prompt, load_prompts
from routepilot.agents.schemas import REPORT_SCHEMAS, AnswerText, StepKind, TraceStatus, TraceStep
from routepilot.shared.auth import Principal
from routepilot.shared.clock import Clock
from routepilot.shared.config import Settings
from routepilot.shared.errors import DomainError

DISCLAIMER = (
    "The work/driving/rest schedule is a planning estimate based on a simplified model of selected "
    "rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). "
    "It does not certify legal compliance."
)


class AgentState(TypedDict, total=False):
    run_id: str
    user: dict[str, str]
    locale: str
    messages: list[BaseMessage]
    task: str
    scout_report: dict[str, Any]
    fleet_report: dict[str, Any]
    planner_report: dict[str, Any]
    tool_results: list[dict[str, Any]]
    aliases: dict[str, dict[str, str]]
    pending_approval: dict[str, Any] | None
    budget: dict[str, Any]
    next: str
    plan_facts: dict[str, dict[str, Any]]
    validated_plans: list[str]
    planner_attempts: int
    notes: list[str]
    final_answer: dict[str, Any]
    error: dict[str, str]
    assigned: bool


def initial_state(
    run_id: UUID,
    user: Principal,
    question: str,
    locale: str,
    aliases: dict[str, dict[str, str]] | None = None,
) -> AgentState:
    # User text is data. Strip contact details and internal IDs before model input.
    question = re.sub(r"[\w.+-]+@[\w.-]+", "[email]", question)
    question = re.sub(r"\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b", "[id]", question)
    question = re.sub(r"(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)", "[contact]", question)
    return AgentState(
        run_id=str(run_id),
        user={"id": str(user.id), "role": user.role},
        locale=locale,
        messages=[HumanMessage(question)],
        task=question,
        tool_results=[],
        aliases=aliases or {"drivers": {}, "plans": {}, "offers": {}},
        pending_approval=None,
        budget={"steps": 0, "tool_calls": {}, "tokens_in": 0, "tokens_out": 0, "elapsed_s": 0},
        plan_facts={},
        validated_plans=[],
        planner_attempts=0,
        notes=[],
        assigned=False,
    )


def _model_data(value: Any) -> Any:
    """Untrusted remarks stay in their original get_offer response only."""
    if isinstance(value, dict):
        return {key: _model_data(item) for key, item in value.items() if key != "untrusted_text"}
    if isinstance(value, list):
        return [_model_data(item) for item in value]
    return value


class ToolFailure(Exception):
    """A tool answered TOOL_ERROR twice; the agent's turn ends with a note for the Dispatcher."""

    def __init__(self, role: Role, tool: str) -> None:
        super().__init__(tool)
        self.note = f"{role} stopped: {tool} failed twice (TOOL_ERROR); no new report from {role}"


class GuardStop(BudgetExceeded):
    """A limit was reached and a `guard` step with the reason is already stored."""


@dataclass
class GraphContext:
    registry: ModelRegistry
    tools: ToolExecutor
    store: AgentStore
    clock: Clock
    settings: Settings
    user: Principal
    run_id: UUID
    campaign_budgets: list[TokenBudget] = field(default_factory=list)
    live_campaign: bool = False
    prompts: dict[str, Prompt] = field(default_factory=load_prompts)
    cancelled: Event = field(default_factory=Event)
    started: float = field(default_factory=monotonic)
    run_budget: TokenBudget | None = None
    daily_budget: TokenBudget | None = None
    # Steps that were started and not finished, and whether the run was abandoned (timeout): an
    # abandoned worker thread cannot be stopped, so it must not write after `run_finished`.
    _open: dict[UUID, TraceStep] = field(default_factory=dict, repr=False)
    _closed: bool = field(default=False, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def _budgets(self, state: AgentState) -> list[TokenBudget]:
        if self.run_budget is None:
            self.run_budget = TokenBudget(self.settings.agent_run_token_budget)
            self.run_budget.tokens_in = state["budget"]["tokens_in"]
            self.run_budget.tokens_out = state["budget"]["tokens_out"]
            self.run_budget.used = self.run_budget.tokens_in + self.run_budget.tokens_out
        if self.daily_budget is None:
            limit = (
                self.settings.agent_daily_token_budget_demo
                if self.user.role == "demo"
                else self.settings.agent_daily_token_budget
            )
            used = self.store.daily_usage(self.user.id, self.clock.now().date().isoformat())
            self.daily_budget = TokenBudget(limit, used)
        return [self.run_budget, self.daily_budget, *self.campaign_budgets]

    def trace(
        self, agent: str, kind: StepKind, summary: str, *, tool: str | None = None
    ) -> tuple[UUID, TraceStep, float]:
        step = TraceStep(seq=0, agent=agent, type=kind, toolName=tool, inputSummary=summary[:500])
        with self._lock:
            if self._closed:
                raise GuardStop("RUN_TIMEOUT")
            id = self.store.start_step(self.run_id, step)
            self._open[id] = step
        return id, step, monotonic()

    def end_trace(
        self,
        trace: tuple[UUID, TraceStep, float],
        summary: str,
        status: TraceStatus = "ok",
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        id, step, start = trace
        with self._lock:
            if id not in self._open:
                return  # the run was abandoned and this step closed with it
            del self._open[id]
            step.outputSummary = summary[:500]
            step.status = status
            step.durationMs = max(0, int((monotonic() - start) * 1000))
            step.tokens = {"in": tokens_in, "out": tokens_out}
            self.store.finish_step(id, step)

    def abandon(self) -> None:
        """The run timed out or failed: close open steps and refuse every later write."""
        self.cancelled.set()
        with self._lock:
            self._closed = True
            for id, step in self._open.items():
                step.outputSummary = "RUN_TIMEOUT"
                step.status = "error"
                self.store.finish_step(id, step)
            self._open.clear()

    def reject(self, reason: str) -> GuardStop:
        """Store a `guard` step with the reason of a stop and return the error to raise."""
        trace = self.trace("BudgetGuard", "guard", "Check run, daily and tool budgets")
        self.end_trace(trace, reason, "rejected")
        return GuardStop(reason)

    def persist_usage(self, state: AgentState) -> None:
        if self.run_budget:
            state["budget"].update(
                tokens_in=self.run_budget.tokens_in, tokens_out=self.run_budget.tokens_out
            )
        self.store.update(
            "agent_runs",
            self.run_id,
            {
                "tokens_in": state["budget"]["tokens_in"],
                "tokens_out": state["budget"]["tokens_out"],
            },
        )

    def guard(
        self, state: AgentState, *, count_step: bool = False, tool_role: Role | None = None
    ) -> None:
        if self.cancelled.is_set() and self._closed:
            raise GuardStop("RUN_TIMEOUT")
        trace = self.trace("BudgetGuard", "guard", "Check run, daily and tool budgets")
        reason = None
        if (
            self.cancelled.is_set()
            or monotonic() - self.started + state["budget"]["elapsed_s"]
            >= self.settings.agent_run_timeout_s
        ):
            reason = "RUN_TIMEOUT"
        elif state["budget"]["steps"] >= self.settings.agent_recursion_limit:
            reason = "STEP_LIMIT"
        elif (
            tool_role is not None
            and state["budget"]["tool_calls"].get(tool_role, 0)
            >= self.settings.agent_max_tool_calls
        ):
            reason = "TOOL_CALL_LIMIT"
        elif any(budget.closed or budget.used >= budget.limit for budget in self._budgets(state)):
            reason = "TOKEN_BUDGET"
        self.end_trace(trace, reason or "Within limits", "rejected" if reason else "ok")
        if reason:
            raise GuardStop(reason)
        if count_step:
            state["budget"]["steps"] += 1

    def call(
        self,
        state: AgentState,
        role: Role,
        messages: list[BaseMessage],
        *,
        schema: type[BaseModel] | None = None,
        tools: bool = False,
    ) -> ModelResult:
        current: tuple[UUID, TraceStep, float] | None = None

        def observe(status: str, model: str, tokens_in: int, tokens_out: int) -> None:
            nonlocal current
            if status == "started":
                self.guard(state, count_step=True)
                current = self.trace(role, "llm", f"Model call for {role}")
            elif current:
                self.persist_usage(state)
                self.end_trace(
                    current, f"{model}: {status}", cast(TraceStatus, status), tokens_in, tokens_out
                )

        try:
            return self.registry.call(
                role,
                messages,
                schema=schema,
                tools=self.tools.schemas(role) if tools else [],
                budgets=self._budgets(state),
                live_campaign=self.live_campaign,
                observe=observe,
            )
        except GuardStop:
            raise
        except BudgetExceeded as error:
            # The token reservation was refused inside the registry: store the reason as a guard
            # step like every other stop.
            raise self.reject(str(error) or "TOKEN_BUDGET") from error

    def turn(self, state: AgentState, role: Role) -> dict[str, Any]:
        self.tools.prepare(cast(dict[str, Any], state))
        reports = {
            key: state[key]
            for key in ("scout_report", "fleet_report", "planner_report")
            if key in state
        }
        context = {
            "locale": state["locale"],
            "task": state["task"],
            "reports": reports,
            "plans": list(state["plan_facts"].values()),
            "notes": state["notes"],
            "output_schema": REPORT_SCHEMAS[role].model_json_schema(),
        }
        messages: list[BaseMessage] = [
            SystemMessage(self.prompts[role].text),
            *state["messages"][:1],
            HumanMessage(json.dumps(_model_data(context), default=str)),
        ]
        schema = REPORT_SCHEMAS[role]
        while True:
            result = self.call(state, role, messages, tools=True)
            message = result.message
            # Structured report calls are output transport, never application tools.
            if len(message.tool_calls) == 1 and message.tool_calls[0]["name"] == schema.__name__:
                return schema.model_validate(message.tool_calls[0]["args"]).model_dump()
            if not message.tool_calls:
                try:
                    return schema.model_validate_json(str(message.content)).model_dump()
                except ValidationError:
                    result = self.call(
                        state,
                        role,
                        [*messages, HumanMessage("Return the structured report.")],
                        schema=schema,
                    )
                    if result.parsed is None:
                        raise ProviderFailure("AI_PROVIDER_ERROR") from None
                    return result.parsed.model_dump()
            messages.append(message)
            for call in message.tool_calls:
                self.guard(state, tool_role=role)
                counts = state["budget"]["tool_calls"]
                counts[role] = counts.get(role, 0) + 1
                trace = self.trace(role, "tool", f"Call {call['name']}", tool=call["name"])
                for attempt in (1, 2):
                    facts = self.tools.execute(
                        role,
                        call["name"],
                        call["args"],
                        cast(dict[str, Any], state),
                        lambda messages, schema: self.call(
                            state, "explainer", messages, schema=schema
                        ),
                    )
                    if facts.get("error", {}).get("code") != "TOOL_ERROR":
                        break
                    if attempt == 2:
                        self.end_trace(trace, "Tool failed twice", "error")
                        raise ToolFailure(role, call["name"])
                rejected = facts.get("error", {}).get("code") == "TOOL_NOT_ALLOWED"
                self.end_trace(
                    trace,
                    "Tool rejected" if rejected else "Bounded tool result",
                    "rejected" if rejected else "error" if "error" in facts else "ok",
                )
                state["tool_results"].append(
                    {"tool": call["name"], "call_id": call["id"], "facts": _model_data(facts)}
                )
                messages.append(
                    ToolMessage(json.dumps(facts, default=str), tool_call_id=call["id"])
                )


def _failure(state: AgentState, error: Exception) -> AgentState:
    state["error"] = {
        "code": "BUDGET_EXCEEDED" if isinstance(error, BudgetExceeded) else "AI_PROVIDER_ERROR",
        "message": "Generation stopped; deterministic facts retained.",
    }
    state["next"] = "template"
    return state


def budget_guard(state: AgentState, runtime: Runtime[GraphContext]) -> AgentState:
    try:
        runtime.context.guard(state)
    except BudgetExceeded as error:
        return _failure(state, error)
    state["next"] = "dispatcher"
    return state


def dispatcher(state: AgentState, runtime: Runtime[GraphContext]) -> AgentState:
    try:
        decision = runtime.context.turn(state, "dispatcher")
        state["next"] = decision["next"]
        if decision["next"] == "approve" and not state["pending_approval"]:
            state["notes"].append("Approval requires an accepted request_approval result.")
            state["next"] = "finish"
        return state
    except ToolFailure as error:
        state["notes"].append(error.note)
        state["next"] = "finish"
        return state
    except (BudgetExceeded, ProviderFailure, ValidationError) as error:
        return _failure(state, error)


def _specialist(
    state: AgentState, runtime: Runtime[GraphContext], role: Role, key: str
) -> AgentState:
    try:
        cast(dict[str, Any], state)[key] = runtime.context.turn(state, role)
        state["next"] = "plan_validator" if role == "route_planner" else "budget_guard"
    except ToolFailure as error:
        state["notes"].append(error.note)
        state["next"] = "budget_guard"
    except (BudgetExceeded, ProviderFailure, ValidationError) as error:
        return _failure(state, error)
    return state


def freight_scout(state: AgentState, runtime: Runtime[GraphContext]) -> AgentState:
    return _specialist(state, runtime, "freight_scout", "scout_report")


def fleet_compliance(state: AgentState, runtime: Runtime[GraphContext]) -> AgentState:
    return _specialist(state, runtime, "fleet_compliance", "fleet_report")


def route_planner(state: AgentState, runtime: Runtime[GraphContext]) -> AgentState:
    return _specialist(state, runtime, "route_planner", "planner_report")


def plan_validator(state: AgentState, runtime: Runtime[GraphContext]) -> AgentState:
    context = runtime.context
    trace = context.trace("PlanValidator", "guard", "Validate stored plan snapshots")
    invalid = context.tools.validate_plans(cast(dict[str, Any], state))
    context.end_trace(
        trace, "Plans rejected" if invalid else "Plans validated", "rejected" if invalid else "ok"
    )
    if invalid:
        state["planner_attempts"] += 1
        state["notes"].append("Invalid plans removed: " + ", ".join(invalid))
        state["next"] = "route_planner" if state["planner_attempts"] == 1 else "budget_guard"
        if state["planner_attempts"] > 1:
            state["planner_report"] = {}
    else:
        state["next"] = "budget_guard"
    return state


def _assignment_failure(state: AgentState, pending: dict[str, Any], error: DomainError) -> str:
    """Tell the Dispatcher which approved plans failed, so it can drop them and ask again.

    The service reports a changed offer by its internal id; only the plans holding that offer are
    named. For other failures the service does not name a plan, so none is guessed.
    """
    offers = state["aliases"]["offers"]
    changed = {str(item["offerId"]) for item in error.errors if "offerId" in item}
    stale = [
        ref
        for ref in pending["plan_refs"]
        if changed
        & {offers.get(offer) for offer in state["plan_facts"].get(ref, {}).get("offer_ids", [])}
    ]
    codes = ", ".join(sorted({str(item.get("code", error.code)) for item in error.errors}))
    if stale:
        return f"{error.code}: nothing was assigned; stale plans {', '.join(stale)} ({codes})"
    return f"{error.code}: nothing was assigned; the failing plan is not identified ({codes})"


def approval_gate(state: AgentState, runtime: Runtime[GraphContext]) -> AgentState:
    context = runtime.context
    pending = state["pending_approval"]
    if pending is None:
        raise DomainError("APPROVAL_NOT_PENDING")
    interrupt_id = f"{state['run_id']}:{state['budget']['steps']}"
    existing = context.store.find(
        "approval_requests", run_id=context.run_id, interrupt_id=interrupt_id
    )
    if existing:
        approval = existing[0]
    else:
        try:
            context.guard(state)
        except BudgetExceeded as error:
            # No approval request exists yet: end the run with the template answer instead of
            # letting the exception fail the whole run.
            return _failure(state, error)
        payload = pending["payload"]
        approval = context.store.create(
            "approval_requests",
            {
                "run_id": context.run_id,
                "interrupt_id": interrupt_id,
                "action": "assign_plan",
                "payload": payload,
                "status": "pending",
                "decided_by": None,
                "decided_at": None,
                "expires_at": context.clock.now()
                + timedelta(minutes=context.settings.approval_ttl_min),
            },
        )
        context.store.update("agent_runs", context.run_id, {"status": "waiting_approval"})
        trace = context.trace("ApprovalGate", "interrupt", "Wait for an explicit owner decision")
        context.end_trace(trace, "Approval required")
        context.store.emit(
            context.run_id,
            "approval_required",
            {
                "approvalId": str(approval["id"]),
                "action": "assign_plan",
                "payload": payload,
                "expiresAt": approval["expires_at"].isoformat(),
            },
        )
    context.persist_usage(state)
    state["budget"]["elapsed_s"] += monotonic() - context.started
    # This interrupt is deliberately outside try/except. Re-entry only re-reads
    # the same approval row and never creates a second interrupt or assignment.
    decision = interrupt(
        {"approvalId": str(approval["id"]), "action": "assign_plan", "payload": approval["payload"]}
    )
    context.started = monotonic()
    if decision.get("decision") == "approve":
        try:
            context.guard(state)
        except BudgetExceeded as error:
            state["notes"].append("Approved assignments were not committed: a limit was reached.")
            return _failure(state, error)
        trace = context.trace(
            "ApprovalGate", "tool", "Commit the approved set atomically", tool="assign_plan"
        )
        try:
            context.tools.assign(
                [UUID(id) for id in pending["plan_ids"]], context.user.id, context.run_id
            )
            state["assigned"] = True
            context.end_trace(trace, "Approved assignments committed")
            state["notes"].append("Approved assignments committed.")
        except DomainError as error:
            context.end_trace(trace, error.code, "error")
            state["notes"].append(_assignment_failure(state, pending, error))
    else:
        state["notes"].append(
            f"Human decision: {decision.get('decision')}; {decision.get('comment') or ''}"
        )
    state["pending_approval"] = None
    state["next"] = "budget_guard"
    return state


def _answer(state: AgentState, summary: str, source: str, cited: list[str]) -> dict[str, Any]:
    return {
        "summary": summary,
        "proposals": [
            {
                "planRef": ref,
                "routePlanId": state["aliases"]["plans"][ref],
                "driverRef": facts["driver_ref"],
                "variant": facts["variant"],
                "netProfit": {
                    "amountMinor": int(Decimal(facts["net_profit_eur"]) * 100),
                    "currency": "EUR",
                },
                "finishAt": facts["finish_at"],
                "fuelL": facts["fuel_l"],
                "co2Kg": facts["co2_kg"],
            }
            for ref, facts in state["plan_facts"].items()
            if ref in state["validated_plans"]
        ],
        "citedFacts": cited,
        "grounded": True,
        "source": source,
        "disclaimer": DISCLAIMER,
    }


def template_answer(state: AgentState, runtime: Runtime[GraphContext]) -> AgentState:
    plans = [facts for ref, facts in state["plan_facts"].items() if ref in state["validated_plans"]]
    pieces = [f"{facts['plan_ref']}: {facts['net_profit_eur']} EUR" for facts in plans]
    label = "Zatwierdzone przydziały" if state["assigned"] else "Proponowane plany"
    if state["locale"] == "en":
        label = "Approved assignments" if state["assigned"] else "Proposed plans"
    summary = (
        label + ": " + "; ".join(pieces)
        if pieces
        else (
            "Brak zweryfikowanego planu."
            if state["locale"] == "pl"
            else "No validated recommendation is available."
        )
    )
    suspicious = [
        item["facts"]
        for item in state["tool_results"]
        if "SUSPICIOUS_TEXT" in json.dumps(item["facts"])
    ]
    if suspicious:
        summary += (
            " Suspicious offers were excluded."
            if state["locale"] == "en"
            else " Podejrzane oferty pominięto."
        )
    state["final_answer"] = _answer(
        state, summary, "template", [facts["plan_ref"] for facts in plans]
    )
    return state


def grounding_guard(state: AgentState, runtime: Runtime[GraphContext]) -> AgentState:
    context = runtime.context
    try:
        result = context.call(
            state,
            "dispatcher",
            [
                SystemMessage(context.prompts["dispatcher"].text),
                HumanMessage(
                    json.dumps(
                        {
                            "locale": state["locale"],
                            "facts": list(state["plan_facts"].values()),
                            "reports": {
                                key: state[key]
                                for key in ("scout_report", "fleet_report", "planner_report")
                                if key in state
                            },
                            "notes": state["notes"],
                            "assigned": state["assigned"],
                        },
                        default=str,
                    )
                ),
            ],
            schema=AnswerText,
        )
        candidate = cast(AnswerText, result.parsed)
        trace = context.trace("GroundingGuard", "guard", "Check final answer against tool facts")
        facts = [item["facts"] for item in state["tool_results"]] + list(
            state["plan_facts"].values()
        )
        violations = grounding_violations(
            candidate.summary + " " + " ".join(candidate.citedFacts), facts
        )
        context.end_trace(
            trace,
            "Ungrounded answer discarded" if violations else "Answer grounded",
            "rejected" if violations else "ok",
        )
        if violations:
            state["notes"].append("GROUNDING_VIOLATION")
            return template_answer(state, runtime)
        state["final_answer"] = _answer(state, candidate.summary, "llm", candidate.citedFacts)
        return state
    except (BudgetExceeded, ProviderFailure) as error:
        _failure(state, error)
        return template_answer(state, runtime)


def build_graph(checkpointer: BaseCheckpointSaver[Any]) -> CompiledStateGraph[Any, Any, Any, Any]:
    graph = StateGraph(AgentState, context_schema=GraphContext)
    nodes = {
        "budget_guard": budget_guard,
        "dispatcher": dispatcher,
        "freight_scout": freight_scout,
        "fleet_compliance": fleet_compliance,
        "route_planner": route_planner,
        "plan_validator": plan_validator,
        "approve": approval_gate,
        "finish": grounding_guard,
        "template": template_answer,
    }
    for name, node in nodes.items():
        graph.add_node(name, node)
    graph.add_edge(START, "budget_guard")
    for name in (
        "budget_guard",
        "dispatcher",
        "freight_scout",
        "fleet_compliance",
        "route_planner",
        "plan_validator",
        "approve",
    ):
        graph.add_conditional_edges(name, lambda state: state["next"], {key: key for key in nodes})
    graph.add_edge("finish", END)
    graph.add_edge("template", END)
    return graph.compile(checkpointer=checkpointer)
