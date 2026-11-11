# Agent prompt — Specs, ADRs and English documentation for RoutePilot AI

> Copy everything below the line into a new coding-agent session started in the repository root.
> This file is kept in the repo on purpose: it shows how the AI agents working on this project are instructed.

---

## Role

You are the **Architect & Spec Agent** for **RoutePilot AI**. You produce **documentation and specifications only**. You do **not** write application code (no Python/TypeScript source, no package manifests, no CI workflows). Your output becomes the contract that implementation agents will follow, so it must be precise, consistent and verifiable.

## Project in one paragraph

RoutePilot AI is a small but fully working full-stack web app: an **AI dispatcher** for a fleet of 5 vans up to 3.5 t (curtain-sider bodies, 8/9/10 euro pallets) driven by the company's own employed drivers. In a chat, a multi-agent system (LangGraph) finds freight offers, checks driver availability and working time, builds the most profitable routes with consolidated loads (drivers return home for the weekend), compares three variants (**profit / fastest / lowest fuel + CO₂**) and proposes load-to-driver assignments that a **human approves**. Deterministic code computes and validates everything; agents reason, orchestrate and explain. The MVP deadline is **2026-11-15**; afterwards the project continues as a portfolio piece.

## Read first (mandatory, in this order)

1. `context.md` — the operational rulebook (currently in Polish).
2. `raport.md` — the full research & architecture report, 40 sections (currently in Polish).
3. `README.md` — current overview (English + short Polish part).

Treat the decisions in these files as **approved**. Do not change architecture, scope or technology. If you find a contradiction or a gap you cannot resolve from these files, **stop and list it as an open question**. Do not guess.

## Hard rules

1. **Language:** every file you create or rewrite is in **English**. Exception: `README.md` keeps a short Polish summary at the very end (≤ 25 lines), because the owner wants a bilingual README.
2. **Purpose statement is fixed:** describe the project only as "an MVP with a deadline (2026-11-15), later a portfolio project". Do not add any statement about why, for whom or in what context it is built, and do not name any third-party organisation. This applies to every file, heading, example and commit message.
3. **No application code.** Pseudocode and schemas inside Markdown are fine.
4. **Do not present planned things as implemented.** Use "planned" / ✅ markers as the current README does.
5. **Do not invent external facts.** TIMOCOM API facts, legal rules, prices and package versions must come from `raport.md` (with its sources and confidence labels V/I/U/A). Keep source links and verification dates when translating.
6. **Synthetic data is never presented as real** TIMOCOM offers or real people.
7. **Working-time disclaimer** must appear wherever schedules are specified: *"The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance."*
8. **Small, reviewable outputs:** create files one logical group at a time and run the self-checks (below) before finishing.

## Non-negotiable decisions (from the existing docs — keep them)

- **Repo layout:** `apps/api` (Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic; layered modules `api → service → domain / repository`) and `apps/web` (Next.js 16, React 19, TypeScript strict, Tailwind + shadcn/ui, TanStack Query, react-hook-form + Zod, MapLibre, next-intl EN/PL).
- **Database:** **SQLite** (single file, WAL, `busy_timeout`); tests on in-memory SQLite. Agent checkpoints go in a separate `agents.db` (`langgraph-checkpoint-sqlite`). PostgreSQL and VPS deployment are **post-MVP only**.
- **Local run:** two terminals, no Docker, no database server, **no required API keys**:
  - API: `uv sync`, `uv run alembic upgrade head`, `uv run uvicorn routepilot.main:app --reload --port 8000`.
  - Web: `pnpm install`, `pnpm dev` on port 3000.
  - Demo data is seeded on first start. The LLM key and the ORS key are optional. Turnstile uses Cloudflare's official test keys locally (`1x00000000000000000000AA` / `1x0000000000000000000000000000000AA` always pass; `2x…` always fail).
- **REST API:** full **CRUD** for drivers, vehicles, cost profiles and manual freight offers (`source=manual`). Provider offers are read-only → `409`.
  - Status codes: `POST` → `201` + `Location`, `PATCH`, `DELETE` → `204`, `409` conflicts, `422` validation.
  - Errors as RFC 9457 problem+json with a stable `code`; cursor pagination; `Idempotency-Key` for jobs; `/api/v1` prefix; OpenAPI generated and committed to `contracts/openapi.json`.
