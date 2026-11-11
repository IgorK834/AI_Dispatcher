# RoutePilot AI — Project Context

> **Audience:** every AI coding agent working on RoutePilot AI (and every human in the project).
> **Status:** v3.1, 2026-11-09. Phase: research and design are finished, **implementation has not started**. Every path, command and module is **planned** until it exists in the repository.
> **Document hierarchy:** `context.md` (rules — this file) > `specs/FEAT-*.md` (what to build) > `docs/adr/*` (why) > `docs/report.md` (research and rationale) > `README.md` (overview and run steps) and `DEVELOPMENT.md` (how-to guide).
> `AGENTS.md` and `CLAUDE.md` are entry points for coding agents: they summarise behaviour and point to this file. On project rules this file wins. Do not copy rules into them.
> A contradiction between documents = **stop and report** (see "When to stop work").
> Terms: **coding agents** (development agents — you) ≠ **runtime agents** (LangGraph inside the application). Do not mix them up.
> **Language:** all project documents are in English; `README.md` ends with a short Polish summary.

---

## Product Mission

RoutePilot AI is an **AI dispatcher** for a small fleet of vans up to 3.5 t (curtain-sider body, 8/9/10 euro pallets). It keeps a list of drivers and their vans and, in a conversation with a human dispatcher, it finds freight offers, checks driver availability and working time, builds the most profitable routes with consolidated loads and chains of orders (and brings each driver back to base for the weekend), shows the variants **most profitable / fastest / lowest fuel** and proposes load-to-driver assignments. **A human approves the decision.**

Guiding principle: **agents reason and orchestrate; deterministic code computes and verifies.**

---

## Project Constraints

1. **Deadline:** MVP 2026-11-09 … 2026-11-15 — a small, fully working full-stack application with a transport theme. Afterwards it continues as a portfolio project.
1a. **Local run in a few steps:** no Docker, no database server (SQLite), no required API keys (LLM and ORS are optional, Turnstile uses test keys). This is a hard requirement — any change that breaks it is rejected.
1b. **Full-stack quality over complexity:** clear layers, correct REST with full CRUD, explicit CORS, intuitive UI. Complex features (agents, engine) only in a form that can be understood and explained (plain-language explanations in `docs/report.md` §18.4, §22.9).
2. **Data:** there is no access to TIMOCOM. Offers are **synthetic**, in the format of TIMOCOM Freight Exchange API v3.0.6. Drivers and vehicles come from a **demo data generator** (later managed by the admin). Synthetic data is **never** presented as real.
3. **Driver working time** is a key constraint. The model is a **simplification** of the rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006 for vans in international transport since 2026-07-01). We **never** claim that a plan complies with the law.
4. **AI is not a source of truth** for mass, capacity, working time, feasibility, regulations, costs or prices.
5. **Swappable LLM provider** (the owner uses Google Gemini; Anthropic and OpenAI are supported too) — no code that depends on one provider outside the adapters.
6. **Database and run:** SQLite in the MVP; PostgreSQL and a self-managed VPS (Docker Compose) only in the portfolio version. No Kubernetes, Redis or queue brokers.
7. **Public repository:** `README.md` (English, with a short Polish summary) with a description, technologies, step-by-step run instructions (API and web separately) and a section on the use of AI tools; a `.mp4`/`.gif` recording and screenshots in `docs/media/`; instruction files for coding agents (`context.md`, `AGENTS.md`, `CLAUDE.md`) are committed. No secrets and no personal data in the repo.
8. **No scraping** of freight exchanges and no circumvention of access limits.
9. **Avoid over-engineering:** every new agent, framework or service needs a justification (ADR).
10. **Purpose statement is fixed:** describe the project only as an MVP with a deadline (2026-11-15), later a portfolio project. Do not state why, for whom or in what context it is built, and do not name any third-party organisation in that role — in any file, heading, example or commit message.

---

## Delivery Deadline

| Day | Goal (details: `docs/report.md` §33) |
|---|---|
| 2026-11-09 | specifications FEAT-000…007, 009, golden GOLD-001…010, ADR-0001…0014, `AGENTS.md`/`CLAUDE.md`, `DEVELOPMENT.md` (approved by a human) |
| 2026-11-10 | FEAT-000 monorepo + `ci-fast` + `AGENTS.md`/`CLAUDE.md` kept in sync; FEAT-001 domain + SQLite + **CRUD** + CORS + auth (Turnstile test keys); FEAT-002 fleet and offer generators + seed on start |
| 2026-11-11 | FEAT-003 engine (DriverRules, costs, CO₂, B&B, fleet assignment, 3 objectives, validators); FEAT-004 routing (matrix in the repo, ORS optional) + in-process jobs |
| 2026-11-12 | FEAT-006 LangGraph agents (Dispatcher + 3 specialists, guards, `interrupt`, SQLite checkpoints, SSE, model policy) |
| 2026-11-13 | FEAT-005 frontend (login, AI Dispatcher, fleet and offers with CRUD, plan with variants and CO₂, admin, EN/PL) |
| 2026-11-14 | FEAT-007 `ci-full` + E2E + UX polish + metric measurements + `README.md` + clean-clone run test |
| 2026-11-15 | FEAT-009 `.mp4`/`.gif` recording and screenshots in the repo, tag `v0.1.0` |

**Cut order:** (1) AI interpretation of offer descriptions, (2) road choice (ORS alternatives), (3) full admin panel (the generator stays), (4) full translations, (5) Freight Scout merged into the Dispatcher, (6) ORS → only the repo matrix / haversine, (7) `ci-full` → E2E smoke.
**Never cut:** engine + validators + property tests, `DriverRules`, CRUD + CORS, easy local run, `interrupt` before a write, `GroundingGuard`, login with captcha, `ci-fast`, the path without AI (manual optimizer), `README.md` with instructions, the recording.

---

## MVP Boundaries

**P0:** monorepo + CI + `AGENTS.md`/`CLAUDE.md`; **SQLite** (SQLAlchemy + Alembic); **REST API with full CRUD** (drivers, vehicles, cost profiles, manual offers) and **explicit CORS** (`localhost:3000` → `localhost:8000`); **auth** (email + password, Argon2id, Cloudflare Turnstile — test keys locally, roles `admin`/`dispatcher`/`demo`, cookie sessions, CSRF token, rate limit, demo account on first start); **fleet generator** (5 drivers, vans 8/9/10 EP, working-time states) and **offer generator** + import through the TIMOCOM v3 mapper + **seed on first start**; engine (DriverRules PL + 561, costs, **CO₂**, B&B per driver, fleet assignment, objectives `profit`/`fastest`/`fuel`, baselines, validators); routing: city matrix in the repo + ORS optional + fallback; jobs inside the API process; **LangGraph agents** (Dispatcher, Freight Scout, Fleet & Compliance, Route Planner; nodes PlanValidator, GroundingGuard, BudgetGuard, ApprovalGate; SQLite checkpoints; SSE; model policy per role; LLM key optional); `explain_plan` with grounding and fallback; UI: login, AI Dispatcher (chat + map + trace + approval cards), fleet and offers with CRUD forms, plan with 3 variants and CO₂, manual optimizer, admin (generator), EN/PL for key screens; `README.md` with the required sections; recording and screenshots in the repo.

