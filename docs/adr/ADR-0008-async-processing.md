# ADR-0008: Asynchronous processing — jobs table and a worker inside the API process

- Status: accepted (2026-11-11)
- Date: 2026-11-09

## Context

Fleet optimisation is CPU-bound and may take seconds (target p95 ≤ 15 s). Agent runs take tens of seconds and can pause for human approval. HTTP requests must return quickly, progress must be visible, and unfinished work must not be lost silently on restart. The MVP may not use Redis, Celery, RabbitMQ or any extra service ([`context.md`](../../context.md) → Project Constraints 6 and dependency rules), and SQLite has no `SKIP LOCKED`. Source: [`docs/report.md`](../report.md) §11.1, §30.2.

## Decision

- **Jobs are rows.** `POST /optimization-jobs` stores a job with its input snapshot and returns `202` + `Location`. The client polls the job resource. Agent runs are rows in `agent_runs` and stream their steps over SSE.
- **One worker inside the API process:** an `asyncio` background task started in the application lifespan takes queued jobs one at a time and runs the engine in a `ProcessPoolExecutor(max_workers=1)` so that the event loop stays responsive.
- **Heartbeat and recovery:** the worker updates `heartbeat_at`; on startup, a job stuck in `running` is re-queued (limited attempts) or marked failed.
- **Idempotency:** an `Idempotency-Key` on job creation prevents duplicates.
- **Agent runs** execute as `asyncio` tasks in the same process (IO-bound); they enqueue optimisation jobs on the CPU worker.
- **Post-MVP:** a separate worker container that claims jobs with `SELECT … FOR UPDATE SKIP LOCKED` on PostgreSQL.

## Alternatives

| Alternative | Why it was rejected for the MVP |
|---|---|
| Synchronous optimisation inside the request | blocks the request for seconds; no progress, no recovery; blocks the event loop |
| FastAPI `BackgroundTasks` without a jobs table | state lives only in memory; lost on restart; no status resource for the client |
| Celery / RQ / Dramatiq with Redis or RabbitMQ | extra services break the "no Docker, no extra services" constraint; explicitly forbidden dependencies |
| A separate worker process polling SQLite | two processes writing one SQLite file without `SKIP LOCKED` adds lock contention and a third terminal to the run steps |
| Threads for the engine | the engine is pure Python and CPU-bound; threads would not run in parallel with the event loop effectively |

## Consequences

- One job at a time: enough for one dispatcher and 5 vans; a queue forms under load (a per-user limit of queued jobs is specified in FEAT-004).
- The engine snapshot and result must be picklable (they cross a process boundary).
- A crash of the API process also stops the worker; recovery on startup handles it.
- Write concurrency in SQLite stays low: one worker, short transactions, agent checkpoints in a separate file (ADR-0002).
- The job-claiming code is the part that changes when moving to PostgreSQL; it is isolated in `optimization.jobs`.
