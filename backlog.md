# RoutePilot AI — Backlog

> **Status (2026-11-11):** specifications FEAT-000 … FEAT-007 and FEAT-009 are `approved`, ADR-0001 … 0014 are `accepted`, golden cases GOLD-001 … 010 are `approved`. **Nothing is implemented.** FEAT-008 (P1) is `draft` and cannot be implemented until the owner approves it.
> **Deadline:** MVP 2026-11-15 (tag `v0.1.0`), later a portfolio project.
> **Sources:** [`context.md`](context.md) (rules, delivery plan, cut order) > [`specs/`](specs/README.md) (what to build, ACs) > [`docs/report.md`](docs/report.md) §33 (day plan). If this file disagrees with them, they win — report the difference.

This file turns the approved specifications into **slices**: one slice = one task brief = one branch/PR (≤ ~400 lines of manual changes, `context.md` → Agent Collaboration Protocol 7). Every AC of every approved specification belongs to exactly one slice. A slice is done when the Definition of Done in `context.md` holds and its completion report is filed.

**Legend**

- **Status:** `todo` · `in progress` · `review` · `done` · `blocked`
- **Lock:** shared files the slice changes (one author at a time; `context.md` → Shared files). 🔒 = needs human approval or review before merge (migrations, workflows, prompts, model policy, golden values, external calls, releases).
- **Depends:** slices that must be merged first (or mocked, where noted).
- AC ranges are inclusive: `04–09` means AC-…-04 to AC-…-09.

---

## 1. Schedule check

| Day | Planned in `context.md` | Actual (2026-11-11) |
|---|---|---|
| 11-09 | specifications, golden cases, ADRs, agent files | ✅ done; approved on 11-11 |
| 11-10 | FEAT-000, FEAT-001, FEAT-002 | ❌ not started |
| 11-11 | FEAT-003, FEAT-004 | ❌ not started (today) |
| 11-12 | FEAT-006 | — |
| 11-13 | FEAT-005 | — |
| 11-14 | FEAT-007 | — |
| 11-15 | FEAT-009, `v0.1.0` | — |

The plan is about **two days behind**. Section 3 proposes how to catch up; it is a proposal, the owner decides.

---

## 2. Owner actions and blockers

These cannot be done by a coding agent alone (`context.md` → Operations that need human confirmation, Human Approval Requirements).

| # | Action | Needed by | Status |
|---|---|---|---|
| O-1 | Initialise the git repository and create the public GitHub repository (the working folder is not a git repository yet). | 000/1 (branches, worktrees), 000/5 (`ci-fast`) | todo |
| O-2 | Review and approve `.github/workflows/ci-fast.yml`, later `ci-full.yml` and `ai-evals.yml`. 🔒 | 000/5, 007/3 | todo |
| O-3 | Review the initial Alembic migration `0001_initial` (all MVP tables, OQ-001-05). 🔒 | 001/1 | todo |
| O-4 | Approve reading the official TIMOCOM OpenAPI 3.0.6 file once to create the mapper fixtures and enumeration values (OQ-002-02). 🔒 | 002/3 | todo |
| O-5 | **ORS key and fixtures.** AC-FEAT-004-04 needs *recorded* ORS matrix and directions responses (OQ-004-03: "do not write the adapter from memory"). Decision (2026-11-11): the owner gets a free ORS key. The owner puts it in `apps/api/.env` as `ORS_API_KEY` (gitignored, never in chat, code or fixtures) and approves the recording calls; recorded fixtures are checked for the key before commit. The committed `routing-matrix.json` stays the haversine variant unless the owner revises OQ-004-02. | 004/2 | in progress (owner) |
| O-6 | Approve the agent prompts `agents/prompts/<agent>.v1.md` and `AGENT_MODEL_POLICY`; confirm the Gemini model id against the provider list with one live run (OQ-006-01). 🔒 | 006/1, 006/3, 006/7 | in progress (owner): model id confirmed, prompts v1 approved, fallback set 2026-11-12; smoke run reached `request_approval` but timed out at 120 s before `approval_required`; no live run reached `approval_required` yet |
| O-7 | Agree a token budget and run `ai-evals` live (paid API). 🔒 | 006/7, 007/3 | in progress (owner): budget 500 000 tokens in total: 80 000 smoke + 420 000 one eval batch (2026-11-12), 484 835 counted; batch ran 18 of 40 scenarios (all injection, 0 write violations); 22 agent scenarios not run; allowance exhausted |
| O-8 | Fill `scripts/docs_denylist.txt` (OQ-007-02). | 007/4 | todo |
| O-9 | Check the terms of the suggested map style (OpenFreeMap) before any public deployment (OQ-005-01). | after the MVP | todo |
| O-10 | Manual clean-clone run on the owner's machine (OQ-007-01) and the FEAT-005 UX checklist review. | 007/4, 005/9 | todo |
| O-11 | Record the demo video and screenshots; tick the pre-publication checklist; create the tag `v0.1.0`. 🔒 | 009/1, 009/2 | todo |