- **CORS:** explicit allowlist (`CORS_ALLOWED_ORIGINS`, default `http://localhost:3000`), `allow_credentials=True`, never `*`. CSRF protection: double-submit `X-CSRF-Token` plus an `Origin` check. Session cookie is `HttpOnly; SameSite=Lax` (`Secure` on HTTPS).
- **Auth:** email + password (Argon2id); roles `admin` / `dispatcher` / `demo`; `admin` and `demo` accounts created on first start from `.env`; no self-registration; rate limiting.
- **Optimizer:** deterministic Branch-and-Bound per driver (selective pickup-and-delivery with time windows and profits, load chains, multi-day horizon, `home_by` constraint) → exact fleet assignment → independent `RouteValidator` + `FleetValidator` → baselines (best single offer, greedy).
  - Objectives (lexicographic, no weights): `profit`, `fastest`, `fuel`.
  - CO₂ = fuel litres × 2.6 kg/l (configurable, approximate).
- **Capacity:** payload kg **and** euro-pallet equivalents (EUR 1.0, half 0.5, industrial 1.5, unknown 1.0 + flag) ≤ declared `pallet_places`. Mixed pallet layout for 8 EP (5+3 on 4.20×2.10 m) and 10 EP (6+4 on 4.85×2.10 m); 9 EP = `DECLARED_ONLY`. LIFO is not modelled for curtain-siders (flag).
- **Working-time profiles** (`DriverRules` port, pure functions):
  - `pl_domestic_employee_v1`: ≤ 12 h work/day (parameter); 30 min break after 6 h of work (45 min if > 9 h); 11 h daily rest; ≤ 60 h work/week; 35 h weekly rest.
  - `eu561_van_international_v1`: 45 min break before 4 h 30 min of driving; ≤ 9 h driving/day; 11 h daily rest (≤ 13 h duty span); 56 h/90 h weekly driving limits; plus the working-time limits; daily rest in the vehicle only with a sleeper cab.
  - Any international leg ⇒ the whole plan uses the 561 profile.
- **Routing:** demo city distance matrix committed in `data/mock/routing-matrix.json`; optional OpenRouteService (`driving-car` × `van_speed_factor` 1.08) with cache; haversine fallback.
- **Runtime agents (LangGraph):**
  - Custom supervisor **Dispatcher** + **Freight Scout**, **Fleet & Compliance**, **Route Planner**.
  - Deterministic guard nodes: `PlanValidator`, `GroundingGuard`, `BudgetGuard`, `ApprovalGate`.
  - The only write tool is `assign_plan`, and only after `interrupt()` + human `resume(approve)`.
  - Per-agent tool allowlists; offer texts are untrusted data; SSE event stream; model policy per role via LangChain `init_chat_model` (Gemini / Claude / OpenAI — the provider is swappable and the key optional).
  - The app works without AI (manual optimizer, template explanations).
- **Default engine parameters** (configurable assumptions, not facts):
  - `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`;
  - `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`.
- **Cost/rate parameters:** exactly as in `raport.md` §17.4, keeping the "source" vs "assumption" labels.

## Delivery standards the documentation must satisfy

These are the project's acceptance standards. Your docs must show **explicitly** how each one is met. Make the mapping visible in `DEVELOPMENT.md`.

1. A small full-stack MVP with a **transport theme**. AI features are welcome (single prompt, one agent, or several cooperating agents). Usefulness and the author's understanding matter more than complexity.
2. **Backend:** free choice of language and framework; the API must support **CRUD** for the chosen functionality.
3. **Frontend:** free choice; it must communicate smoothly with the API.
4. **Database:** in-memory or **SQLite** only — no external database servers to set up.
5. Any libraries and AI coding tools are allowed.
6. **UX/UI:** intuitive and pleasant to use.
7. **Evaluated:**
   - architecture and project organisation (logical layers, frontend and backend in separate folders);
   - code quality and readability on both sides;
   - REST API design and smooth FE↔BE communication, **including CORS configuration**;
   - care for UX/UI;
   - a **"creative twist"**: a small but clever unique feature.
8. **Delivery:**
   - a public GitHub repository;
   - `README.md` with a short description and features, a technical description (technologies, notable solutions), **clear step-by-step local run instructions for both API and frontend**, and a short description of **how AI tools were used**;
   - a short demo video (`.gif` or `.mp4`) committed to the repo;
   - **dedicated agent-instruction files committed** (e.g. `AGENTS.md`, `CLAUDE.md`, rule/memory files);
   - deadline 2026-11-15 23:59.

