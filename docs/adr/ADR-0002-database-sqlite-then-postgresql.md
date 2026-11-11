# ADR-0002: Database — SQLite in the MVP, PostgreSQL in the portfolio version

- Status: accepted (2026-11-11)
- Date: 2026-11-09

## Context

The application must start locally in a few steps with no Docker and no database server ([`context.md`](../../context.md) → Project Constraints 1a). The database must be in-memory or SQLite. The MVP serves one user and a fleet of 5 vans. The agent runtime needs a durable checkpoint store. After the MVP the project should be deployable on a VPS with a server database. Source: [`docs/report.md`](../report.md) §10.3, §14, §30.2.

## Decision

- **MVP: SQLite**, one local file `apps/api/data/routepilot.db`, opened with `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`. Tests use in-memory SQLite or a temporary file.
- **Agent checkpoints** go to a separate file `agents.db` through `langgraph-checkpoint-sqlite` (fewer write conflicts with the main file).
- **Access:** SQLAlchemy 2 + Alembic (`render_as_batch=True`). Models and queries use **no dialect-specific functions**.
- **Portable type conventions:** UUID as `TEXT`, UTC date-times through a type decorator, money as integer minor units, lengths in mm, distances in m, masses in kg, lists and structures in `JSON` columns ([`DEVELOPMENT.md`](../../DEVELOPMENT.md) §5.2, ADR-0010).
- **Portfolio version:** PostgreSQL 17 with the same models; differences (checkpointer package, job queue) sit behind ports.

## Alternatives

| Alternative | Why it was rejected for the MVP |
|---|---|
| PostgreSQL from the start | needs a database server or Docker, which breaks the hard requirement of an easy local run; no benefit for one user and 5 vans |
| In-memory only (no file) | data and agent checkpoints would vanish on restart; an approval that waits for a human must survive a restart |
| A document or key-value store | the domain is relational (drivers, vehicles, offers, plans, assignments); no ORM/migration tooling advantage |

Costs of SQLite named in the report, with the answer to each:

| Cost | Answer |
|---|---|
| no `SKIP LOCKED` | exactly one worker inside the API process (ADR-0008) |
| no JSONB or arrays | `JSON` columns |
| weak numeric and date types | integers for money, mm, m, kg; `UtcDateTime` type decorator |
| serialised writes | short transactions; checkpoints in a second file |

## Consequences

- Zero setup: the database is created by `alembic upgrade head`; the seed runs on first start.
- Write concurrency is limited (risk R5); acceptable for the MVP, mitigated as above.
- `ALTER TABLE` needs Alembic batch mode; every migration is reviewed by a human.
- Discipline is required: a query that uses a SQLite-only or PostgreSQL-only function is a defect.
- Moving to PostgreSQL later means: a new connection URL, `langgraph-checkpoint-postgres`, a `SKIP LOCKED` queue with a separate worker, and a data migration script — but no model rewrite.