---

## 3. Catch-up proposal (needs owner decision)

The engine (FEAT-003) is pure and needs only the shared kernel (001/1) and `cities.json` (002/1); the frontend can start against MSW handlers generated from `contracts/openapi.json` (FEAT-005 §9). That allows three parallel lanes in separate worktrees with disjoint files:

| Day | Lane A — backend platform | Lane B — engine | Lane C — web |
|---|---|---|---|
| 11-11 | 000/1, 000/3, 000/4, 000/5 → 001/1 | — (waits for 001/1) | 000/2 |
| 11-12 | 001/2 … 001/7, 002/1 … 002/5 | 003/1 … 003/4 | 005/1, 005/2 (MSW) |
| 11-13 | 004/1, 004/3 … 004/5, 006/1 … 006/3 | 003/5 … 003/8 | 005/3 … 005/6 |
| 11-14 | 006/4 … 006/6, 007/1, 007/3 | 007/5 | 005/7, 005/8, 007/2 |
| 11-15 | 007/4, 009/2 | — | 005/9, 009/1 |

If the lanes still slip, apply the cut order of `context.md` in sequence. Items 1 and 2 (offer-text interpretation, road choice) are already out because FEAT-008 is `draft`; item 3 (full admin panel) is P1. Next cuts: (4) full translations, (5) Freight Scout merged into the Dispatcher, (6) ORS → repo matrix / haversine only, (7) `ci-full` → E2E smoke.
**Never cut:** engine + validators + property tests, `DriverRules`, CRUD + CORS, easy local run, `interrupt` before a write, `GroundingGuard`, login with captcha, `ci-fast`, the path without AI, `README.md` with instructions, the recording.

---

## 4. P0 backlog

### FEAT-000 — Monorepo and `ci-fast` · [spec](specs/FEAT-000-monorepo-and-ci.md) · planned 11-10

| Slice | Scope | ACs (AC-FEAT-000-…) | Depends | Lock | Status |
|---|---|---|---|---|---|
| 000/1 | API skeleton: FastAPI app factory, layered package folders, pydantic-settings, structlog with `request_id`, `/health`, `/ready` (`503 NOT_READY` behind head), CORS middleware, problem+json handler, `apps/api/.env.example`, production-defaults check | 02, 03, 12 | O-1 | `uv.lock`, `apps/api/.env.example` | todo |
| 000/2 | Web skeleton: Next.js 16 App Router, TypeScript strict (pin 6.0.x per OQ-000-04, re-check on the day), Tailwind themed from `docs/design/tokens.json` + design-system fonts via `next/font` (ADR-0015, no shadcn/ui), next-intl EN/PL with switch, placeholder home, `apps/web/.env.example` | 04 | O-1 | `pnpm-lock.yaml`, `messages/*.json`, `apps/web/.env.example` | todo |
| 000/3 | Tooling: `Makefile` shortcuts, `make check`, pre-commit (ruff, gitleaks, prettier), import-linter contracts for every backend boundary row, clean install from lockfiles | 01, 05, 06, 11 | 000/1, 000/2 | `Makefile` | todo |
| 000/4 | Scripts: `export_openapi.py` (+ `--check`), `trace.py` (+ `--check`), `check_spec_touch.py` (+ `--agent-docs`); first `contracts/openapi.json` | 07, 08, 09, 13 | 000/1 | `contracts/openapi.json` | todo |
| 000/5 | `ci-fast.yml`: gates 1, 2, 3, 3a, 4, 5, 8a, 8c, 9, 10 as named jobs, no network calls | 10 | 000/3, 000/4, O-2 | 🔒 `.github/workflows/**` | todo |