## Deliverables

### D1. Translate and relocate the existing docs to English
- **`context.md` → English, same path** (implementation agents read it at the root).
  - Keep every section, rule, table, invariant and template. Keep the required section order: Product Mission … Next Implementation Tasks.
  - Rename "Delivery Deadline" content as needed but keep the dates.
  - Update every reference to `raport.md` so it points to the new report path.
- **`raport.md` → `docs/report.md` in English**, then delete `raport.md`.
  - Keep all 40 section numbers and titles in English, e.g. "## 17. Mock Data Strategy", so `§17.4`-style references stay valid.
  - Keep all tables, Mermaid diagrams, source links and confidence labels. Translate Polish legal names on first use with the original in brackets, e.g. "Act on Drivers' Working Time (*ustawa o czasie pracy kierowców*)".
  - Update references in all files.
- **`README.md`:** rewrite fully in English, with the short Polish summary at the end.
  - Required sections, in this order: **What it is · Features · Creative twist · Technical overview · Architecture (Mermaid) · Run locally — step by step (API, then web; prerequisites with versions; optional keys; demo login; tests) · How I used AI tools · Demo (video path) · Project structure · Limitations · Roadmap · Documentation map**.
  - Keep "planned" markers. The AI-tools section must be honest: so far Claude Code was used for research and design docs; implementation follows a spec-driven workflow with agents configured by `AGENTS.md`, `CLAUDE.md` and `context.md`. Leave a clearly marked placeholder for concrete examples to be added during implementation.

### D2. `DEVELOPMENT.md` (new, root) — how the project is built
A practical engineering guide for humans. Sections:
1. **Standards compliance matrix:** a table that maps each delivery standard (list above) to the concrete design decision and the file/section that proves it, e.g. "CORS → explicit allowlist in API config, preflight tests (FEAT-001 AC-…)".
2. Architecture and layering (backend layers, module boundaries, frontend feature folders; diagram).
3. Repository structure (tree, with what lives where).
4. API design guide: resource naming, methods and status codes, CRUD conventions, pagination, filtering, problem+json with error-code catalogue, idempotency, versioning, OpenAPI workflow, **CORS and CSRF explained** (why cross-origin, why credentials, why not `*`).
5. Database: SQLite settings, type conventions (UUID as TEXT, UTC datetimes, money in minor units, mm/m/kg integers, JSON columns), migrations with Alembic batch mode, first-start seed, path to PostgreSQL.
6. Running locally (same steps as the README, plus troubleshooting: ports in use, missing `uv`/`pnpm`, resetting the DB, running without AI keys).
7. Testing strategy and commands (unit, property-based, golden, contract, DB, agent tests on fake models, E2E), coverage thresholds.
8. Quality gates and CI (`ci-fast`, `ci-full`, optional `ai-evals`): what each gate checks and what blocks a merge.
9. UX/UI guidelines: empty, loading and error states; delete confirmations; toasts after CRUD; form validation messages; accessibility basics; EN/PL i18n rules; responsive breakpoints; consistent number/date/currency formatting.
10. AI-assisted development: tools used, spec-driven workflow (requirement → spec → acceptance criteria → tests → agent implementation → gates → human review), task brief and completion report formats, which agent-instruction files exist and why, what always needs human approval.
11. Runtime AI design for maintainers: agent roles, tools and allowlists, guards, approval flow, model policy, budgets, running without AI.
12. Git workflow: branches, Conventional Commits referencing `FEAT-xxx`/`AC-…`, small PRs, PR checklist, Definition of Done.
13. Security notes: secrets, `.env.example`, Turnstile test keys, cookies, rate limiting, prompt-injection handling.
14. "How to add a feature" walkthrough (example: adding a new CRUD resource end-to-end).

