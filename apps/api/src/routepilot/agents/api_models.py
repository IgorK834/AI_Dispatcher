"""HTTP and SSE payload schemas from FEAT-006 section 6."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from routepilot.agents.schemas import ExplanationOutput, StepKind, TraceStatus


class Wire(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Money(Wire):
    amountMinor: int
    currency: str


class BudgetStatus(Wire):
    usedTokens: int
    limitTokens: int


class AgentStatus(Wire):
    aiEnabled: bool
    reason: str | None = None
    dailyBudget: BudgetStatus


class Proposal(Wire):
    planRef: str
    routePlanId: UUID
    driverRef: str
    variant: Literal["profit", "fastest", "fuel"]
    netProfit: Money
    finishAt: datetime
    fuelL: str
    co2Kg: str


class FinalAnswer(Wire):
    summary: str
    proposals: list[Proposal]
    citedFacts: list[str]
    grounded: bool
    source: Literal["llm", "template"]
    disclaimer: str


class ApprovalPlan(Wire):
    planRef: str
    routePlanId: UUID
    driverRef: str
    driverLabel: str
    offerIds: list[str]
    variant: Literal["profit", "fastest", "fuel"]
    netProfit: Money
    finishAt: datetime
    homeReached: bool


class ApprovalTotals(Wire):
    netProfit: Money
    fuelL: str
    co2Kg: str


class ApprovalPayload(Wire):
    plans: list[ApprovalPlan]
    totals: ApprovalTotals


class PendingApproval(Wire):
    approvalId: UUID
    action: Literal["assign_plan"]
    payload: ApprovalPayload
    expiresAt: datetime


class RunError(Wire):
    code: str
    message: str


class Run(Wire):
    id: UUID
    threadId: UUID
    status: Literal["queued", "running", "waiting_approval", "succeeded", "failed", "cancelled"]
    modelPolicy: dict[str, Any]
    tokensIn: int
    tokensOut: int
    pendingApproval: PendingApproval | None = None
    finalAnswer: FinalAnswer | None = None
    error: RunError | None = None
    startedAt: datetime | None = None
    finishedAt: datetime | None = None


class Message(Wire):
    role: Literal["user", "assistant"]
    content: str
    runId: UUID | None = None
    createdAt: datetime


class Thread(Wire):
    id: UUID
    title: str
    createdAt: datetime
    messages: list[Message] | None = None
    runs: list[Run] | None = None


class ThreadPage(Wire):
    items: list[Thread]
    nextCursor: str | None


class Accepted(Wire):
    runId: UUID


class RouteExplanation(Wire):
    id: UUID
    routePlanId: UUID
    source: Literal["llm", "template"]
    model: str | None = None
    promptVersion: str | None = None
    groundingOk: bool
    output: ExplanationOutput
    disclaimer: str


class RunStarted(Wire):
    runId: UUID
    threadId: UUID
    modelPolicy: dict[str, str]
    startedAt: datetime


class StepStarted(Wire):
    seq: int
    agent: str
    type: StepKind
    toolName: str | None = None
    inputSummary: str = Field(max_length=500)


class StepFinished(Wire):
    seq: int
    agent: str
    type: StepKind
    toolName: str | None = None
    status: TraceStatus
    outputSummary: str = Field(max_length=500)
    durationMs: int
    tokens: dict[str, int] | None = None


class ApprovalRequired(PendingApproval):
    pass


class ApprovalResolved(Wire):
    approvalId: UUID
    decision: Literal["approve", "reject", "edit"]
    decidedBy: UUID


class RunFinished(Wire):
    status: Literal["succeeded", "failed", "cancelled"]
    tokensIn: int
    tokensOut: int
    error: RunError | None = None


EVENT_SCHEMAS: dict[str, type[BaseModel]] = {
    "run_started": RunStarted,
    "step_started": StepStarted,
    "step_finished": StepFinished,
    "approval_required": ApprovalRequired,
    "approval_resolved": ApprovalResolved,
    "final_answer": FinalAnswer,
    "run_finished": RunFinished,
}