### FEAT-001 — Domain, SQLite, CRUD, auth · [spec](specs/FEAT-001-domain-sqlite-crud-auth.md) · planned 11-10

| Slice | Scope | ACs (AC-FEAT-001-…) | Depends | Lock | Status |
|---|---|---|---|---|---|
| 001/1 | `shared` kernel (Money, units, ids, `Clock`, `UtcDateTime`, `DomainError`), SQLite engine with PRAGMAs, Alembic setup (`render_as_batch`), `0001_initial` with all MVP tables + `app_meta` | 01, 02, 03 | 000/1, O-3 | 🔒 `apps/api/migrations/**` | todo |
| 001/2 | `identity`: Argon2id, server-side sessions (hashed token, TTL), `CaptchaVerifier` (Turnstile, test keys), login / logout / me, rate limits, first-start `admin` and `demo` accounts, no registration route | 20, 21, 22, 25, 26, 28, 29, 31, 33 | 001/1 | `.env.example`, `contracts/openapi.json` | todo |
| 001/3 | CSRF double-submit token, `Origin` check (including login), role dependencies `require_user` / `require_role`, security headers | 23, 24, 34 | 001/2 | — | todo |
| 001/4 | Drivers CRUD (cursor pagination, filters, `version`, soft delete via `DriverUsageChecker`) and driver state (`POST`/`GET …/state`) | 04, 05, 06, 07, 08, 09, 15 | 001/3 | `contracts/openapi.json` | todo |
| 001/5 | Vehicles CRUD and cost-profiles CRUD | 10, 11 | 001/4 | `contracts/openapi.json` | todo |
| 001/6 | Freight offers: manual CRUD (`source=manual`, `MAN-` ids), provider offers read-only, list filters with completeness and provenance (cities fixture until 002/1) | 12, 13, 14 | 001/3 | `contracts/openapi.json` | todo |
| 001/7 | Cross-cutting: problem+json for every error code with `requestId`, CORS preflight / disallowed origin / no `*`, permission-matrix test over every endpoint of §6.2 (§6.5: drivers/vehicles writable by all roles, cost profiles admin only — OQ-001-01), audit events, OpenAPI completeness + schemathesis over CRUD | 16, 17, 18, 19, 27, 30, 32 | 001/4, 001/5, 001/6 | `contracts/openapi.json` | todo |

### FEAT-002 — Demo data generators and import · [spec](specs/FEAT-002-demo-data-generators.md) · planned 11-10

| Slice | Scope | ACs (AC-FEAT-002-…) | Depends | Lock | Status |
|---|---|---|---|---|---|
| 002/1 | `data/mock/cities.json` (39 cities), `fleet-generator v1`, committed `fleet.json` (fuel values per OQ-002-01) | 01, 02, 03, 08 | 001/1 | `data/mock/*.json` | todo |
| 002/2 | `offers-generator v2`: 150 offers, enrichment file with tags, lane rates (OQ-002-03), committed output (body/equipment enumeration values come from the official OpenAPI file, OQ-002-02) | 04, 05, 06, 07 | 002/1, O-4 | `data/mock/*.json` | todo |
| 002/3 | TIMOCOM v3 subset schemas, tolerant `TimocomV3Mapper`, fixtures from the official OpenAPI examples, `SUSPICIOUS_TEXT` flag | 09, 10, 11, 12, 19 | 002/1, O-4 | 🔒 fixtures from an external file | todo |
| 002/4 | `MockFreightProvider` (no network), idempotent import with batches, raw records, synthetic-data checks | 13, 14, 18, 20 | 002/2, 002/3, 001/6 | — | todo |
| 002/5 | First-start seed (`DEMO-DEFAULT` cost profile, fleet, offers, `app_meta.seed_version`), admin `demo-data/generate` and `demo-data/reset`, `make seed-fleet` | 15, 16, 17 | 002/4, 001/5 | `Makefile`, `contracts/openapi.json` | todo |

