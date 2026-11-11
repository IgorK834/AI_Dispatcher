# ADR-0007: Local run without Docker in the MVP; VPS with Docker Compose after the MVP

- Status: accepted (2026-11-11)
- Date: 2026-11-09

## Context

A hard project constraint: the application starts locally in a few steps, with no Docker, no database server and no required API keys ([`context.md`](../../context.md) → Project Constraints 1a; NFR-014: a clean clone works in ≤ 10 minutes). The risk "running on another person's machine fails" is rated medium probability / high impact (R6 in [`docs/report.md`](../report.md) §36). After the MVP the project should be reachable online as a portfolio piece. Source: report §10.5, §30.

## Decision

**MVP — two local processes, two terminals:**

1. API: `cp .env.example .env` → `uv sync` → `uv run alembic upgrade head` → `uv run uvicorn routepilot.main:app --reload --port 8000`.
2. Web: `cp .env.example .env.local` → `pnpm install` → `pnpm dev` (port 3000).

- Prerequisites: Python 3.13 + uv, Node.js 22 LTS + pnpm.
- Demo data is seeded on first start. The LLM key and the ORS key are optional. Turnstile uses Cloudflare's official test keys locally.
- A `Makefile` offers shortcuts, but the README gives the direct commands, which work without `make`.
- A clean-clone check in CI executes exactly the README commands (FEAT-007).

**Post-MVP — portfolio version:** one self-managed VPS with Docker Compose: Caddy (TLS, reverse proxy), web, api, a separate worker container, PostgreSQL 17, a backup job; deployment from GitHub Actions. Not part of the MVP and not to be implemented without a new specification.

## Alternatives

| Alternative | Why it was rejected for the MVP |
|---|---|
| Docker Compose as the main way to run | requires Docker on the reader's machine; slower first start; contradicts the hard constraint |
| One process serving API and frontend (FastAPI serving a static build) | hides the frontend/backend separation and the CORS configuration that the project wants to show; loses Next.js server features |
| A hosted demo only (no local run) | depends on a paid or rate-limited host and on secrets; the repository must be runnable by itself |
| Managed platforms (PaaS, serverless) for the portfolio version | the in-process worker, SQLite files and long SSE connections fit a single VPS better; lower cost (about 5–15 € per month, approximate) and no lock-in |
| Kubernetes | over-engineering at this scale (forbidden by project constraints) |

## Consequences

- Readers need two runtimes (Python and Node.js) installed; the README states versions and a troubleshooting table exists in [`DEVELOPMENT.md`](../../DEVELOPMENT.md) §6.2.
- Local development uses plain HTTP on `localhost`; cookies are not `Secure` there. HTTPS, HSTS and server hardening belong to the VPS version.
- No Docker image is built in the MVP; CI smoke-tests the API by starting `uvicorn` directly (see FEAT-000 OQ-000-01 about the wording of Gate 9).
- The move to the VPS brings PostgreSQL (ADR-0002), a separate worker (ADR-0008) and real Turnstile keys; starting with test keys in `APP_ENV=production` is a startup error.
