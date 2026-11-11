# Requirements

Source: [`docs/report.md`](../docs/report.md) §7 (functional) and §8 (non-functional). This file is the list of record; it is a **shared file** (one author at a time, see [`context.md`](../context.md) → Module Boundaries).

> **Status (2026-11-09):** design phase. Nothing is implemented. "FEAT" columns name the specification that covers a requirement, not finished work.

Priorities: **P0** = MVP (deadline 2026-11-15); **P1** = only if time allows; **Post** = after the MVP, needs a new specification.

## 1. Functional requirements

| ID | Requirement | Priority | Covered by |
|---|---|---|---|
| REQ-001 | Offer model independent of the source, with field provenance | P0 | FEAT-001, FEAT-002 |
| REQ-002 | Idempotent import of offers from a provider (mock in the TIMOCOM v3 format) | P0 | FEAT-002 |
| REQ-003 | Deterministic offer generator for vans ≤ 3.5 t (150 offers, PL + EU, difficulty categories) | P0 | FEAT-002 |
| REQ-004 | Deterministic fleet generator: 5 drivers with assigned vans 8/9/10 EP, bases, positions, working-time state; started from the admin panel or the CLI | P0 | FEAT-002 |
| REQ-005 | Login with email + password and Cloudflare Turnstile (official test keys locally), roles `admin`/`dispatcher`/`demo`, demo account created on first start, logout, lockout after many failed attempts | P0 (lockout: P1) | FEAT-001, FEAT-005 |
| REQ-006 | Full CRUD through the REST API and the UI: drivers, vehicles, cost profiles, manual offers (`source=manual`; provider offers are read-only); generator and reset of demo data in the admin panel | P0 | FEAT-001, FEAT-002, FEAT-005 |
| REQ-007 | Offer list with filters, data completeness and provenance | P0 | FEAT-001, FEAT-005 |
| REQ-008 | Fleet view: drivers, vans, positions, working-time state, availability | P0 | FEAT-001, FEAT-005 |
| REQ-009 | Optimisation for a selected driver: top-K plans (consolidated loads + chain of orders within the horizon), with a schedule, breaks/rests, occupancy (EP, kg), costs and profit | P0 | FEAT-003, FEAT-004, FEAT-005 |
| REQ-010 | Fleet optimisation: assignment of offers to drivers that maximises total profit, without duplicating offers | P0 | FEAT-003, FEAT-004 |
| REQ-011 | Three result variants: most profitable, fastest (earliest completion), lowest fuel consumption | P0 (combinations/order), P1 (road choice) | FEAT-003, FEAT-005, FEAT-008 |
| REQ-012 | Working-time model with the profiles `pl_domestic_employee_v1` and `eu561_van_international_v1`; a plan never violates the rules of its profile | P0 | FEAT-003 |
| REQ-013 | Return of the driver to base for the weekend as a hard constraint (configurable) | P0 | FEAT-003 |
| REQ-014 | Comparison with baselines (best single offer per driver; greedy assignment) and a rejection report | P0 | FEAT-003 |
| REQ-015 | Chat with the AI dispatcher (multi-agent system): questions in natural language, delegation to agents, answers based on tool results | P0 | FEAT-006, FEAT-005 |
| REQ-016 | Trace of agent activity in the UI (which agent, which tool, result, time, tokens) in real time | P0 | FEAT-006, FEAT-005 |
| REQ-017 | Human approval of state-changing actions (assigning an offer to a driver) | P0 | FEAT-006, FEAT-004, FEAT-005 |
| REQ-018 | Plan explanation with verification of numbers (grounding) and a template fallback | P0 | FEAT-006 |
| REQ-019 | Route map with stops and their order | P0 (degradable to a list) | FEAT-005 |
| REQ-020 | Routing: demo city matrix stored in the repo, ORS with a cache when a key is given, estimation fallback — the application works offline | P0 | FEAT-004 |
| REQ-021 | EN/PL interface | P0 (switch, key screens), P1 (full coverage) | FEAT-005, FEAT-000 |
| REQ-022 | Interpretation of offer descriptions by the Freight Scout agent (pallets, pallet type, remarks) as enrichment with provenance `ai` | P1 | FEAT-008 |
| REQ-023 | Alternative roads for legs (fastest vs avoiding motorways) and their effect on time and fuel | P1 | FEAT-008 |
| REQ-024 | Risk rating of a plan (time buffers, inferred data) | P1 | FEAT-008 |
| REQ-025 | Event-driven mode: automatic rating of new offers and an inbox of proposals | Post | — (no specification; out of MVP scope) |
| REQ-026 | Driver messaging (Telegram/SMS/WhatsApp) with approval | Post | — |
| REQ-027 | Real offer sources (TIMOCOM, other exchanges) | Post | — |
| REQ-028 | Tachograph/telematics data as the source of driver state | Post | — |
| REQ-029 | Multi-tenant SaaS | Post | — |
| REQ-030 | MCP server with RoutePilot tools | Post | — |
| REQ-031 | Carbon footprint: kg CO₂ for every plan and variant (litres of diesel × emission factor), comparison of variants | P0 | FEAT-003, FEAT-005 |
| REQ-032 | Local run without Docker, a database server or API keys; data seed on first start; explicit CORS between `localhost:3000` and `localhost:8000` | P0 | FEAT-000, FEAT-001, FEAT-002, FEAT-007 |
| REQ-033 | Delivery documentation: `README.md` (description, technologies, step-by-step run of API and web, how AI tools were used), a `.mp4`/`.gif` recording in the repo, instruction files for coding agents in the repo | P0 | FEAT-007, FEAT-009, FEAT-000 |