### FEAT-003 — Optimizer and working time · [spec](specs/FEAT-003-optimizer-and-working-time.md) · planned 11-11

Pure code: no DB, HTTP, environment or system clock. Gates: `make check` + `make test-props`. Changes to invariants, objectives, legal rules or validators need human approval.

| Slice | Scope | ACs (AC-FEAT-003-…) | Depends | Lock | Status |
|---|---|---|---|---|---|
| 003/1 | `compliance`: `DriverRules` port, `pl_domestic_employee_v1` (break split 30 + 15 min, OQ-003-04), `eu561_van_international_v1`, profile choice per plan, weekly counters (Monday 00:00 base zone) | 14, 15, 16, 17, 18 | 001/1 | — | todo |
| 003/2 | Cost model: fuel with `VAN_DEFAULT_V1` speed curve, CO₂, tolls, driver cost, per diems (domestic 45 zł/day, none international), accommodation, vehicle cost | 19, 20 | 001/1 | — | todo |
| 003/3 | Snapshot models, prefilter with ordered rejection codes, rejection report, empty result without exception | 21, 22 | 003/1, 003/2, 002/1 | — | todo |
| 003/4 | `RouteValidator` and `FleetValidator` (separate implementation from the search) | 25 | 003/3 | — | todo |
| 003/5 | Per-driver Branch-and-Bound (horizon, chains, `home_by`, top-K), objectives `profit`/`fastest`/`fuel` with tie-breakers, node budget / `truncated`, brute-force `oracle.py`, property tests P1–P9, P11 | 01, 02, 03, 04, 05, 06, 07, 08, 09, 11, 23, 27 | 003/4 | — | todo |
| 003/6 | Fleet assignment, `fastest`/`fuel` fleet solutions over the `profit` drivers, `baseline_single`, `baseline_greedy`, `fleet_oracle.py`, property tests P10, P12, P13 | 10, 12, 13, 24, 26 | 003/5 | — | todo |
| 003/7 | Golden tests GOLD-001 … GOLD-010 (values are binding; a mismatch = stop and report, never edit the golden file) | 30, 31, 32, 33, 34, 35, 36, 37, 38, 39 | 003/6 | 🔒 golden values | todo |
| 003/8 | Import-linter contract for engine/compliance purity and oracles test-only; `bench/fleet_5x60.py` with p50/p95 report | 28, 29 | 003/6 | — | todo |

### FEAT-004 — Routing and jobs · [spec](specs/FEAT-004-routing-and-jobs.md) · planned 11-11

| Slice | Scope | ACs (AC-FEAT-004-…) | Depends | Lock | Status |
|---|---|---|---|---|---|
| 004/1 | `RoutingProvider` port, repo matrix provider (`matrix_repo_v1`), haversine provider, composite fallback with `ROUTING_FALLBACK`, committed `data/mock/routing-matrix.json` (haversine variant per OQ-004-02), no HTTP without a key | 01, 02, 03, 06, 07, 08 | 002/1 | `data/mock/*.json` | todo |
| 004/2 | `OrsRoutingProvider` (`driving-car`), retry then fallback, `routing_cache` | 04, 05 | 004/1, O-5 | 🔒 recorded ORS fixtures (external calls, no key in files) | todo — waits for O-5 |
| 004/3 | Jobs: `POST /optimization-jobs` (`202`, `Idempotency-Key`), in-process worker (`ProcessPoolExecutor(max_workers=1)`), result storage, heartbeat and restart recovery, sequential runs, per-user job limit | 09, 10, 11, 13, 14, 15 | 003/6, 004/1, 002/5 | `contracts/openapi.json` | todo |
| 004/4 | Results and route plans: `GET …/result`, `GET /route-plans/{id}` with geometry, immutable snapshot and plans | 12, 16, 17 | 004/3 | `contracts/openapi.json` | todo |
| 004/5 | Assignments: `POST`/`DELETE /assignments`, `PLAN_NOT_ASSIGNABLE`, `DriverUsageChecker` implementation for FEAT-001; auth/CSRF/rate-limit test over all endpoints of FEAT-004 §6.1 | 18, 19, 20 | 004/4 | `contracts/openapi.json` | todo |

