# ADR-0017: Event-driven deterministic evaluation, proposals and one approval service

- Status: proposed
- Date: 2026-11-18
- Amends: [ADR-0006](ADR-0006-ai-orchestration-langgraph.md) (no new runtime agent; the ApprovalGate delegates to a shared service) and [ADR-0008](ADR-0008-async-processing.md) (job kinds, leases, outbox)
- Specifications: [FEAT-014](../../specs/FEAT-014-commitments-and-execution.md), [FEAT-015](../../specs/FEAT-015-event-driven-proposals.md), [FEAT-016](../../specs/FEAT-016-agent-tools-for-planning.md)
- Research: [`docs/research/2026-11-17-ai-dispatcher-evolution.md`](../research/2026-11-17-ai-dispatcher-evolution.md) §8, §9.3, §9.5

## Context

Runtime agent runs start only from chat (`agents/service.py:131-189`). Nothing reacts to new offers, cancellations or delays.

REQ-025 ("event-driven mode: automatic rating of new offers and an inbox of proposals") was post-MVP without a specification. The constraints remain:
- `context.md` 1a and 6: local run without Docker, no Redis or queue brokers;
- LangGraph Agent Server self-hosting requires an Enterprise licence plus PostgreSQL and Redis (research note §8.1).

Assignment uniqueness relies on an in-process lock (FEAT-014). Feasibility, costs and law must never come from an LLM (`context.md` Project Constraint 4).

## Decision

1. **Transactional outbox in SQLite.** Business changes and their `outbox_events` row are written in one transaction. A relay inside the existing worker turns events into jobs with idempotency keys (at-least-once delivery, idempotent consumers).
2. **Job kinds on the existing worker** (ADR-0008): `optimize`, `evaluate_offer`, `replan`, `expire_proposals`. Jobs are claimed with `BEGIN IMMEDIATE`, with leases, priorities, attempts and cancel.
3. **Deterministic services, not agents.**
   - `OfferEvaluationService` inserts after committed stops.
   - `ReplanService` handles delays and cancellations.
   - Both use the engine and the validators and produce **proposals** (`proposals` table, dedup key, expiry).
   - **No new LLM agent.** An LLM may explain a proposal through the existing `ExplanationService`, which has a template fallback.
4. **One `ApprovalService`.**
   - Every write that commits or changes freight goes through `ApprovalService.approve`: role check, version re-validation, a `BEGIN IMMEDIATE` write, audit.
   - It is used by the REST proposal inbox and by the LangGraph ApprovalGate after `interrupt()`.
   - The write tools (`assign_plan`, the new `amend_assignment`) stay reachable only from the ApprovalGate.
5. **PostgreSQL** (ADR-0002) only when multi-host or multi-writer operation, `SKIP LOCKED` or `LISTEN/NOTIFY` are needed.

## Alternatives

| Alternative | Why not |
|---|---|
| An autonomous "monitor" LLM agent | feasibility must be deterministic; cost and latency (50k–76k tokens per run, development log P13); harder to test |
| LangGraph Agent Server cron/background runs | Enterprise licence + PostgreSQL + Redis; breaks the local-run rule |
| Redis/Celery/RabbitMQ | forbidden by `context.md` |
| APScheduler with a shared job store | its FAQ warns against sharing a job store across processes; unnecessary with a polling worker |
| Keep approvals only inside the graph | deterministic proposals would need a graph thread and checkpoint each, for no benefit |

## Consequences

- **Owner decision needed (`context.md` AI Architecture Rule 3).** Today it says the only write tool is executed "only after `interrupt()` and a `resume` with the decision `approve`". This ADR proposes to add: "or through `ApprovalService.approve` called by the REST proposal inbox for a deterministic proposal, by a user with the role `dispatcher`/`admin`". The human-approval requirement itself does not change.
- New tables (`outbox_events`, `proposals`, `assignment_offers`, `stop_events`) and job columns: migrations with human review.
- SQLite write contention grows with events. Mitigation: short transactions, batching in the relay, priorities, a busy-retry metric.
- Approval expiry becomes eager (periodic job) instead of lazy.