Note on REQ-012: the report writes the profile names as `PL_DOMESTIC_EMPLOYEE` / `EU_561_VAN_INTERNATIONAL`. The identifiers used in code and specifications are `pl_domestic_employee_v1` / `eu561_van_international_v1` (`context.md` → Core Domain Rules 6–8).

## 2. Non-functional requirements

| ID | Requirement | Measure | Priority | Covered by |
|---|---|---|---|---|
| NFR-001 | Engine determinism: identical snapshot → identical result | property + golden tests; node budget | P0 | FEAT-003 |
| NFR-002 | Engine performance: per driver a pool of ≤ 60 offers, ≤ 6 offers in a plan, a 5-day horizon; a fleet of 5 drivers | p95 ≤ 15 s for the whole fleet optimisation on a typical laptop (target; to be measured) | P0 | FEAT-003 |
| NFR-003 | Correctness: 0 plans that violate the invariants | validator + property tests | P0 | FEAT-003 |
| NFR-004 | Agent control: every run is bounded — max steps (`recursion_limit`), max tool calls, token budget, timeout | configuration + tests | P0 | FEAT-006 |
| NFR-005 | AI resilience: no LLM or an LLM failure → the application works (optimisation from the UI, template explanations) | tests with a fake model | P0 | FEAT-006, FEAT-005 |
| NFR-006 | Model swappability: changing the provider/model only through configuration | contract test for ≥ 2 providers (fakes) | P0 | FEAT-006 |
| NFR-007 | Chat latency: first token / trace event ≤ 2 s after sending the question (streaming) | measurement | P0 | FEAT-006 |
| NFR-008 | Security: OWASP ASVS L1 for auth; no secrets in the repo; no PII in prompts | tests, gitleaks | P0 | FEAT-001, FEAT-000, FEAT-006 |
| NFR-009 | Contracts: OpenAPI matches the implementation; no unintended breaking changes | drift + oasdiff | P0 | FEAT-000, FEAT-001 |
| NFR-010 | Accessibility: WCAG 2.1 AA for key views | manual checklist (P0), axe (P1) | P0 / P1 | FEAT-005 |
| NFR-011 | Observability: JSON logs with `request_id`, `run_id`, `job_id`; agent trace in the DB; optionally LangSmith | review | P0 | FEAT-001, FEAT-004, FEAT-006 |
| NFR-012 | Cost: local run without charges; optional LLM with a daily token budget | configuration | P0 | FEAT-006, FEAT-007 |
| NFR-013 | Maintainability: module boundaries enforced automatically | import-linter, ESLint | P0 | FEAT-000, FEAT-003 |
| NFR-014 | Ease of running: clean clone → working application in ≤ 10 min following the README; no Docker, database server or API keys | "clean clone" test | P0 | FEAT-007, FEAT-000 |
| NFR-015 | API quality: REST consistent with HTTP semantics, full CRUD, problem+json, CORS with an allowlist | contract and CORS tests | P0 | FEAT-001 |

## 3. Traceability (REQ → FEAT → AC)

AC IDs refer to section 7 of each FEAT file. Ranges are inclusive. This table is maintained by hand until `scripts/trace.py` generates `docs/traceability.md` (FEAT-000).