### FEAT-006 — Runtime agents · [spec](specs/FEAT-006-runtime-agents.md) · planned 11-12

All `agent` tests run on scripted fake models without network (`make test-agents`). The only write tool is `assign_plan`, after `interrupt()` and an `approve` decision.

| Slice | Scope | ACs (AC-FEAT-006-…) | Depends | Lock | Status |
|---|---|---|---|---|---|
| 006/1 | `agents/models.py`: `AGENT_MODEL_POLICY`, `build_chat_model(role)` via `init_chat_model`, provider fallback mechanics, fake-model registration for tests; versioned prompt files and loader; AI-enabled rule and `GET /agent/status` | 21 | 004/5, O-6 | 🔒 `agents/prompts/**`, `.env.example` | todo |
| 006/2 | Tools (13 read tools + `assign_plan` adapter) as thin adapters over services: registry with allowlist and `read`/`write` kind, Pydantic schemas `extra="forbid"`, size limits, facts export, `untrusted_text`, driver and plan aliases | 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36 | 006/1 | — | todo |
| 006/3 | `StateGraph`: Dispatcher + Freight Scout + Fleet & Compliance + Route Planner, allowlist enforcement, `PlanValidator`, `request_approval`, `ApprovalGate` with idempotent `interrupt()`/resume, `assign_plan`, SQLite checkpoints in `agents.db`, data minimisation, prompt-injection containment (run service, no HTTP yet) | 01, 02, 05, 06, 07, 08, 13, 20, 38, 39 | 006/2 | 🔒 `agents/prompts/**` | todo |
| 006/4 | `GroundingGuard` with formatting tolerance, template answers (incl. excluded suspicious offers), provider fallback in nodes, `explain_plan` and `POST /route-plans/{id}/explanations` with template fallback | 09, 10, 14, 18, 25, 37 | 006/3 | `contracts/openapi.json` | todo |
| 006/5 | `BudgetGuard`: recursion limit, tool-call limit, run token budget, run timeout (excluding `waiting_approval`), daily budget accounting per user (lower for `demo`) | 11, 12 | 006/3 | `.env.example` | todo |
| 006/6 | Threads, runs, messages, resume and SSE endpoints (`sse-starlette`, `Last-Event-ID` replay), trace in `agent_steps`, resume authorisation, `503 AI_UNAVAILABLE`, `429 AI_BUDGET_EXCEEDED`, provider swap end to end | 03, 04, 15, 16, 17, 19, 22, 23, 24 | 006/3, 006/4, 006/5 | `contracts/openapi.json` | todo |
| 006/7 | Live evaluation set: ≥ 30 scenarios + ≥ 10 prompt-injection scenarios in `evals/agents/*.yaml` (manual `ai-evals` only, never blocks CI) | 40, 41 | 006/6, 007/3, O-7 | 🔒 paid API budget | todo |

### FEAT-005 — Frontend · [spec](specs/FEAT-005-frontend.md) · planned 11-13

All texts through next-intl in EN and PL; API access only through `lib/api/`. Until a backend contract exists, use MSW handlers typed from `contracts/openapi.json`.