**P1:** road choice (ORS: fastest vs avoiding motorways, alternatives) with re-validation; `interpret_offer_text`; risk rating; full admin panel (users, model policy); full translations; account lockout after failed logins; night work in the PL profile; B&B label dominance; axe.

**P2:** 2D pallet solver; split breaks; Sentry/Grafana; plan export.

**Outside the MVP (do not implement without a new specification):** PostgreSQL and VPS deployment (Docker Compose, Caddy, backup, deploy from CI), event-driven mode, driver messaging (Telegram/SMS/WhatsApp — described in `docs/report.md` §15.5, §35), real TIMOCOM and other exchanges, self-hosted routing, tachograph/telematics, OR-Tools, MCP server, multi-tenant, user registration, Communications/Pricing agents, box bodies with LIFO, refrigerated bodies.

---

## Domain Glossary

| Term | Meaning |
|---|---|
| **Van / vehicle** | vehicle ≤ 3.5 t gross vehicle weight, TIMOCOM type `VEHICLE_UP_TO_3_5_T`, curtain-sider body (`CURTAIN_SIDER`), 8/9/10 pallet places |
| **EP (pallet place)** | a place for a euro pallet 1200×800; van capacity = `pallet_places` (declared) |
| **EUR equivalent** | occupancy in EP places: EUR = 1.0; half pallet 800×600 = 0.5; industrial 1200×1000 = 1.5 (conservative); unknown = 1.0 + flag |
| **Mixed layout** | pallet arrangement in an 8/10 EP van: one transverse column + one longitudinal column (not "one behind another") |
| **Payload** | `payload_kg`; in vans it is often the binding constraint |
| **Driver** | a company employee (employment contract), home base, assigned van (1:1 in the demo) |
| **DriverState** | current position, `available_from`, work/driving counters (day, since break, week, previous week), end of the last daily/weekly rest, `home_by` |
| **Legal profile** | `pl_domestic_employee_v1` (Act on Drivers' Working Time) or `eu561_van_international_v1` (561/2006 + working time) |
| **Working time** | driving + loading/unloading + other duties + waiting (conservative) |
| **`home_by`** | the latest return of the driver to base (default Friday 18:00 local time of the base) |
| **Offer / Stop / Window** | as in TIMOCOM: an offer with ≥ 2 points; window = the interval in which service may start |
| **Plan (RoutePlan)** | a feasible sequence of actions of one driver (consolidated loads + chain of orders + drive to base) with a schedule and costs; `variant ∈ {profit, fastest, fuel}` |
| **Fleet solution (FleetSolution)** | at most one plan per driver, no shared offers, for a given objective |
| **Baseline** | `baseline_single` (best single offer per driver), `baseline_greedy` (greedy assignment) |
| **Assignment** | a plan for a driver approved by a human — the only write action available to runtime agents |
| **Runtime agent** | a LangGraph graph node with an LLM: Dispatcher, Freight Scout, Fleet & Compliance, Route Planner |
| **Tool** | a deterministic function exposed to a runtime agent; `read` or `write` |
| **Guard** | a deterministic node in the graph: PlanValidator, GroundingGuard, BudgetGuard, ApprovalGate |
| **Interrupt / resume** | pausing the graph until a human decides (`interrupt()`), resuming with `Command(resume=…)` |
| **Run / Step / Thread** | one execution of the graph / a step (LLM, tool, guard) / a conversation |
| **Grounding** | every number and ID in an AI answer occurs in the tool results of that run |
| **Carbon footprint (CO₂)** | estimated kg CO₂ of a plan: litres of diesel × emission factor |
| **Provenance** | `source`, `derived`, `inferred`, `default`, `generated_mock`, `ai`, `user`, `assumption` |

---

## Core Domain Rules

1. **Units:** kg (int), m (Decimal 2), km (Decimal 2), min (int), money as **int in minor units** + ISO-4217. `float` is forbidden for money.
2. **Time:** UTC (`timestamptz` / aware `datetime`); the IANA zone of a stop is stored separately; `datetime.now()` is forbidden in domain logic (an injected `Clock`).
3. **Missing data:** `None` + `missing_fields`; inventing values is forbidden; substitutes only with provenance and a flag.
4. **Van capacity:** on every leg Σ kg ≤ `payload_kg` **and** Σ EUR equivalents ≤ `pallet_places`; load dimensions ≤ interior (if known). Pallets: `source`/`user`/`generated_mock` → use them; missing → `ceil(length_m × 2.4)` + flag; AI → `max(derived, ai)` + flag; nothing → rejection `MISSING_CAPACITY_DATA`. Access order (LIFO) is **not modelled** for curtain-siders (flag `LOADING_ORDER_NOT_MODELLED`).
5. **Offer without a price** → rejection `MISSING_REVENUE`; **without coordinates** and not geocodable from `cities.json` → `MISSING_COORDINATES`.
6. **Legal profile of a plan:** any international operation / cabotage in the plan ⇒ `eu561_van_international_v1` for the whole plan; otherwise `pl_domestic_employee_v1`.
7. **`pl_domestic_employee_v1`** (Act on Drivers' Working Time, Dz.U. 2024 poz. 220): daily work ≤ 12 h (parameter, equivalent working-time system; 8 h in the basic system); a 30-minute break after 6 h of work, plus a 15-minute top-up when daily work reaches 9 h and more work follows (the planning model accepted in FEAT-003 FR-5 / OQ-003-04); daily rest ≥ 11 h in every 24-hour period; weekly work ≤ 60 h; weekly rest ≥ 35 h; no driving-time limits (the work limits constrain driving).
8. **`eu561_van_international_v1`**: a 45-minute break before exceeding 4 h 30 min of driving; daily driving ≤ 9 h (no extensions); daily rest 11 h, ≤ 13 h after the end of the previous rest; weekly driving ≤ 56 h and two-week driving ≤ 90 h (from `DriverState`); **plus** a break after 6 h of work and weekly work ≤ 60 h; daily rest in the vehicle only when `sleeper_cab = true` (otherwise an accommodation cost); weekly rest at base.
9. Service (loading/unloading) and waiting = **work**, not a break.
10. **Return for the weekend:** if `home_by` lies within the horizon, the plan ends at base before `home_by` (hard).
11. **Net profit** = revenue − fuel − tolls − driver cost − per diems − accommodation − vehicle cost (formulas: `docs/report.md` §19.1). Revenue only for delivered offers. The drive to base is a real cost.
12. **Fuel and CO₂:** `L100 = (c_empty + (c_full − c_empty) × kg/payload) × speed_curve(v)`; `co2_kg = fuel_l × CO2_FACTOR_KG_PER_L` (default 2.6 — an approximation, `docs/report.md` §17.4); the parameters are **assumptions** from `CostProfile`/vehicle, labelled as an estimate in the UI.
13. **Objectives (lexicographic, no weights):** `profit`: max profit → min completion time → min fuel; `fastest`: min completion time → max profit; `fuel`: min litres → max profit. All subject to `profit ≥ min_profit` and margin ≥ `min_margin_pct`.
14. **Fleet:** every offer with at most one driver; every driver has at most one plan.
15. **Mandatory notice** next to every schedule: "The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance." (The Polish wording for the PL locale is in the Polish summary of `README.md`.)
16. **Synthetic data** (`is_synthetic=true`, `MOCK-*`, fictional people/companies/phone numbers) carries a "SYNTHETIC DATA" badge in the UI (translated in the PL locale); no TIMOCOM branding.
17. **Demo cost parameters** come from `docs/report.md` §17.4; values marked there as "assumption" must have provenance `assumption` in the code.

---

## Selected Technology Stack

| Layer | Choice (ADR) |
|---|---|
| Web | Next.js 16 (App Router), React 19, TypeScript strict (a version supported by Next.js/ESLint), Tailwind themed from `docs/design/tokens.json` + Radix UI primitives + own components, no shadcn/ui (ADR-0015, design system `docs/design/`), TanStack Query v5, react-hook-form + Zod, MapLibre + react-map-gl, **next-intl (EN/PL)**, `EventSource` (SSE) |
| API client | `openapi-typescript` + `openapi-fetch` (generated types — do not edit) |
| Backend | Python 3.13, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2 + Alembic, psycopg 3 (post-MVP, with PostgreSQL — ADR-0002), structlog (ADR-0001) |
| Database | **SQLite** (WAL) through SQLAlchemy 2 + Alembic; tests on in-memory SQLite; PostgreSQL 17 — portfolio version (ADR-0002) |
| Jobs | worker inside the API process (`asyncio` + `ProcessPoolExecutor(max_workers=1)`), state in a jobs table (ADR-0008) |
| Runtime agents | **LangGraph 1.2.x** + `langgraph-checkpoint-sqlite`; `langchain-core` + `init_chat_model`; adapters `langchain-google-genai`, `langchain-anthropic`, `langchain-openai`; SSE through `sse-starlette` (ADR-0006, 0013). **Not used:** `langgraph-supervisor`, LiteLLM, CrewAI, Agent SDK |
| Engine | custom B&B + fleet assignment (ADR-0004); OR-Tools **not** in the MVP |
| Routing | OpenRouteService (`driving-car`) + cache + `HaversineRoutingProvider` (ADR-0005) |
| Auth | Argon2id (argon2-cffi), server-side sessions in a cookie, Cloudflare Turnstile, slowapi (ADR-0012) |
| Tests | pytest, Hypothesis, schemathesis, pytest-cov; Vitest + Testing Library + MSW; Playwright |
| Quality | ruff, mypy --strict, import-linter; ESLint, Prettier, `tsc --noEmit`; gitleaks; pip-audit/pnpm audit; CodeQL/Semgrep |
| Tooling | uv, pnpm workspaces, Makefile (optional shortcut — the README gives the direct commands), pre-commit, GitHub Actions |
| Run | locally: API `uvicorn` on `:8000`, web `pnpm dev` on `:3000`; no Docker (ADR-0007). VPS + Docker Compose — post-MVP |

**Dependency rules:** a new runtime dependency = a justification in the task report (problem, alternatives, licence). Forbidden: GPL/AGPL at runtime, Redis/Celery/RabbitMQ, additional agent frameworks, TypeScript ORMs. **Do not add a package whose existence and version you have not verified in the registry.**

---

## Architecture Principles

1. A modular monolith with automatically enforced boundaries; an architecture change = ADR + human approval.
2. Ports & Adapters: `FreightProvider`, `OfferMapper`, `RoutingProvider`, `DriverRules`, `CaptchaVerifier`, chat models (LangChain), `Clock`, (post-MVP) `MessagingProvider`.
3. **Pure core:** `optimization.engine` and the rules in `compliance` have no IO (no DB, HTTP, env, system clock); they receive ready data (for example a travel matrix).
4. **Runtime agents sit above services:** agent tools are thin adapters over the same services as the HTTP API; zero business logic in the agent layer.
5. Contract-first: OpenAPI is generated to `contracts/openapi.json`, committed, with drift + oasdiff checks in CI.
6. Engine determinism: sorting by `id`, explicit seeds, a node budget.
7. Verifiability: `RouteValidator` + `FleetValidator` for every result; `GroundingGuard` for AI answers; `interrupt` for writes.
8. Explicit uncertainty: provenance, quality flags, warnings (`ROUTING_FALLBACK`, `LOADING_ORDER_NOT_MODELLED`, `SERVICE_TIME_DEFAULTED`, …).
9. The application works without AI (manual optimizer, template explanations).
10. The smallest necessary change; refactoring outside the scope is a separate task.

---

## Module Boundaries

### Backend (`apps/api/src/routepilot/`)
| Module | Responsibility | May import | **Must not** import |
|---|---|---|---|
| `shared` | money, units, ids, clock, errors, i18n of codes | stdlib, pydantic | the other modules |
| `identity` | users, sessions, passwords, Turnstile, roles, rate limit | `shared` | the domains (`fleet`, `freight`, `optimization`, `agents`) |
| `fleet` | CRUD for drivers and vehicles, DriverState, cost profiles, fleet generator | `shared` | `optimization.jobs`, `agents`, `integrations` |
| `freight` | offers: import from a provider (read-only) + CRUD for manual offers (`source=manual`), normalisation | `shared` | `integrations`, `optimization`, `agents` |
| `routing` | `RoutingProvider`, ORS, cache, haversine, fuel model | `shared` | `optimization.jobs`, `agents` |
| `compliance` | `DriverRules` + profiles (pure) | `shared` | anything with IO |
| `optimization.engine` | prefilter, costs, B&B, fleet assignment, objectives, validators, baselines | `shared`, `compliance` (rules) | DB, FastAPI, httpx, `os.environ`, `agents`, `routing` adapters (it receives a matrix) |
| `optimization.jobs` | jobs, worker, results, assignments | `shared`, `fleet`, `freight`, `routing`, `compliance`, `optimization.engine` | `agents`, `integrations` |
| `agents` | graph, state, nodes, tools (adapters over services), guards, prompts, model policy, trace | `shared`, the public services of `fleet`/`freight`/`optimization.jobs`/`routing` through tool ports | repositories/DB directly, `optimization.engine` internals, `identity` internals |
| `integrations.*` | mock, timocom | `shared`, `freight` (target model) | `optimization`, `agents` |
| `main.py` | composition (DI), routers, CORS, lifespan (migration check, seed on first start, start of the in-process worker) | everything | — |
Test-only: `optimization/engine/oracle.py`, `fleet_oracle.py` — importing them outside `tests/` is forbidden.

### Frontend (`apps/web/src/`)
`app/*` holds thin pages; logic lives in `features/{agent-chat,fleet,offers,plans,optimizer,admin,auth}`; `features/x` imports from `features/y` only through `index.ts`; API access only through `lib/api/client.ts`; SSE through `lib/api/sse.ts`; UI texts only through next-intl (`messages/en.json`, `messages/pl.json`) — hard-coded texts in components are forbidden.

### Shared files (one author of changes at a time)
`contracts/openapi.json`, `apps/api/migrations/**`, `context.md`, `specs/requirements.md`, lockfiles, `.github/workflows/**`, `Makefile`, `.env.example`, `apps/api/src/routepilot/agents/prompts/**`, `apps/web/messages/*.json` (key conflicts — append, do not reorder).

---

## Data Model

MVP tables in **SQLite** (columns: `docs/report.md` §14): `users`, `sessions`, `drivers`, `driver_states`, `vehicles`, `cost_profiles`, `import_batches`, `raw_freight_records`, `freight_offers`, `freight_stops`, `optimization_jobs`, `route_plans`, `route_stops`, `assignments`, `agent_threads`, `agent_runs`, `agent_steps`, `approval_requests`, `route_explanations`, `routing_cache`, `audit_events`, `app_meta` + the LangGraph checkpoint tables in a separate file `agents.db` (created by `SqliteSaver.setup()` on start).

Rules: UUID primary keys as `TEXT`; times through `UtcDateTime` (UTC, aware); money as `INTEGER` minor units + currency `TEXT(3)`; lengths in mm, distances in m, masses in kg (`INTEGER`); coordinates `REAL`; structures and lists in `JSON` columns; PRAGMA `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`; **no dialect-specific functions** in models and queries (portability to PostgreSQL); `version` on editable entities; optimisation results are immutable (snapshot in `optimization_jobs.request`); `driver_states` are versioned; logins, configuration changes, CRUD, data generation and assignments → `audit_events`; migrations only through Alembic (`render_as_batch=True`), with `downgrade`, no editing of merged migrations, with human review; the database file stays outside the repo (`.gitignore`).

---

## External Integration Contracts

```python
class FreightProvider(Protocol):           # integrations/ports.py
    name: str
    def capabilities(self) -> ProviderCapabilities: ...
    def search(self, query: FreightSearchQuery) -> Iterator[RawOfferRecord]: ...
    def lookup(self, source_offer_ids: list[str]) -> list[RawOfferRecord]: ...

class OfferMapper(Protocol):
    source: str
    def to_domain(self, record: RawOfferRecord) -> NormalizedOffer | MappingFailure: ...

class RoutingProvider(Protocol):           # routing/ports.py
    provider_id: str                        # "ors_driving_car_v1" | "haversine_v1"
    def matrix(self, points: Sequence[GeoPoint]) -> TravelMatrix: ...
    def route(self, waypoints: Sequence[GeoPoint], *, variant: RouteVariant) -> RouteResult: ...

class DriverRules(Protocol):               # compliance/ports.py (pure implementations)
    profile_id: str
    def advance_drive(self, s: DriverState, minutes: int) -> Outcome: ...
    def advance_work(self, s: DriverState, minutes: int) -> Outcome: ...
    def advance_wait(self, s: DriverState, minutes: int) -> Outcome: ...
    def remaining(self, s: DriverState) -> Remaining: ...

class CaptchaVerifier(Protocol):           # identity/ports.py
    def verify(self, token: str, remote_ip: str | None) -> CaptchaResult: ...
```
- LLM: only through `agents/models.py` (`build_chat_model(role)` from `AGENT_MODEL_POLICY` → `init_chat_model("<provider>:<model>", …)`). Importing provider SDKs outside this file is forbidden.
- ORS: the key `ORS_API_KEY` stays on the server side; every response is cached (`routing_cache`, key = hash of provider, profile, options, points); the demo city matrix is committed in `data/mock/routing-matrix.json`; tests never call ORS (fixtures).
- Turnstile: `TURNSTILE_SITE_KEY` (public), `TURNSTILE_SECRET_KEY` (server); verification before the password check. Locally and in CI the default is Cloudflare's official test keys (`1x00000000000000000000AA` / `1x0000000000000000000000000000000AA` — always pass; `2x…` — always fail, for negative tests). `APP_ENV=production` with test keys = startup error.
- CORS: `CORS_ALLOWED_ORIGINS` (default `http://localhost:3000`), `allow_credentials=True`, `*` is forbidden; the frontend calls the API directly with `credentials: 'include'` and the `X-CSRF-Token` header for state-changing methods.
- REST: plural resources, `POST` → `201` + `Location`, `PATCH` partial change, `DELETE` → `204`, `409` for conflicts (version, read-only provider offer), `422` validation, problem+json with `code`.

---

## TIMOCOM Adapter Rules

Facts (official portal + OpenAPI v3.0.6, 2026-11-09): Live `https://api.timocom.com/freight-exchange/3`, Sandbox `https://sandbox.timocom.com/freight-exchange/3`; `POST /freight-offers/search` (`offerSearchFilter` → `{meta: {requestId, responseTimestamp}, payload: freightOffer[]}`); Basic Auth (other TIMOCOM APIs: OAuth2); `firstResult`/`maxResults ≤ 30`; `inclusiveRightUpperBoundDateTime` is required (≤ 8 h in the past); an identical search **no more often than every 45 s**; search returns no contact persons (separate lookup); generic searches only with consent; Business Approval; not in the model: pallets, temperature, service time; `price` and `geoCoordinate` are optional; `startTime`/`endTime` have no time zone; `vehicleType` contains `VEHICLE_UP_TO_3_5_T`.

Rules:
1. Do not attribute to TIMOCOM any field outside OpenAPI 3.0.6 — everything else is enrichment with provenance.
2. `integrations/timocom/schemas.py` = a subset of the OpenAPI with a version comment.
3. Tolerant mapper: `startTime` as `HH:MM` and `HH:MM:SSZ`; `distance_km` > 200; the key `"creationDateTime "`.
4. Fixtures from the OpenAPI examples in `apps/api/tests/fixtures/timocom/` with a source annotation.
5. No "download everything" mode; targeted searches (area + `size_km`, `vehicleProperties.type=["VEHICLE_UP_TO_3_5_T"]`, `weightRange_t` ≤ payload).
6. `RepeatIntervalLimiter` ≥ 45 s; a page limit; runtime agents cannot bypass the limiter.
7. Log `meta.requestId`; do not log secrets or personal data.
8. Do not persist lookup results; raw search records carry `retention_until`.
9. Do not send real TIMOCOM data to an LLM without consent (Q4).
10. The mock uses the same mapper (`source="mock_timocom_v3"`, `is_synthetic=true`).
11. Zero network calls to TIMOCOM in CI.

---

## AI Architecture Rules (runtime agents)

1. **Graph:** LangGraph `StateGraph`, a custom supervisor (Dispatcher) + specialists: **Freight Scout**, **Fleet & Compliance**, **Route Planner**; deterministic nodes: `PlanValidator`, `GroundingGuard`, `BudgetGuard`, `ApprovalGate`. A new agent = ADR + specification + evaluation.
2. **Tool allowlist per agent** (`docs/report.md` §22.2). An agent cannot call a tool outside its list — an attempt = an error recorded in the trace.
3. **The only write tool in the MVP: `assign_plan`**, executed only after `interrupt()` and a `resume` with the decision `approve` from a user with the role `dispatcher`/`admin`. Every new `write` tool requires `interrupt` — without it the PR is rejected.
4. Node code before `interrupt()` must be **idempotent** (the node restarts after resume); do not wrap `interrupt()` in a bare `try/except`; the order of interrupts is fixed.
5. **Tools:** Pydantic input/output schemas (`extra="forbid"`), `read`/`write` classification, an output size limit, the result = facts for `GroundingGuard`; zero business logic (an adapter over a service).
6. **Offer texts are untrusted:** in tool results only in the field `untrusted_text`; never in system prompts; specialist prompts say explicitly that this is data, not instructions; mark suspicious offers (`SUSPICIOUS_TEXT`).
7. **GroundingGuard:** every number/ID in the final answer must occur in the tool facts of that run (formatting tolerance); a violation → a template answer built from tool data.
8. **Budgets:** `recursion_limit` (default 25), `max_tool_calls` per agent (default 6), `AGENT_RUN_TOKEN_BUDGET`, run timeout 120 s, daily budgets per user (lower for `demo`).
9. **Models:** only through `AGENT_MODEL_POLICY` (role → `provider:model`, parameters); do not hard-code a model or provider; fall back to a second configured model on provider errors; no model → a message + a link to the manual optimizer.
10. **Data minimisation:** the LLM receives driver IDs (`D1…`), positions, counters, offers without contact data; no phone numbers, emails or company names (pseudonyms).
11. **Prompts** in `agents/prompts/<agent>.v<N>.md`; a content change = a new version + an `ai-evals` run before merge; the version is stored in `agent_runs.model_policy`.
12. **Trace:** every step (LLM/tool/guard/interrupt) is stored in `agent_steps` (input/output summaries, tokens, time, status); in `demo/production` no full data contents in logs.
13. **Tests in CI** run only on fake models (no network). Live runs only in `ai-evals` with a budget.
14. Runtime agents **do not** change engine results; every "correction" of a plan must go through the engine and the validator again.

---

## Optimization Engine Invariants

Checked by `RouteValidator`/`FleetValidator` at runtime and by property tests:
1. Load (EUR equivalents, kg) after every action ∈ [0, capacity].
2. Every offer of a plan: one `PICKUP` and one `DELIVERY`, `PICKUP` before `DELIVERY`.
3. No actions for offers outside the plan; revenue = Σ revenues of the plan's offers.
4. Service start at a stop ∈ time window.
5. Time is monotonic; arrival = departure + driving + inserted breaks/rests.
6. Driver state conforms to the plan's legal profile (Core Domain Rules 6–9).
7. Profit = revenue − Σ costs (reconstruction, accuracy 1 minor unit).
8. Determinism (except `runtimeMs`).
9. No feasible plans → an empty list + a rejection report.
10. Top-K: distinct offer sets, sorted by the objective and tie-breakers.
11. B&B = brute-force oracle (N ≤ 5, K ≤ 3).
12. Fleet: an offer at most once; a driver at most one plan.
13. `home_by` within the horizon ⇒ the plan ends at base before `home_by`.
14. An international leg ⇒ validation with the profile `eu561_van_international_v1`.
15. Fleet profit of the `profit` variant ≥ profit of both baselines (when `truncated=false`).
16. `fastest.finish_at` ≤ `profit.finish_at`; `fuel.litres` ≤ `profit.litres` (for the same drivers).
17. `co2_kg` of a plan = `fuel_l` × the configured factor (reconstruction from the breakdown).

Weakening the validators so that results pass is **forbidden**. Validators and search are separate implementations (shared: data models, `CostModel`, `DriverRules`).

Default parameters (configurable, not facts): `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`, `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`, `wall_clock_safety_s=30`.

---

## Specification-Driven Workflow

Flow: `REQ` → (research) → **FEAT spec** (`draft`) → ADR (if a decision is needed) → contracts → **AC** with IDs → test plan → **human approval** (`approved`) → implementation in a worktree → CI gates → review → merge → `implemented` + traceability.

### Before implementing a feature
1. Read `context.md` in full.
2. Identify the FEAT specification with the status `approved` (otherwise **stop**).
3. Verify the contracts (API, data, ports, agent tools) in the specification and in `contracts/openapi.json`.
4. Check that the modules you will touch are in the brief's "Allowed paths".
5. Write/update the tests for the ACs in scope (with AC markers).
6. Implement the smallest change that satisfies the ACs.
7. Run `make check` (+ `make test-props` for engine/compliance, `make test-agents` for agents, `make test-db` for the DB, `make openapi` when a contract changes).
8. File a Completion Report (results, assumptions, unverified items, risks).

### When to stop work (STOP)
- No `approved` specification, or ambiguous ACs.
- A contradiction between `context.md`, a specification and an ADR.
- A need to change a contract, migration, prompt, agent policy or a module outside the brief that the specification did not foresee.
- An invariant cannot be satisfied; a legal rule is unclear.
- A new dependency, service, runtime agent or `write` tool is needed.
- A test is "fixable" only by weakening an assertion, deleting it or silencing it.
- Secrets, real data or paid APIs outside the brief are needed.
Report it with a Completion Report `blocked`, with a description and a proposal (without implementing it).

---

## Specification Templates

### FEAT (`specs/_template.md`)
```markdown
---
id: FEAT-XXX
title: <title>
status: draft | approved | implemented | deprecated
owner: <human>
requirements: [REQ-xxx, NFR-xxx]
adrs: [ADR-nnnn]
modules: [...]
revision: 1
---
## 1. Goal
## 2. Business context
## 3. Scope / Out of scope
## 4. Functional requirements
## 5. Non-functional requirements (with a measure)
## 6. Contracts (API, data/migrations, ports, agent tools)
## 7. Acceptance criteria
- **AC-FEAT-XXX-01** [unit|property|golden|contract|db|integration|agent|e2e|eval] Given … When … Then …
## 8. Edge cases
## 9. Dependencies
## 10. Test plan (AC → test, fixtures, golden, eval scenarios)
## 11. Open questions
## 12. Changelog
```

### Agent Tool Spec (a section in a FEAT for every runtime agent tool)
```markdown
### Tool: <name>
- Agent(s): <allowlist>
- Kind: read | write (write ⇒ interrupt required)
- Input schema: <Pydantic model / fields>
- Output schema: <model>, max size: <N items>
- Backing service: <module.service.method>
- Facts exported for grounding: <fields>
- Untrusted fields: <fields with external content>
- Errors: <codes> → agent behaviour
- Tests: AC-…
```

### ADR (`docs/adr/ADR-nnnn-title.md`)
```markdown
# ADR-nnnn: <title>
- Status: proposed | accepted | superseded by ADR-mmmm | deprecated
- Date: YYYY-MM-DD
## Context
## Decision
## Alternatives
## Consequences
```
ADRs: 0001 backend, 0002 database (SQLite → PostgreSQL), 0003 TIMOCOM, 0004 engine, 0005 routing (ORS), 0006 AI orchestration (LangGraph), 0007 local run / deployment, 0008 async (in-process worker), 0009 API, CRUD, CORS and contracts, 0010 units, 0011 driver working time, 0012 authentication, 0013 LLM providers, 0014 van capacity (content: `docs/report.md` §37), 0015 frontend UI and design system (index: `docs/adr/README.md`).

### Task Brief
```markdown
## Task: <FEAT-xxx / slice n — title>
- Spec: specs/FEAT-xxx-*.md (approved, revision N)
- ACs in scope: …
- Allowed paths: … / Forbidden paths: …
- Shared files touched (owner lock): none | …
- Depends on: …
- Required gates: make check [+ test-props | test-agents | test-db | e2e]
- Done when: … / Stop and ask if: …
```

### Completion Report
```markdown
## Report: <FEAT-xxx / slice n>
- Status: done | partial | blocked
- Changes: <file/module — 1 line>
- ACs covered: AC-… → <test>
- Gates run: lint / types / unit / props / agents / db / build (results)
- Assumptions / Unverified / Spec changes proposed / Dependencies added / Risks
```

---

## Development Agent Responsibilities

| Role | Does | Does not |
|---|---|---|
| **Human (owner)** | approves specifications, ADRs, migrations, breaking changes, prompts and agent policy, changes to `context.md`, releases, merges | — |
| **Architect & Spec Agent** | specifications, ACs, golden cases, ADRs (`proposed`), Agent Tool Specs, consistency of documents and boundaries | production code; changing a status to `approved` |
| **Implementation Agent** (instances: backend/engine, agents, frontend, infra) | one task from a brief in its own worktree, tests, contract regeneration | leaving the Allowed paths, changing a specification (proposal only), merging |
| **Review & QA Agent** | review against the specification and `context.md`, tests for ACs, gaps, security (secrets, PII, injection, `write` tools without `interrupt`), traceability | rewriting the implementation |

---

## Agent Collaboration Protocol

1. No approved specification — no implementation.
2. No specification update — no change to a contract, migration, agent tool or prompt.
3. Do not modify modules outside the Allowed paths without a justification and consent.
4. Do not delete, disable or weaken tests; `xfail` only with a reference to a reported bug and human consent.
5. Do not bypass gates: `--no-verify`, `# type: ignore`/`# noqa` without a code and a comment, `eslint-disable` without a justification, `@ts-ignore`, lowering thresholds and loosening linter configuration are forbidden.
6. Do not hide errors: no empty `except`/`catch`, errors are mapped to domain errors with logging; fix compilation errors, do not silence them.
7. Small PRs (≤ ~400 lines of manual changes); one PR = one task.
8. Every implementation comes with tests that cover the ACs.
9. Report assumptions and unverified items.
10. Architecture conflicts → Architect Agent → human decision (ADR).
11. High-risk changes → human approval.
12. Isolation: a separate worktree and branch `feat/FEAT-xxx-description` (`fix/…`, `chore/…`); in parallel only tasks with disjoint files.
13. Rebase before a PR; conflicts in shared files are resolved by their owner.
14. **Mock vs production data:** synthetic data only from the generators (`data/mock/`), always `is_synthetic=true`; never treat it as real TIMOCOM offers or real drivers.
15. Conventional Commits with a reference to `FEAT-xxx`/`AC-…`.

### Operations that need human confirmation
`git push --force`, rewriting the history of `main`, deleting other people's branches; deleting files outside the Allowed paths; operations on a database other than the local/test one; any action on remote servers, in Cloudflare, ORS or LLM provider consoles; adding/rotating secrets; changes in `.github/workflows/**`; calls to paid APIs outside `ai-evals` with an agreed budget; publishing anything externally (deploy, release, issues/comments in other repositories, recordings).

---

## Coding Standards

**Python:** 3.13, full typing, `mypy --strict`, `ruff` (E, F, I, B, UP, S, PGH, RUF, ASYNC); Pydantic at the boundaries; SQLAlchemy `Mapped[...]`; pure logic, IO at the edges; `Money` (int minor), `Decimal` for distances; `DomainError(code)` → problem+json; `structlog` JSON; no `print` and no mutable global state; snake_case in code/DB, camelCase in the JSON API.
**Agents (Python):** nodes as functions that take/return typed state; tools in `agents/tools/<area>.py` with a decorator that registers the allowlist and the kind `read/write`; prompts only from versioned files; zero provider SDK calls outside `agents/models.py`; every function with `interrupt()` is idempotent before the interrupt point.
**TypeScript:** `strict`, `noUncheckedIndexedAccess`; ESLint (next, @typescript-eslint, jsx-a11y), Prettier; Server Components by default, `"use client"` when needed; types from `schema.d.ts`; formatting through `lib/format/*` with the locale from next-intl; no `any`/`@ts-ignore`; all texts through next-intl (EN + PL); colours, fonts, radii and shadows only through the design tokens of `docs/design/tokens.json` (red is the only accent colour; no raw colour values in components).
**General:** identifiers and code comments in English; project documentation (`context.md`, `docs/report.md`, `DEVELOPMENT.md`, specs, ADRs) in English; README in English with a short Polish summary at the end; model assumptions as named constants/configuration with the comment "assumption".

---

## Testing Standards

| Kind | Where | Rules |
|---|---|---|
| Unit | `apps/api/tests/unit`, `apps/web/src/**/*.test.ts(x)` | fast, no IO, factories, injected `Clock` |
| Property | `apps/api/tests/props` | Hypothesis (profiles `dev` 50 / `ci` 100 / `nightly` 1000); engine and fleet oracles; `compliance` rules |
| Golden | `apps/api/tests/golden` + `specs/golden/GOLD-*.md` | values from manual calculations in the specification; a change = a specification change + human approval |
| Contract | `apps/api/tests/contract` | TIMOCOM fixtures (OpenAPI 3.0.6), ORS (recorded), schemathesis, problem+json |
| DB | `apps/api/tests/db` | SQLite (temporary file / in-memory), rollback per test, migrations up/down/up |
| Agent | `apps/api/tests/agents` (`make test-agents`) | the graph on fake models: delegations, allowlists, `interrupt`/resume (approve/reject), limits, grounding, poisoned tool results, provider swap |
| Security | `apps/api/tests/security` | auth, sessions, lockouts, Turnstile (test keys pass/fail), roles, CSRF token + Origin, **CORS preflight** (allowed/disallowed origin) |
| API / CRUD | `apps/api/tests/api` | for every CRUD resource: `201`+`Location`, `200`, `204`, `404`, `409`, `422`, pagination, filters |
| Integration | `-m integration` | generator → import → fleet optimisation → agent run (fake) → assignment |
| E2E | `tests/e2e` | Playwright against locally running API (`:8000`) and web (`:3000`): login (test key), driver CRUD, chat + trace + approval, manual optimizer, EN/PL |
| Evals | `evals/` (`ai-evals`) | live, budget, a report of success/violations/cost per model |

Every AC has ≥ 1 test with a marker (`@pytest.mark.ac("AC-…")` / `[AC-…]` in the title). Tests are deterministic; no network in `ci-fast`/`ci-full`. Coverage thresholds (lines/branches): `optimization.engine`, `compliance` ≥ 90/85; `identity` ≥ 90/80; `freight`, `fleet`, `routing`, `agents` ≥ 85/75; routers ≥ 75; web `lib/` ≥ 80.

---

## CI Quality Gates

Workflows: `ci-fast` (PR, blocking, ≤ 8 min), `ci-full` (main + nightly), `ai-evals` (manual, secrets, budget). Deployment — post-MVP.

| Gate | Content | fast | full |
|---|---|---|---|
| 1 | ruff format/check; prettier; eslint `--max-warnings=0` | ✅ | ✅ |
| 2 | mypy --strict; tsc --noEmit | ✅ | ✅ |
| 3 | pytest + Hypothesis `ci` + coverage; vitest | ✅ | ✅ (`nightly`) |
| 3a | agent tests on fake models | ✅ | ✅ |
| 4 | OpenAPI drift, TS types drift, `oasdiff breaking`, schemathesis (subset/full) | ✅ | ✅ |
| 5 | alembic up/down/up on a fresh SQLite file; repositories on in-memory SQLite | ✅ | ✅ |
| 6 | integration | — | ✅ |
| 7 | E2E Playwright | — | ✅ |
| 8a/8b/8c | gitleaks / audits+SAST+licences / auth, CSRF and CORS tests | ✅/—/✅ | ✅ |
| 9 | `next build`; API started with `uvicorn` on an empty database + `/health`, `/ready`, one CORS preflight | ✅ | ✅ |
| 10 | import-linter, ESLint boundaries, `trace.py --check`, `check_spec_touch.py` (contracts/migrations/prompts/tools ⇒ specs) | ✅ | ✅ |

**Policy:** `No passing CI → No merge`; `No approved specification → No implementation`; `No acceptance criteria → No completed feature`; `No tests → No completed implementation`; `Breaking API change → Contract review required`; `New migration → Human review`; `Prompt/agent policy change → new version + ai-evals`; `Write tool without interrupt → rejected`.
Locally before a report: `make check` (+ `test-props`, `test-agents`, `test-db` depending on the scope).

---

## Security Requirements

1. Argon2id passwords; a password policy; no registration in the MVP; the `admin` and `demo` accounts are created on first start from `.env` (locally the default demo credentials described in the README; outside `local` your own passwords are required).
2. Turnstile on login (server-side verification before the password; test keys locally); rate limit per IP and account; account lockout after N failed attempts (P1).
3. Sessions: a random token ≥ 256 bits in a cookie `HttpOnly; SameSite=Lax` (`Secure` on HTTPS), only a hash in the DB; expiry; invalidation on logout/password change.
4. CSRF: the frontend and the API are cross-origin (same-site) → a CSRF token (double submit, header `X-CSRF-Token`) + an `Origin` check against the CORS allowlist for state-changing methods.
5. Role authorisation in FastAPI dependencies; tests of the permission matrix; the `demo` account has no admin rights and a low AI budget.
6. Secrets only in `.env` (gitignored) and GitHub Secrets; `.env.example` without secrets (exception: the public Turnstile test keys); gitleaks; no secrets in logs.
7. Security headers (CSP, X-Content-Type-Options, Referrer-Policy); HTTPS and HSTS in the portfolio version (VPS).
8. Agents: see "AI Architecture Rules" (allowlists, `interrupt`, untrusted data, minimisation, budgets).
9. (Post-MVP, VPS) firewall, SSH by key, updates, database backup with an off-site copy.
10. Dependencies: lockfiles, pinned versions, Actions pinned to a SHA, audits, no GPL/AGPL at runtime.
11. API errors: problem+json without stack traces in `demo/production`.

---

## Definition of Ready
- [ ] the specification is `approved` with a revision; ACs have IDs, Given/When/Then and a test type;
- [ ] contracts (API, data, ports, **agent tools** with an Agent Tool Spec) are described or marked "no change";
- [ ] dependencies are merged or mocked; golden cases have values (if applicable);
- [ ] the brief has Allowed/Forbidden paths and shared files; open questions do not block the ACs.

## Definition of Done
- [ ] tests for all ACs in scope pass; `ci-fast` is green (release: `ci-full`);
- [ ] coverage thresholds of the touched packages are met; no new suppressions without a justification;
- [ ] contracts/types are regenerated and committed; no unintended breaking changes;
- [ ] for agent changes: 3a tests are green, `ai-evals` was run when a prompt/policy/tool changed;
- [ ] UI texts exist in EN and PL (for frontend changes);
- [ ] for API changes: CRUD/CORS/problem+json follow the rules, tests exist in `tests/api` and `tests/security`;
- [ ] the run instructions in `README.md` still work from a clean clone (when you change dependencies, environment variables, migrations or the seed);
- [ ] the specification (changelog, status), traceability (`make trace`) and the Completion Report are updated;
- [ ] review has no blocking comments; human consent for high-risk changes; README updated if the scope or the run steps change.

## Pull Request Acceptance Rules
1. A Conventional Commits title + `FEAT-xxx`; the description links the specification, the ACs and the Completion Report.
2. `ci-fast` is green; no changes that lower the rigour of the gates.
3. The diff stays inside the Allowed paths (+ generated files).
4. ≤ ~400 lines of manual changes, or a justification.
5. A change to a contract/migration/prompt/agent tool ⇒ a specification change in the same PR; breaking ⇒ the label `contract-change-approved` from a human.
6. New dependencies are justified (name, version, licence).
7. No secrets, PII or real data.
8. A `write` tool without `interrupt` ⇒ the PR is rejected.
9. Review & QA confirmed conformance; squash merge by a human.

## Human Approval Requirements
Before merge/execution: the `approved` status of a specification and changes to golden cases; ADRs and changes to `context.md`; breaking API changes; migrations; changes in `optimization.engine`/`compliance` that concern invariants, objectives, legal rules or validators; prompts, model policy, allowlists and new agent tools; runtime dependencies and services; CI/CD, secrets, actions on remote servers; real and personal data; publication of media and releases.

---

## Known Risks
| Risk | What the coding agent does |
|---|---|
| Scope vs deadline | sticks to P0 and the cut list |
| Non-determinism of runtime agents | logic in tools; tests on fake models; guards |
| Wrong working-time model | property tests, golden cases, human review; no compliance claims |
| Engine performance | benchmark (`bench/`), pruning instead of weakening constraints |
| ORS limits | cache and fixtures; haversine fallback with a warning |
| LLM API costs/changes | model policy, budgets, fakes in CI |
| Unknown 9 EP geometry | declared capacity + equivalents (Q11) |
| Auth/CORS security | 8c tests, headers, CSRF token, zero secrets in the repo |
| SQLite write concurrency | WAL, `busy_timeout`, short transactions, one worker, checkpoints in a separate file |
| Running on another person's machine | no required keys, seed on start, clean-clone test before release |
| Prompt injection | untrusted data, allowlists, `interrupt` |
| Architecture erosion | import-linter, contracts, small PRs |

## Open Questions
| # | Question | Default assumption |
|---|---|---|
| Q1–Q7 | TIMOCOM: API costs, retention, AI on the data, Basic vs OAuth2, time zone of windows, monitoring of offers | as in `docs/report.md` §38 |
| Q8 | Map tile provider | free with OSM attribution; fallback to a list |
| Q9 | Cost calibration (consumption, driver cost, accommodation, FR/IT tolls) | `docs/report.md` §17.4 (assumptions) |
| Q10 | Domestic PL→PL van rate | 0.85 €/km (assumption) |
| Q11 | Geometry of the 9 EP body | declared capacity, `DECLARED_ONLY` |
| Q12 | Gemini model identifier ("3.8 Flash", "high" mode) | configuration in `AGENT_MODEL_POLICY`, verification in FEAT-006 |
| Q13 | Working-time system of the drivers (equivalent 12 h vs basic 8 h) | 12 h (parameter) |
| Q14 | Night time in the work regulations (Art. 21 of the Act) | P1 |
| Q15 | VPS provider and domain (portfolio version) | after the MVP |
| Q16 | Does the demo account have access to the AI chat | yes, with a low budget |

Owner decisions (2026-11-11): the default assumptions of Q8–Q14 and Q16 are accepted (Q8: OpenFreeMap as the suggested style; Q9: per diems follow the Act — none on international plans, 45 zł/day on domestic ones, FEAT-003 FR-12); Q1–Q7 and Q15 stay post-MVP.

Open questions raised while writing the specifications are recorded in section 11 of each `specs/FEAT-*.md` (IDs `OQ-<feat>-<nn>`); the owner's decisions of 2026-11-11 are recorded at the top of each of those sections.

## Next Implementation Tasks
| # | Task | Scope | Depends on |
|---|---|---|---|
| 0 | Specifications + ADRs | `specs/requirements.md` (REQ/NFR from `docs/report.md` §7–8), `_template.md`, FEAT-000…007, 009 (+ Agent Tool Specs in FEAT-006), GOLD-001…010 with values, ADR-0001…0014, `AGENTS.md`, `CLAUDE.md`, `DEVELOPMENT.md` | — |
| 1 | **FEAT-000** monorepo + `ci-fast` | pnpm + uv, `apps/web` (Next.js strict, next-intl EN/PL skeleton, `.env.example`), `apps/api` (FastAPI, layers, `/health`, `/ready`, CORS, `.env.example`), Makefile (shortcuts), pre-commit, `ci-fast.yml`, scripts (`export_openapi.py`, `trace.py`, `check_spec_touch.py`), **`AGENTS.md` and `CLAUDE.md` kept in sync and pointing to `context.md`** | 0 |
| 2 | **FEAT-001** domain + SQLite + CRUD + auth | models and migrations (SQLite), **REST CRUD**: drivers, vehicles, cost-profiles, freight-offers (manual), CORS + CSRF token, `identity` (Argon2id, sessions, Turnstile with test keys, roles, rate limit), admin/demo accounts on start, audit | 1 |
| 3 | **FEAT-002** generators + import + seed | `fleet-generator v1`, `offers-generator v2` (150 offers, `VEHICLE_UP_TO_3_5_T`, pallets/kg, rates §17.4), `cities.json`, TIMOCOM mapper, idempotent import, **seed on first start**, admin `demo-data/generate|reset` | 2 |
| 4 | **FEAT-003** engine + compliance | `DriverRules` (2 profiles), `CostModel` (fuel with a speed curve, per diems, accommodation, tolls), prefilter, B&B (horizon, chains, `home_by`), fleet assignment, objectives `profit/fastest/fuel`, `RouteValidator`, `FleetValidator`, baselines, oracles, property P*, GOLD-001…010, benchmark | 2 |
| 5 | **FEAT-004** routing + jobs | `RoutingProvider` (matrix from the repo, ORS optional, haversine), `data/mock/routing-matrix.json`, cache, jobs + in-process worker, API for results/plans/assignments | 3, 4 |
| 6 | **FEAT-006** runtime agents | LangGraph graph, 4 agents, tools with allowlists, guards, `interrupt`/resume, SQLite checkpoints, SSE (sse-starlette), `AGENT_MODEL_POLICY` (Gemini/Claude/OpenAI), `explain_plan`, 3a tests, initial evals | 5 |
| 7 | **FEAT-005** frontend | login (Turnstile), AI Dispatcher (chat, trace, approval cards, map), **fleet and offers with CRUD forms**, plan with 3 variants and CO₂, manual optimizer, admin (generator), EN/PL, empty/loading/error states | 5 (contract; MSW before that), 6 (SSE) |
| 8 | **FEAT-007** quality and documentation | `ci-full.yml`, `ai-evals.yml`, E2E, `benchmark_report.py`, **`README.md`: description, technologies, step-by-step run of API and web, the section "How I used AI tools"**, clean-clone run test | 1–7 |
| 9 | **FEAT-009** media | recording `docs/media/demo.mp4` (and/or `.gif`), screenshots `docs/media/screenshots/`, embedding in the README, tag `v0.1.0` | 8 |
| 10 | FEAT-008 (P1) | `interpret_offer_text`, road choice (ORS alternatives) | 5, 6 |

**Now:** task #0, then #1 (FEAT-000).