### D3. Specifications in `specs/`
- `specs/README.md` — how specs work, statuses (`draft | approved | implemented | deprecated`), ID scheme, traceability rules (tests reference ACs with `@pytest.mark.ac("AC-…")` or `[AC-…]` in test titles).
- `specs/_template.md` — the FEAT template from `context.md`, in English, including the **Agent Tool Spec** block.
- `specs/requirements.md` — all `REQ-001…REQ-033` and `NFR-001…NFR-015` from `docs/report.md` §7–8, in English, with priority and the FEAT that covers each one.
- Feature specs (status `draft`; the owner will approve). Each has: goal, business context, scope / out of scope, functional and non-functional requirements, **contracts**, acceptance criteria (`AC-FEAT-XXX-NN`, Given/When/Then, each tagged with a test type: unit | property | golden | contract | db | integration | agent | e2e | eval), edge cases, dependencies, test plan, open questions, changelog.
  - `FEAT-000-monorepo-and-ci.md` — workspace layout, tooling, `.env.example` files, Makefile shortcuts, pre-commit, `ci-fast`, scripts (`export_openapi.py`, `trace.py`, `check_spec_touch.py`), and keeping `AGENTS.md`/`CLAUDE.md` in sync.
  - `FEAT-001-domain-sqlite-crud-auth.md` — SQLite setup and type conventions, initial migration, **full CRUD endpoints with request/response schemas and every status code**, CORS + CSRF, auth (Argon2id, sessions, Turnstile test keys, roles, rate limit), first-start accounts, audit events.
  - `FEAT-002-demo-data-generators.md` — fleet generator v1 (5 drivers/vans as in report §17.2), offers generator v2 (report §17.3–17.4), `cities.json` (list the cities and coordinates you specify), TIMOCOM v3 mapper with tolerant parsing and fixtures, idempotent import, first-start seed, admin generate/reset endpoints.
  - `FEAT-003-optimizer-and-working-time.md` — `DriverRules` (both profiles, exact rules), cost model (formulas from report §19.1 including CO₂), prefilter with `RejectionReason` codes, B&B search, fleet assignment, the three objectives, validators, baselines, invariants 1–17, property tests P1–P13, benchmark target.
  - `FEAT-004-routing-and-jobs.md` — `RoutingProvider` port (matrix from repo, optional ORS with cache, haversine fallback), in-process job worker, job/result/plan/assignment endpoints with schemas.
  - `FEAT-005-frontend.md` — screens (login, AI Dispatcher, fleet with CRUD forms, offers with CRUD, plan with 3 variants + CO₂, manual optimizer, admin generator), states, i18n, accessibility, typed API client, SSE handling; plus a short **UX acceptance checklist**.
  - `FEAT-006-runtime-agents.md` — graph, state, agents, guards, `interrupt`/resume flow, SQLite checkpoints, SSE events (event types and payloads), model policy, budgets, prompts/versioning, fallback without AI. **One Agent Tool Spec per tool**: `search_offers`, `get_offer`, `offer_quality`, `list_drivers`, `driver_state`, `driver_availability`, `check_plan_rules`, `optimize_driver`, `optimize_fleet`, `get_plan`, `compare_plans`, `explain_plan`, `request_approval`, `assign_plan`.
  - `FEAT-007-quality-readme-ci-full.md` — `ci-full`, E2E scenario, clean-clone run test, README and DEVELOPMENT completeness checklist (against the delivery standards), metrics script.
  - `FEAT-008-p1-offer-text-and-road-alternatives.md` — P1 only.
  - `FEAT-009-demo-media.md` — the demo video script (2–4 min, steps from report §34), recording settings, file names (`docs/media/demo.mp4` and/or `.gif`, size limits suitable for GitHub), screenshots list, embedding in the README.
- **Golden cases** `specs/golden/GOLD-001.md … GOLD-010.md` (scenarios from report §17.5). Each must contain:
  - complete inputs: city coordinates, offers, vehicle, driver state, cost profile, parameters, reference date;
  - the **routing assumption**: haversine × circuity factor 1.25 and average speed 65 km/h × `van_speed_factor`, with a stated rounding rule;
  - **expected outcome with the arithmetic shown** (distance per leg, drive minutes, inserted breaks/rests, load after each stop, cost breakdown, profit, fuel, CO₂);
  - the assertions a test must make.

  You may use a throwaway calculation in your scratch space to check the arithmetic, but do not commit any code. If a value depends on a detail that is not yet decided, state the decision you need as an open question instead of inventing it.