| Slice | Scope | ACs (AC-FEAT-005-…) | Depends | Lock | Status |
|---|---|---|---|---|---|
| 005/1 | Foundations: design system "Clear Route v3" in code (`styles/tokens.css`, Tailwind theme, base components in `components/ui/` on Radix primitives, `VanSide` in `components/vehicle/`, token lint rule — `docs/design/`); generated `schema.d.ts` + `openapi-fetch` client, SSE helper with reconnect and polling fallback, problem+json error helper with translated codes, `lib/format` (money, km, durations, zoned times), i18n key-parity check and no-hard-coded-strings lint rule (verified by AC-18 in 005/9) | 20, 21, 22, 24 | 000/2, 000/4 | `messages/*.json`, `pnpm-lock.yaml` | todo |
| 005/2 | Login with Turnstile (`@marsidev/react-turnstile`), session/CSRF handling, redirects and "no access" page; minimal Playwright harness in `tests/e2e/` for the first e2e AC | 01, 02, 03 | 005/1, 001/3 (or MSW) | `messages/*.json`, `pnpm-lock.yaml` | todo |
| 005/3 | Fleet screen: drivers and vehicles tables with van illustration and working-time bars, create/edit/delete forms for all roles, conflicts, toasts, confirmation dialogs, keyboard accessibility | 04, 05, 06, 07, 08, 19 | 005/2, 001/5 (or MSW) | `messages/*.json` | todo |
| 005/4 | Offers screen: filters in the URL, "SYNTHETIC DATA" badge, provenance and quality flags, manual offer CRUD, read-only provider offers, safe text rendering | 09, 10 | 005/2, 001/6 (or MSW) | `messages/*.json` | todo |
| 005/5 | Plan view: header with van illustration, three variant cards with deltas, CO₂ and estimate labels, legal notice, **top-view load plan with stop selector** (`LoadPlanTopView`), timeline in design-system colours, stop list, occupancy chart, cost breakdown, vehicle card, MapLibre map with list fallback and route progress line | 11, 12, 23, 26 | 005/1, 004/4 (or MSW) | `messages/*.json` | todo |
| 005/6 | Manual optimizer: start a fleet job, poll progress, results with van per driver, baselines chart and rejections, assign with confirmation | 13 | 005/5, 004/5 | `messages/*.json` | todo |
| 005/7 | AI Dispatcher: chat, live trace panel, draft → final answer, proposal cards with van illustration and approval cards (approve/reject with comment), "AI is off" panel, responsive layout | 14, 15, 16, 25 | 005/1, 006/6 (or mocked SSE) | `messages/*.json` | todo |
| 005/8 | Admin: demo-data generate (seed) and reset with a typed confirmation word; cost profiles read-only (OQ-005-05) | 17 | 005/2, 002/5 | `messages/*.json` | todo |
| 005/9 | EN/PL parity across login, fleet and plan screens; design-system conformance (token lint, contrast of token pairs, van illustration in the four places); UX acceptance checklist of FEAT-005 §7, reviewed by a human before the spec is marked `implemented` | 18, 27 (+ checklist) | 005/3 … 005/8, O-10 | `messages/*.json` | todo |

### FEAT-007 — Quality, README, `ci-full` · [spec](specs/FEAT-007-quality-readme-ci-full.md) · planned 11-14

| Slice | Scope | ACs (AC-FEAT-007-…) | Depends | Lock | Status |
|---|---|---|---|---|---|
| 007/1 | Backend integration scenario (generator → import → fleet optimisation → fake agent run → assignment → `409` on driver delete) and the per-package coverage gate | 02, 10 | 004/5, 006/6 | — | todo |
| 007/2 | Playwright E2E (both specs): login, language switch, CRUD with toasts, three variants with CO₂ and notice, assignment, "AI is off", fake-model approve and reject (`APP_ENV=test` only) | 03 | 005/7, 005/6 | `pnpm-lock.yaml` | todo |
| 007/3 | `ci-full.yml` (gates 1–10 incl. 6, 7, 8b; CodeQL default setup; audits and licence check) and `ai-evals.yml` (manual trigger, secrets, budget, report) | 01, 08, 09 | 007/1, 007/2, O-2 | 🔒 `.github/workflows/**` | todo |
| 007/4 | `scripts/clean_clone_check.sh` (≤ 10 min, no keys), `scripts/check_docs.py --readme/--development`, final `README.md` (status table, verified commands, "How I used AI tools", Polish summary) | 04, 05, 06 | 007/3, O-8, O-10 | `README.md` | todo |
| 007/5 | `scripts/benchmark_report.py` → `docs/metrics.md` (fleet profit vs baselines, timings) | 07 | 003/8, 004/3 | — | todo |

### FEAT-009 — Demo media and release · [spec](specs/FEAT-009-demo-media.md) · planned 11-15