| Requirement | FEAT | Acceptance criteria |
|---|---|---|
| REQ-001 | FEAT-001 | AC-FEAT-001-12 … 14 |
| | FEAT-002 | AC-FEAT-002-09 … 12 |
| REQ-002 | FEAT-002 | AC-FEAT-002-13, 14, 20 |
| REQ-003 | FEAT-002 | AC-FEAT-002-04 … 07, 18, 19 |
| REQ-004 | FEAT-002 | AC-FEAT-002-01 … 03, 16 |
| REQ-005 | FEAT-001 | AC-FEAT-001-20 … 22, 25 … 29, 33 |
| | FEAT-005 | AC-FEAT-005-01 … 03 |
| REQ-006 | FEAT-001 | AC-FEAT-001-04 … 15 |
| | FEAT-002 | AC-FEAT-002-16, 17 |
| | FEAT-005 | AC-FEAT-005-05 … 08, 10, 17 |
| REQ-007 | FEAT-001 | AC-FEAT-001-14 |
| | FEAT-005 | AC-FEAT-005-09 |
| REQ-008 | FEAT-001 | AC-FEAT-001-05, 06, 15 |
| | FEAT-005 | AC-FEAT-005-04 |
| REQ-009 | FEAT-003 | AC-FEAT-003-01 … 05, 08, 30 … 37 |
| | FEAT-004 | AC-FEAT-004-09 … 12, 17 |
| | FEAT-005 | AC-FEAT-005-26 |
| REQ-010 | FEAT-003 | AC-FEAT-003-10, 24, 38 |
| | FEAT-004 | AC-FEAT-004-09 |
| REQ-011 | FEAT-003 | AC-FEAT-003-13, 23 |
| | FEAT-005 | AC-FEAT-005-11 |
| | FEAT-008 | AC-FEAT-008-04 … 06 |
| REQ-012 | FEAT-003 | AC-FEAT-003-05, 14 … 18, 34, 36 |
| REQ-013 | FEAT-003 | AC-FEAT-003-11, 37 |
| REQ-014 | FEAT-003 | AC-FEAT-003-12, 22, 26, 35 |
| REQ-015 | FEAT-006 | AC-FEAT-006-01, 26 … 39 |
| | FEAT-005 | AC-FEAT-005-14 |
| REQ-016 | FEAT-006 | AC-FEAT-006-15, 16, 22 |
| | FEAT-005 | AC-FEAT-005-14, 21 |
| REQ-017 | FEAT-006 | AC-FEAT-006-03 … 06, 23 |
| | FEAT-004 | AC-FEAT-004-18, 19 |
| | FEAT-005 | AC-FEAT-005-15 |
| REQ-018 | FEAT-006 | AC-FEAT-006-09, 10, 25 |
| REQ-019 | FEAT-005 | AC-FEAT-005-23 |
| REQ-020 | FEAT-004 | AC-FEAT-004-01 … 08 |
| REQ-021 | FEAT-005 | AC-FEAT-005-18 |
| | FEAT-000 | AC-FEAT-000-04 |
| REQ-022 | FEAT-008 | AC-FEAT-008-01 … 03 |
| REQ-023 | FEAT-008 | AC-FEAT-008-04 … 07 |
| REQ-024 | FEAT-008 | AC-FEAT-008-08 |
| REQ-025 … REQ-030 | — | post-MVP; no specification and no ACs yet |
| REQ-031 | FEAT-003 | AC-FEAT-003-06, 20 |
| | FEAT-005 | AC-FEAT-005-11 |
| REQ-032 | FEAT-000 | AC-FEAT-000-01, 02, 12 |
| | FEAT-001 | AC-FEAT-001-17 … 19, 29 |
| | FEAT-002 | AC-FEAT-002-15 |
| | FEAT-007 | AC-FEAT-007-04 |
| REQ-033 | FEAT-007 | AC-FEAT-007-05, 06 |
| | FEAT-009 | AC-FEAT-009-01 … 04 |
| | FEAT-000 | AC-FEAT-000-13 |
| NFR-001 | FEAT-003 | AC-FEAT-003-07 |
| NFR-002 | FEAT-003 | AC-FEAT-003-27, 29 |
| NFR-003 | FEAT-003 | AC-FEAT-003-01 … 13, 25 |
| NFR-004 | FEAT-006 | AC-FEAT-006-11, 12, 24 |
| NFR-005 | FEAT-006 | AC-FEAT-006-18, 19, 25 |
| | FEAT-005 | AC-FEAT-005-13, 16 |
| NFR-006 | FEAT-006 | AC-FEAT-006-17 |
| NFR-007 | FEAT-006 | AC-FEAT-006-15 |
| NFR-008 | FEAT-001 | AC-FEAT-001-20 … 31 |
| | FEAT-000 | AC-FEAT-000-06, 12 |
| | FEAT-006 | AC-FEAT-006-20 |
| NFR-009 | FEAT-000 | AC-FEAT-000-07 |
| | FEAT-001 | AC-FEAT-001-32 |
| NFR-010 | FEAT-005 | AC-FEAT-005-19, 27 |
| NFR-011 | FEAT-001 | AC-FEAT-001-16 |
| | FEAT-004 | AC-FEAT-004-11 |
| | FEAT-006 | AC-FEAT-006-22 |
| NFR-012 | FEAT-006 | AC-FEAT-006-19, 24 |
| | FEAT-007 | AC-FEAT-007-04 |
| NFR-013 | FEAT-000 | AC-FEAT-000-11 |
| | FEAT-003 | AC-FEAT-003-28 |
| NFR-014 | FEAT-007 | AC-FEAT-007-04 |
| | FEAT-000 | AC-FEAT-000-01 |
| NFR-015 | FEAT-001 | AC-FEAT-001-04 … 19, 32 |

## 4. Coverage check

- Every P0 and P1 requirement is covered by at least one FEAT.
- REQ-025 … REQ-030 are post-MVP by decision ([`context.md`](../context.md) → MVP Boundaries). They have no FEAT on purpose: implementing them needs a new specification.
- Every FEAT lists its requirements in its front matter; FEAT-000 … FEAT-009 together reference all requirements above.
