"""Agent application service: asynchronous runs, ownership and approval decisions."""

import asyncio
import hashlib
from datetime import datetime
from threading import RLock
from typing import Any, cast
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from routepilot.agents.graph import (
    AgentState,
    GraphContext,
    build_graph,
    initial_state,
    template_answer,
)
from routepilot.agents.guards import TokenBudget
from routepilot.agents.models import ModelRegistry, Role
from routepilot.agents.ports import AgentStore, ToolExecutor
from routepilot.agents.prompt_loader import load_prompts
from routepilot.agents.schemas import MessageCreate, ResumeInput
from routepilot.shared.auth import Principal
from routepilot.shared.clock import Clock
from routepilot.shared.config import Settings
from routepilot.shared.errors import DomainError

ACTIVE = {"queued", "running", "waiting_approval"}


def _uuid(value: Any) -> UUID:
    return UUID(str(value))


class AgentService:
    def __init__(
        self,
        store: AgentStore,
        registry: ModelRegistry,
        tools: ToolExecutor,
        clock: Clock,
        settings: Settings,
        checkpointer: BaseCheckpointSaver[Any],
        *,
        campaign_budgets: list[TokenBudget] | None = None,
        live_campaign: bool = False,
    ) -> None:
        self.store, self.registry, self.tools, self.clock, self.settings = (
            store,
            registry,
            tools,
            clock,
            settings,
        )
        self.graph = build_graph(checkpointer)
        self.prompts = load_prompts()
        self.campaign_budgets = campaign_budgets or []
        self.live_campaign = live_campaign
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._contexts: dict[UUID, GraphContext] = {}
        self._daily: dict[tuple[UUID, str], TokenBudget] = {}
        self._slots = asyncio.Semaphore(2)
        self._lock = RLock()

    def status(self, user: Principal) -> dict[str, Any]:
        return {
            "aiEnabled": self.registry.enabled,
            "reason": None if self.registry.enabled else "AI_UNAVAILABLE",
            "dailyBudget": {
                "usedTokens": self.store.daily_usage(user.id, self.clock.now().date().isoformat()),
                "limitTokens": self._limit(user),
            },
        }

    def _limit(self, user: Principal) -> int:
        return (
            self.settings.agent_daily_token_budget_demo
            if user.role == "demo"
            else self.settings.agent_daily_token_budget
        )

    def create_thread(self, user: Principal, title: str | None) -> dict[str, Any]:
        return self.store.create(
            "agent_threads",
            {
                "user_id": user.id,
                "title": title or "New conversation",
                "created_at": self.clock.now(),
                "updated_at": self.clock.now(),
            },
        )

    def _thread(self, user: Principal, id: UUID) -> dict[str, Any]:
        row = self.store.get("agent_threads", _uuid(id))
        if row is None or _uuid(row["user_id"]) != user.id:
            raise DomainError("NOT_FOUND", 404)
        return row

    def threads(self, user: Principal) -> list[dict[str, Any]]:
        return self.store.find("agent_threads", user_id=user.id)

    def thread(self, user: Principal, id: UUID) -> dict[str, Any]:
        row = self._thread(user, id)
        runs = self.store.find("agent_runs", thread_id=id)
        row["runs"] = [self._run_view(run) for run in runs]
        row["messages"] = []
        for run in runs:
            row["messages"].append(
                {
                    "role": "user",
                    "content": run["user_message"],
                    "runId": str(run["id"]),
                    "createdAt": run["created_at"],
                }
            )
            if run.get("final_answer"):
                row["messages"].append(
                    {
                        "role": "assistant",
                        "content": run["final_answer"]["summary"],
                        "runId": str(run["id"]),
                        "createdAt": run["finished_at"],
                    }
                )
        return row

    def message(
        self, user: Principal, thread_id: UUID, body: MessageCreate, idempotency_key: str | None
    ) -> dict[str, Any]:
        thread_id = _uuid(thread_id)
        self._thread(user, thread_id)
        self.expire()
        if not self.registry.enabled:
            raise DomainError("AI_UNAVAILABLE", 503)
        key = (
            hashlib.sha256(f"{user.id}:{thread_id}:{idempotency_key}".encode()).hexdigest()
            if idempotency_key
            else None
        )
        with self._lock:
            if key:
                existing = self.store.find("agent_runs", idempotency_key=key)
                if existing:
                    if existing[0]["user_message"] != body.content:
                        raise DomainError("IDEMPOTENCY_CONFLICT")
                    return {"runId": _uuid(existing[0]["id"])}
            if any(
                run["status"] in ACTIVE
                for run in self.store.find("agent_runs", thread_id=thread_id)
            ):
                raise DomainError("RUN_IN_PROGRESS")
            used = self.store.daily_usage(user.id, self.clock.now().date().isoformat())
            if used >= self._limit(user):
                raise DomainError("AI_BUDGET_EXCEEDED", 429)
            policy = self.registry.policy.model_dump(mode="json", by_alias=True, exclude_none=True)
            policy["promptVersions"] = {
                role: prompt.version for role, prompt in self.prompts.items()
            }
            run = self.store.create(
                "agent_runs",
                {
                    "thread_id": thread_id,
                    "status": "queued",
                    "user_message": body.content,
                    "idempotency_key": key,
                    "model_policy": policy,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cost_estimate_minor": 0,
                    "currency": "USD",
                    "created_at": self.clock.now(),
                    "started_at": None,
                    "finished_at": None,
                    "final_answer": None,
                    "error": None,
                },
            )
            run_id = _uuid(run["id"])
            config: RunnableConfig = {"configurable": {"thread_id": str(thread_id)}}
            previous = self.graph.get_state(config).values
            state = initial_state(
                run_id, user, body.content, body.locale or user.locale, previous.get("aliases")
            )
            self._tasks[run_id] = asyncio.create_task(self._execute(user, run_id, thread_id, state))
            return {"runId": run_id}

    def _owned_run(self, user: Principal, id: UUID) -> dict[str, Any]:
        row = self.store.get("agent_runs", _uuid(id))
        if row is None:
            raise DomainError("NOT_FOUND", 404)
        self._thread(user, _uuid(row["thread_id"]))
        return row

    def _run_view(self, row: dict[str, Any]) -> dict[str, Any]:
        pending = self.store.find("approval_requests", run_id=row["id"], status="pending")
        return {
            "id": row["id"],
            "threadId": row["thread_id"],
            "status": row["status"],
            "modelPolicy": row["model_policy"],
            "tokensIn": row["tokens_in"],
            "tokensOut": row["tokens_out"],
            "pendingApproval": (
                {
                    "approvalId": pending[0]["id"],
                    "action": pending[0]["action"],
                    "payload": pending[0]["payload"],
                    "expiresAt": pending[0]["expires_at"],
                }
                if pending
                else None
            ),
            "finalAnswer": row.get("final_answer"),
            "error": row.get("error"),
            "startedAt": row.get("started_at"),
            "finishedAt": row.get("finished_at"),
        }

    def get_run(self, user: Principal, id: UUID) -> dict[str, Any]:
        self.expire()
        return self._run_view(self._owned_run(user, id))

    def events(self, user: Principal, id: UUID, after: int = 0) -> list[dict[str, Any]]:
        self.get_run(user, id)
        return self.store.events(_uuid(id), after)

    def resume(self, user: Principal, run_id: UUID, body: ResumeInput) -> dict[str, Any]:
        self.expire()
        run_id = _uuid(run_id)
        run = self._owned_run(user, run_id)
        approval = self.store.get("approval_requests", body.approvalId)
        if (
            run["status"] != "waiting_approval"
            or approval is None
            or _uuid(approval["run_id"]) != run_id
            or approval["status"] != "pending"
        ):
            raise DomainError("APPROVAL_NOT_PENDING")
        if not self.store.decide(body.approvalId, user.id, body.decision, self.clock.now()):
            raise DomainError("APPROVAL_NOT_PENDING")
        self.store.emit(
            run_id,
            "approval_resolved",
            {
                "approvalId": str(body.approvalId),
                "decision": body.decision,
                "decidedBy": str(user.id),
            },
        )
        self.store.update("agent_runs", run_id, {"status": "queued"})
        self._tasks[run_id] = asyncio.create_task(
            self._execute(
                user,
                run_id,
                _uuid(run["thread_id"]),
                Command(resume={"decision": body.decision, "comment": body.comment}),
            )
        )
        return self.get_run(user, run_id)

    def expire(self) -> None:
        for approval in self.store.find("approval_requests", status="pending"):
            expiry = approval["expires_at"]
            if isinstance(expiry, str):
                expiry = datetime.fromisoformat(expiry)
            if expiry > self.clock.now():
                continue
            self.store.update("approval_requests", _uuid(approval["id"]), {"status": "expired"})
            run_id = _uuid(approval["run_id"])
            error = {"code": "APPROVAL_EXPIRED", "message": "Approval expired"}
            self.store.update(
                "agent_runs",
                run_id,
                {"status": "cancelled", "error": error, "finished_at": self.clock.now()},
            )
            row = self.store.get("agent_runs", run_id)
            if row:
                self.store.emit(
                    run_id,
                    "run_finished",
                    {
                        "status": "cancelled",
                        "tokensIn": row["tokens_in"],
                        "tokensOut": row["tokens_out"],
                        "error": error,
                    },
                )

    async def _execute(
        self, user: Principal, run_id: UUID, thread_id: UUID, input: AgentState | Command[Any]
    ) -> None:
        async with self._slots:
            day = self.clock.now().date().isoformat()
            daily = self._daily.setdefault(
                (user.id, day), TokenBudget(self._limit(user), self.store.daily_usage(user.id, day))
            )
            context = GraphContext(
                self.registry,
                self.tools,
                self.store,
                self.clock,
                self.settings,
                user,
                run_id,
                self.campaign_budgets,
                self.live_campaign,
                self.prompts,
                daily_budget=daily,
            )
            self._contexts[run_id] = context
            self.store.update(
                "agent_runs", run_id, {"status": "running", "started_at": self.clock.now()}
            )
            if not any(event["event"] == "run_started" for event in self.store.events(run_id)):
                self.store.emit(
                    run_id,
                    "run_started",
                    {
                        "runId": str(run_id),
                        "threadId": str(thread_id),
                        "modelPolicy": {
                            role: self.registry.policy.for_role(cast(Role, role)).model
                            for role in self.prompts
                            if getattr(self.registry.policy, role) or self.registry.policy.default
                        },
                        "startedAt": self.clock.now().isoformat(),
                    },
                )
            config: Any = {
                "configurable": {"thread_id": str(thread_id)},
                "recursion_limit": self.settings.agent_recursion_limit * 4 + 10,
            }
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(self.graph.invoke, input, config, context=context),
                    timeout=self.settings.agent_run_timeout_s,
                )
                if result.get("__interrupt__"):
                    return
            except (TimeoutError, GraphRecursionError):
                context.cancelled.set()
                state = self.graph.get_state(config).values
                state["error"] = {"code": "BUDGET_EXCEEDED", "message": "Run limit reached"}
                from langgraph.runtime import Runtime

                result = template_answer(cast(AgentState, state), Runtime(context=context))
            except Exception:
                context.cancelled.set()
                self.store.update(
                    "agent_runs",
                    run_id,
                    {
                        "status": "failed",
                        "error": {"code": "INTERNAL_ERROR", "message": "Run failed"},
                        "finished_at": self.clock.now(),
                    },
                )
                self.store.emit(
                    run_id,
                    "run_finished",
                    {
                        "status": "failed",
                        "tokensIn": 0,
                        "tokensOut": 0,
                        "error": {"code": "INTERNAL_ERROR", "message": "Run failed"},
                    },
                )
                return
            status = (
                "succeeded"
                if result.get("validated_plans") or not result.get("error")
                else "failed"
            )
            self.store.update(
                "agent_runs",
                run_id,
                {
                    "status": status,
                    "final_answer": result["final_answer"],
                    "error": result.get("error"),
                    "finished_at": self.clock.now(),
                },
            )
            self.store.emit(run_id, "final_answer", result["final_answer"])
            row = self.store.get("agent_runs", run_id)
            if row:
                self.store.emit(
                    run_id,
                    "run_finished",
                    {
                        "status": status,
                        "tokensIn": row["tokens_in"],
                        "tokensOut": row["tokens_out"],
                        "error": row.get("error"),
                    },
                )

    async def wait(self, run_id: UUID) -> None:
        task = self._tasks.get(_uuid(run_id))
        if task:
            await asyncio.shield(task)

    async def stop(self) -> None:
        for context in self._contexts.values():
            context.cancelled.set()
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