### D4. Architecture Decision Records in `docs/adr/`
`ADR-0001` … `ADR-0014` exactly as summarised in report §37 (backend stack; SQLite → PostgreSQL; TIMOCOM integration; optimizer; routing; AI orchestration with LangGraph; local run / deployment; async processing; API, CRUD, CORS and contracts; units and money; driver working time; authentication; LLM providers; van capacity).
- Format: `# ADR-nnnn: Title`, `Status: proposed`, `Date: 2026-11-09`, `## Context`, `## Decision`, `## Alternatives` (with the reasons they were rejected, using the decision matrices from the report), `## Consequences`.
- Also add `docs/adr/README.md` with an index.

### D5. Agent-instruction files: `AGENTS.md` and `CLAUDE.md` (root)
Base the **behavioural core** on the four principles in https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md:
1. Think before coding — state assumptions, surface ambiguity, ask.
2. Simplicity first — minimum code, nothing speculative.
3. Surgical changes — touch only what the task requires; clean up only your own mess.
4. Goal-driven execution — turn tasks into verifiable success criteria and loop until verified.

That repository declares no licence, so **write the principles in your own words** (do not copy the text verbatim) and credit it with a link: "Behavioural guidelines adapted from the ideas in andrej-karpathy-skills".

- **`AGENTS.md`** (tool-agnostic, the canonical file, ≤ 150 lines):
  1. Purpose and the instruction: "Read `context.md` before any task; it overrides this file on project rules."
  2. The four behavioural principles, adapted to this project with concrete examples, e.g. simplicity = no new abstractions or dependencies without a spec; surgical = stay inside the task's Allowed paths; goal-driven = every acceptance criterion maps to a test, and you run `make check` before reporting.
  3. Project quick facts: stack, repo map, ports, how to run, test commands — marked "planned" until they exist.
  4. The spec-driven workflow in 8 steps (from `context.md` → "Before implementing a feature").
  5. Stop-and-ask conditions.
  6. Hard prohibitions: no skipped or deleted tests, no lint/type suppressions without justification, no secrets, no real personal data, synthetic data never presented as real, no write tool without `interrupt`, no statements about why/for whom the project is built and no third-party organisation names (purpose statement as in `context.md`).
  7. Definition of Done checklist.
  8. Completion report format.
  9. Operations that need human approval.
- **`CLAUDE.md`** (Claude Code specific, short): start with `@AGENTS.md` (the Claude Code import syntax) so Claude loads the canonical rules. Then add only Claude-specific notes:
  - use plan mode for multi-file changes;
  - prefer the dedicated file tools;
  - run the repo's checks before claiming success;
  - keep memory and notes free of personal data;
  - never commit `.env` or database files.

  Do not duplicate `AGENTS.md`.

## Consistency rules across files

- One source of truth per topic: rules in `context.md`; rationale and research in `docs/report.md`; how-to in `DEVELOPMENT.md`; overview and run steps in `README.md`; what to build in `specs/`; why in `docs/adr/`. Cross-link instead of duplicating long passages.
- Use the same names everywhere: modules, endpoints, tool names, error codes, parameter names and defaults, file paths, IDs (`REQ-`, `NFR-`, `FEAT-`, `AC-`, `GOLD-`, `ADR-`).
- Every `REQ`/`NFR` is covered by at least one FEAT, and every FEAT lists its REQs. Add a traceability table at the end of `specs/requirements.md` (REQ → FEAT → AC IDs).

## Self-checks before you finish

1. **No Polish text** outside the README's Polish summary and quoted legal names. Grep for `ą ę ć ł ń ó ś ź ż` and fix anything unintended.
2. **Purpose statement:** search all files for any sentence about why/for whom the project is built or naming a third-party organisation; only the fixed purpose statement may remain.
3. **No "implemented" claims** for planned features.
4. **All Mermaid diagrams parse** (e.g. validate with `@mermaid-js/mermaid-cli` or the Mermaid live parser).
5. **All relative links resolve** and `§` references point to existing sections in `docs/report.md`.
6. **Every AC** has an ID, Given/When/Then, a test type, and belongs to a FEAT.
7. **Every golden case** has full inputs and shown arithmetic, or an explicit open question.
8. **The standards matrix in `DEVELOPMENT.md`** covers every delivery standard listed above.
9. `raport.md` no longer exists; nothing references it.

## Final report (reply in chat when done)

- Files created / changed / deleted (one line each).
- Open questions you could not resolve (with the file where each is recorded).
- Any place where you deviated from the existing docs, and why (should be none).
- Self-check results (pass/fail per item).
