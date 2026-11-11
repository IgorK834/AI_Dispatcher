# ADR-0006: AI orchestration — LangGraph with a custom supervisor, deterministic tools and guards

- Status: accepted (2026-11-11)
- Date: 2026-11-09

## Context

The product is an AI dispatcher: a human asks in natural language and gets a recommendation they can approve. The AI must not be a source of truth for mass, capacity, working time, feasibility, costs or prices ([`context.md`](../../context.md) → Project Constraints 4). Requirements on the orchestration: explicit control of the flow, a durable pause for human approval, swappable LLM providers (the owner uses Google Gemini; Anthropic and OpenAI must work too), deterministic tests without a network, event streaming to the UI, local run without a hosted agent service. Source: [`docs/report.md`](../report.md) §10.2, §22, §23.

## Decision

- **Framework: LangGraph 1.2.x** with a `StateGraph` and explicit typed state.
- **Topology: a custom supervisor** (the Dispatcher node with conditional edges) plus three specialists — **Freight Scout**, **Fleet & Compliance**, **Route Planner**. The package `langgraph-supervisor` is not used.
- **Deterministic guard nodes without an LLM:** `PlanValidator`, `GroundingGuard`, `BudgetGuard`, `ApprovalGate`.
- **Tools are thin adapters** over the same application services as the HTTP API, with per-agent allowlists. Every number in an answer comes from tool results.
- **One write tool, `assign_plan`**, executed only by `ApprovalGate` after `interrupt()` and a human `resume(approve)`.
- **Durability:** `langgraph-checkpoint-sqlite` in a separate file `agents.db`.
- **Streaming:** steps are stored in `agent_steps` and sent to the UI as server-sent events.
- **The application works without AI** (manual optimizer, template explanations).

## Alternatives

**Framework** — weighted matrix from report §10.2 (score = Σ(weight × rating)/5):

| Variant | Score | Why it was not chosen |
|---|---|---|
| **LangGraph** | **92.6** | chosen: best flow control, `interrupt` with durable checkpoints, provider swap, streaming |
| Pydantic AI | 83.6 | a good alternative (better typing, simpler), but weaker durable interrupts and less recognised |
| Custom loop on a provider SDK | 70.0 | full control, but human-in-the-loop durability and provider swap would have to be built by hand |
| CrewAI | 63.4 | weak flow control, weak deterministic testing and interrupts |
| Claude Agent SDK | 52.4 | not provider-swappable (the owner uses Gemini); aimed at file-and-code agents |
| Managed Agents (Claude) | 50.6 | hosted and single-provider; no local run |

**Topology** — assessment from report §23:

| Variant | Assessment |
|---|---|
| A single LLM with about 15 tools | simplest, but the prompt grows and loses precision; weak separation of permissions |
| Deterministic workflow with AI steps | most predictable, but it does not give a conversation with flexible tasks |
| **Supervisor + 3 specialists + deterministic nodes** | **chosen**: split of domains and permissions, shorter prompts, testable subgraphs, approvals, a readable trace |
| An agent swarm without a supervisor | hard to control and to test |

`langgraph-supervisor` (0.0.31, last release 2025-11) was rejected in favour of a hand-written supervisor node: more control, simpler tests, no dependence on a young package.

## Consequences

- More LLM calls than a single-agent design; mitigated by step, tool-call, token and time budgets and by allowing a cheaper model per role after evaluation (ADR-0013).
- A learning curve and some boilerplate (the lowest LangGraph rating in the matrix is "deadline risk": 3). Cut-list fallback: merge the Freight Scout into the Dispatcher.
- Node code before `interrupt()` must be idempotent, because the node restarts on resume; `interrupt()` must not be wrapped in a bare `try/except`.
- Any new agent needs an ADR, a specification and an evaluation; any new write tool needs `interrupt` — otherwise the pull request is rejected.
- Agent behaviour is tested on fake models in CI; live evaluations run manually with a budget.
- Newest-version risk (LangGraph 1.2, R12): versions are pinned and the interrupt behaviour is verified during FEAT-006.
