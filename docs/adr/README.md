# Architecture Decision Records

Each ADR records one decision: the context, what was decided, which alternatives were rejected and why, and the consequences. The source of the content is [`docs/report.md`](../report.md) §37 (summary) and the sections named in each record. The template is in [`context.md`](../../context.md) → Specification Templates.

> **Status of all records: `accepted`** (by the owner, 2026-11-11; ADR-0001 … 0014 proposed 2026-11-09, ADR-0015 written and accepted 2026-11-11). Nothing described here is implemented yet.

| ADR | Decision | Main report sections |
|---|---|---|
| [ADR-0001](ADR-0001-backend-stack.md) | Python 3.13 + FastAPI modular monolith with layers; Next.js 16 frontend | §9, §10.1, §11 |
| [ADR-0002](ADR-0002-database-sqlite-then-postgresql.md) | SQLite (WAL) in the MVP; portable SQLAlchemy; PostgreSQL 17 in the portfolio version | §10.3, §14 |
| [ADR-0003](ADR-0003-timocom-integration.md) | Ports and adapters; mock in the TIMOCOM v3 format; shared mapper; no scraping; retention | §5, §6, §15.1, §16 |
| [ADR-0004](ADR-0004-optimization-engine.md) | Branch-and-Bound per driver (top-K) + exact fleet assignment + independent validators | §18, §19 |
| [ADR-0005](ADR-0005-routing.md) | Demo city matrix in the repo + optional ORS with a cache + haversine fallback | §10.4, §15.2, §21 |
| [ADR-0006](ADR-0006-ai-orchestration-langgraph.md) | LangGraph: custom supervisor + 3 specialists, deterministic tools, guards, `interrupt`, SQLite checkpoints | §10.2, §22, §23 |
| [ADR-0007](ADR-0007-local-run-and-deployment.md) | Local run without Docker in the MVP; VPS + Docker Compose + Caddy after the MVP | §10.5, §30 |
| [ADR-0008](ADR-0008-async-processing.md) | Jobs table + worker inside the API process; separate container + `SKIP LOCKED` after the MVP | §11.1, §30.2 |
| [ADR-0009](ADR-0009-api-crud-cors-contracts.md) | REST with full CRUD, problem+json, generated and committed OpenAPI, CORS allowlist | §11.3, §28, §29 |
| [ADR-0010](ADR-0010-units-and-money.md) | SI units; money as integer minor units; mm / m / kg integers in the database; UTC | §13.3, §14 |
| [ADR-0011](ADR-0011-driver-working-time.md) | `DriverRules` port with two profiles; an international plan uses the 561 profile | §20 |
| [ADR-0012](ADR-0012-authentication.md) | Cookie sessions, Argon2id, Turnstile (test keys locally), CSRF token, roles | §29 |
| [ADR-0013](ADR-0013-llm-providers.md) | LangChain `init_chat_model`, model policy per role, optional key | §15.3, §22.3 |
| [ADR-0014](ADR-0014-van-capacity.md) | Mass + EUR-pallet equivalents + declared pallet places; 2D geometry after the MVP | §16.2, §16.3 |
| [ADR-0015](ADR-0015-frontend-ui-components-and-design-system.md) | Own design system "Clear Route v3" on Tailwind + Radix UI primitives; no shadcn/ui (accepted 2026-11-11) | §9 (superseded in part); [`docs/design/`](../design/README.md) |

Rules:

- A new decision that changes architecture, adds a framework, service or runtime agent needs a new ADR and human approval ([`context.md`](../../context.md) → Architecture Principles 1).
- An accepted ADR is not edited to change its decision; a new ADR supersedes it (`Status: superseded by ADR-mmmm`).
- File name: `ADR-nnnn-short-title.md`.