| Slice | Scope | ACs (AC-FEAT-009-…) | Depends | Lock | Status |
|---|---|---|---|---|---|
| 009/1 | Recording (`docs/media/demo.mp4` 120–240 s + `demo.gif`, captions only, English UI) following the six-scene script; ten screenshots (PNG, ≤ 1 MB each, one in Polish); `check_docs.py --media`; pre-publication checklist | 01, 02, 03, 05 | 007/4, O-6, O-11 | 🔒 publication of media | todo |
| 009/2 | Embed media in `README.md` §8 with alt texts, update the status table, tag `v0.1.0` on the green `ci-full` commit | 04, 06 | 009/1, O-11 | 🔒 release tag, `README.md` | todo |

---

## 5. P1 — only if time allows

None of these may start without an `approved` specification.

| Item | Spec | ACs | Notes |
|---|---|---|---|
| `interpret_offer_text` (AI enrichment with provenance `ai`, user confirmation) | [FEAT-008](specs/FEAT-008-p1-offer-text-and-road-alternatives.md) (`draft`) | AC-FEAT-008-01 … 03 | new prompt ⇒ `ai-evals`; cut order item 1 |
| Road alternatives (fastest vs avoid motorways) with re-validation | FEAT-008 (`draft`) | AC-FEAT-008-04 … 07 | uses the ORS key of O-5; cut order item 2 |
| Plan risk rating (`risk_level`, `risk_reasons`) | FEAT-008 (`draft`) | AC-FEAT-008-08 | does not change rank or profit |
| Account lockout after failed logins | none yet | — | REQ-005 (P1 part); needs a spec |
| Full admin panel (users, model policy) | none yet | — | cut order item 3 |
| Full EN/PL translation coverage | none yet | — | REQ-021 (P1 part) |
| Night work in the PL profile | none yet | — | Q14 |
| B&B label dominance | none yet | — | engine performance |
| Automated axe checks | none yet | — | NFR-010 (P1 part) |

## 6. P2 and post-MVP (not planned)

- **P2:** 2D pallet solver, split breaks, Sentry/Grafana, plan export.
- **Post-MVP** (each needs a new specification): PostgreSQL + VPS with Docker Compose, event-driven mode (REQ-025), driver messaging (REQ-026), real offer sources (REQ-027), tachograph/telematics (REQ-028), multi-tenant (REQ-029), MCP server (REQ-030), self-hosted routing, OR-Tools, user registration, Communications/Pricing agents, box and refrigerated bodies.

---

## 7. Documentation drift found while writing this file

Reported, not fixed (these files are outside this task):

- `docs/report.md` §37 says the status of all ADRs is **proposed**; `docs/adr/README.md` and every ADR say **accepted (2026-11-11)**. The ADR files are authoritative; §37 is stale.
- `README.md` and `specs/requirements.md` carry status lines dated 2026-11-09 although approvals happened on 2026-11-11. Still correct in substance (nothing is implemented).
- `AGENTS.md` §3 repository map does not list `backlog.md`.

## 8. Changelog

- 2026-11-11 — first version, built from the approved specifications, owner decisions of 2026-11-11 and the day plan of `context.md`.
- 2026-11-11 — O-5 resolved by owner decision: the owner gets an ORS key; 004/2 is no longer blocked and waits for the key and the recorded fixtures.
- 2026-11-11 — ACs moved to the slice where they can first be tested end to end: AC-FEAT-001-27 → 001/7; AC-FEAT-004-20 → 004/5; AC-FEAT-005-18 → 005/9; FEAT-006 ACs regrouped (02, 20 → 006/3; 14, 18 → 006/4; 03, 04, 17, 19, 24 → 006/6). 002/2 now depends on O-4 (enumeration values). Every AC still belongs to exactly one slice.
- 2026-11-11 — UI design approved (`docs/design/`, ADR-0015, FEAT-000 rev. 4, FEAT-005 rev. 4): 000/2 sets up tokens and fonts instead of shadcn/ui; 005/1 builds the design system and `VanSide`; new AC-FEAT-005-26 → 005/5 (top-view load plan), AC-FEAT-005-27 → 005/9 (design conformance); 005/3, 005/6, 005/7 show the van.
