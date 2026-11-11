# ADR-0001: Backend stack — Python 3.13 + FastAPI modular monolith, Next.js 16 frontend

- Status: accepted (2026-11-11)
- Date: 2026-11-09

## Context

RoutePilot AI is an MVP with a deadline (2026-11-15) and later a portfolio project. It needs a REST API with full CRUD, a custom optimisation engine, a multi-agent runtime that can use several LLM providers, and a web interface. The code is written mostly by AI coding agents behind quality gates, so testability, typed contracts and enforceable module boundaries matter. The frontend and the backend must live in separate folders with clear layers. Source: [`docs/report.md`](../report.md) §9, §10.1, §11.

## Decision

- **Backend:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, in `apps/api`. One process: REST API, engine, agents and an in-process worker (a **modular monolith**).
- **Layers in every domain module:** `api` (routers, schemas) → `service` (use cases, transactions) → `domain` (pure models and rules) and `repository` (SQLAlchemy). Routers hold no business logic.
- **Modules:** `shared`, `identity`, `fleet`, `freight`, `routing`, `compliance`, `optimization.engine`, `optimization.jobs`, `agents`, `integrations`. Allowed imports are listed in [`context.md`](../../context.md) → Module Boundaries and enforced by import-linter.
- **Frontend:** Next.js 16 (App Router), React 19, TypeScript strict, in `apps/web`; it calls the API directly from the browser through a client generated from OpenAPI.

## Alternatives

Weighted decision matrix from report §10.1 (scale 1–5, score = Σ(weight × rating)/5):

| Variant | Score | Why it was not chosen |
|---|---|---|
| **A — Next.js + FastAPI** | **83.6** | chosen |
| D — Next.js only (TypeScript full stack) | 77.0 | weakest solver and optimisation ecosystem (rating 2), weaker testability of the engine and of API contracts; agent frameworks and provider SDKs are best supported in Python |
| C — NestJS | 76.6 | the same solver weakness (rating 2); no advantage for agents |
| B — Spring Boot | 72.8 | slowest development (rating 2) and highest deadline risk (rating 2); strong types and solvers do not compensate within one week |

Sensitivity check from the report: with the weight of "solver integrations" lowered to 4 and "development speed" raised to 20, the scores are A 82.0, D 81.8, C 79.8, B 68.0 — A stays first. The move to a multi-agent system strengthens A further (LangGraph, Pydantic AI and provider SDKs are Python-first).

Microservices were not considered for the MVP: they add infrastructure without a benefit at this scale ([`context.md`](../../context.md) → Project Constraints 9).

## Consequences

- Two languages and two toolchains (uv and pnpm); the OpenAPI contract and generated TypeScript types bridge them (ADR-0009).
- Python's type safety is weaker than Java's or TypeScript's (rating 3 in the matrix); mitigated with `mypy --strict`, Pydantic at the boundaries and property tests.
- CPU-bound optimisation in the API process needs a process pool (ADR-0008).
- Boundaries must be enforced by tools (import-linter, ESLint boundaries), otherwise a monolith erodes.
- Changing this stack later is an architecture change and needs a new ADR.
