---
id: FEAT-004
title: Routing provider, in-process job worker, plans and assignments API
status: approved
owner: project owner
requirements: [REQ-009, REQ-010, REQ-017, REQ-020, NFR-011]
adrs: [ADR-0005, ADR-0008, ADR-0009]
modules: [routing, optimization.jobs, data/mock/routing-matrix.json, main.py (worker start)]
revision: 1
---

# FEAT-004: Routing provider, in-process job worker, plans and assignments API

Priority: **P0**. Nothing in this specification is implemented yet.

> Wherever this API returns a schedule (plans, job results), the response carries the notice: "The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance."

## 1. Goal

The engine of FEAT-003 becomes usable through the API: travel distances and times come from a `RoutingProvider` that works offline, optimisation runs as a background job inside the API process, results are stored as immutable plans, and a human can turn a plan into an assignment.

## 2. Business context

The dispatcher starts an optimisation, waits a few seconds and gets plans (REQ-009, REQ-010). The application must run without an ORS key and without the network (REQ-020, [`context.md`](../context.md) → Project Constraints 1a). An assignment is the only state change that results from optimisation, and a human makes it (REQ-017). Background: [`docs/report.md`](../docs/report.md) §11.1, §15.2, §21; decisions ADR-0005 and ADR-0008.

## 3. Scope / Out of scope

**In scope:** `RoutingProvider` port and three implementations (repo matrix, OpenRouteService, haversine) with a fallback chain and cache; `data/mock/routing-matrix.json`; the job table workflow and the in-process worker; endpoints for optimisation jobs, results, route plans and assignments; the `DriverUsageChecker` implementation for FEAT-001.

**Out of scope:** road alternatives and "avoid motorways" (FEAT-008, P1); agent runs (FEAT-006 reuses the worker infrastructure defined here); a separate worker process or container, `SKIP LOCKED` (post-MVP, ADR-0008); self-hosted routing (post-MVP).

## 4. Functional requirements

### 4.1 Routing

- **FR-1 Port.** As in `context.md` → External Integration Contracts:

  ```python
  class RoutingProvider(Protocol):
      provider_id: str
      def matrix(self, points: Sequence[GeoPoint]) -> TravelMatrix: ...
      def route(self, waypoints: Sequence[GeoPoint], *, variant: RouteVariant) -> RouteResult: ...
  ```

  `TravelMatrix`: `distance_km[i][j]` (Decimal, 2 places), `duration_min[i][j]` (int), `provider_id`, `fallback: bool`. `RouteResult`: `distance_km`, `duration_min`, `geometry` (GeoJSON LineString), `approximate: bool`. `RouteVariant` in the MVP: `FASTEST` only.
- **FR-2 `MatrixFileRoutingProvider`** (`provider_id = "matrix_repo_v1"`). Loads `data/mock/routing-matrix.json` once. A point matches a city when it lies within 1 km of the city's coordinates. `matrix()` answers only if every point matches; durations are `ceil(duration_s × van_speed_factor / 60)` when the file's source is ORS, and are used as stored when the source is haversine (the factor is already included).
- **FR-3 `OrsRoutingProvider`** (`provider_id = "ors_driving_car_v1"`). Used only when `ORS_API_KEY` is set. Profile `driving-car`; durations × `van_speed_factor`. One matrix request for at most 3 500 elements; retries with backoff on transient errors; a per-minute request limit below the free-plan limit. Every response is stored in `routing_cache` under `sha256(provider_id | profile | options | points rounded to 5 decimals)` and served from there afterwards. The key never leaves the server and is never logged.
- **FR-4 `HaversineRoutingProvider`** (`provider_id = "haversine_v1"`). `distance_km = round_half_up(haversine_km × 1.25, 2)`; `duration_min = ceil(distance_km × 60 × van_speed_factor / 65)`; same point → 0 / 0. `route()` returns a straight line per leg with `approximate = true`. (Formula: FEAT-003 OQ-003-01.)
- **FR-5 Fallback chain.** `CompositeRoutingProvider.matrix(points)`: (1) repo matrix if all points match; else (2) ORS if a key is set and the call succeeds; else (3) haversine with `fallback = true`. A matrix built with step 3 makes every plan carry the warning `ROUTING_FALLBACK`. `route()`: cache → ORS (if key) → straight lines (`approximate = true`, plan flag `GEOMETRY_APPROXIMATE`).
- **FR-6 Matrix file.** `data/mock/routing-matrix.json` covers all 39 cities of `cities.json` (FEAT-002 §6.1) in the same order. It is produced once by a script run by the owner (one ORS matrix request, 39 × 39 = 1 521 elements) or, when no key is available, by the haversine formula; the file records which (§6.2).
- **FR-7 Fuel model location.** The fuel and CO₂ formulas live in the engine's cost model (FEAT-003 FR-10, FR-11). `routing` supplies only distances, durations and geometry.

### 4.2 Jobs and worker

- **FR-8 Create.** `POST /optimization-jobs` validates the request, builds the input snapshot (drivers with latest states, vehicles, cost profiles, the offers with their versions, parameters, `CO2_FACTOR_KG_PER_L`, reference time from the injected `Clock`), stores it in `optimization_jobs.request` with `input_sha256`, status `queued`, and returns `202` with `Location`.
- **FR-9 Idempotency.** With an `Idempotency-Key` header: the same key and the same body → the existing job is returned (`202`, same `Location`), no new row; the same key and a different body → `409 IDEMPOTENCY_KEY_REUSED`.
- **FR-10 Worker.** An `asyncio` task started in the application lifespan polls for `queued` jobs (oldest first), one at a time. It marks the job `running`, resolves the travel matrix through `CompositeRoutingProvider` and adds it to the snapshot, runs `optimize(snapshot)` in a `ProcessPoolExecutor(max_workers=1)`, updates `heartbeat_at` and `progress` while waiting, then stores the result and marks the job `succeeded`. An engine exception marks it `failed` with `error {code, message}`.
- **FR-11 Result storage.** On success, in one transaction: a `route_plans` row with its `route_stops` for every returned plan (per-driver top-K per objective and both baselines), and the job's result document (fleet solutions that reference plan ids, rejections, warnings, stats). Stored plans are immutable.
- **FR-12 Recovery.** On startup, a job in `running` with a heartbeat older than 60 s is re-queued if `attempts < 2`, otherwise marked `failed` with `error.code = WORKER_RESTARTED`.
- **FR-13 Logging.** Every log line of a job carries `job_id`; the request that created it also carries `request_id`.
- **FR-14 Limits.** At most 3 queued or running jobs per user; beyond that `429 RATE_LIMITED`.

### 4.3 Plans and assignments

- **FR-15 Read a plan.** `GET /route-plans/{id}` returns the stored plan with stops, cost breakdown, warnings, the legal notice, and `geometry` (computed on first request through `route()` and cached; `null` with `GEOMETRY_APPROXIMATE` handling left to the client when unavailable).
- **FR-16 Create an assignment.** `POST /assignments {routePlanId}` — the caller's click is the human approval. Checks, all in one transaction: the plan exists and is of kind `optimized`; every offer of the plan still has status `open` and the version recorded in the job snapshot; the driver exists, is not deleted and has no active assignment. Any failure → `409 PLAN_NOT_ASSIGNABLE` with `errors[]` naming the reason. On success: insert `assignments` (`status = active`, `approved_by`, `approved_at`, `agent_run_id = null`), set the offers to `assigned`, write an audit event, return `201` + `Location`.
- **FR-17 Cancel.** `DELETE /assignments/{id}` sets `status = cancelled`, returns the plan's offers to `open`, writes an audit event, returns `204`. Cancelling twice → `404`.
- **FR-18 Service reuse.** The same `AssignmentService.assign(plan_id, approved_by, agent_run_id=None)` is called by the HTTP endpoint and, after approval, by the agent write tool `assign_plan` (FEAT-006).
- **FR-19 `DriverUsageChecker`.** `optimization.jobs` implements the port of FEAT-001 §6.3: `"active"` if the driver has an assignment with `status = active`, `"historical"` if only cancelled ones, else `"none"`.

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| REQ-020 | Works offline | with no `ORS_API_KEY` and networking disabled, a fleet job on the seeded data succeeds |
| NFR-011 | Traceable jobs | `job_id` present in all job log lines |
| — | Responsiveness | `POST /optimization-jobs` answers in ≤ 500 ms (target); the API stays responsive while a job runs (health check ≤ 200 ms during a running job) |
| — | Determinism | the same snapshot and matrix give the same stored plans (ids aside) |
| — | Coverage | `routing` ≥ 85/75; `optimization.jobs` routers ≥ 75 |

## 6. Contracts (API, data/migrations, ports, agent tools)

### 6.1 API

All paths under `/api/v1`; minimum role `dispatcher` (dispatcher, demo, admin) for every endpoint here. Common errors (`401`, `403`, `422`, `500`) as in [`DEVELOPMENT.md`](../DEVELOPMENT.md) §4.5.

| Method | Path | Request | Success | Specific errors |
|---|---|---|---|---|
| POST | `/optimization-jobs` | `JobCreate`; optional header `Idempotency-Key` | `202 Job` + `Location: /api/v1/optimization-jobs/{id}` | `404 NOT_FOUND` (unknown driver/offer id), `409 IDEMPOTENCY_KEY_REUSED`, `429 RATE_LIMITED` |
| GET | `/optimization-jobs/{id}` | — | `200 Job` | `404` |
| GET | `/optimization-jobs/{id}/result` | — | `200 JobResult` | `404` (unknown, failed or cancelled job), `409 JOB_NOT_FINISHED` |
| GET | `/route-plans/{id}` | — | `200 RoutePlan` | `404` |
| GET | `/assignments` | `limit`, `cursor`, `driverId`, `status` | `200 {items: Assignment[], nextCursor}` | — |
| POST | `/assignments` | `{routePlanId}` | `201 Assignment` + `Location` | `404`, `409 PLAN_NOT_ASSIGNABLE` |
| GET | `/assignments/{id}` | — | `200 Assignment` | `404` |
| DELETE | `/assignments/{id}` | — | `204` | `404` |

```
JobCreate  { scope ("driver"|"fleet"), driverIds[] (exactly 1 for "driver"; empty = all active drivers for "fleet"),
             offerIds?[] (restrict the pool), objectives?[] (subset of "profit","fastest","fuel"; default all three),
             params? { horizonDays?, maxOffersPerPlan?, topKPerDriver? } }
Job        { id, status ("queued"|"running"|"succeeded"|"failed"|"cancelled"), scope, objectives[],
             progress { phase ("queued"|"routing"|"search"|"assignment"|"saving"), driversDone, driversTotal },
             stats? { nodes, truncated, poolTruncated, runtimeMs }, error? { code, message },
             requestedBy, createdAt, startedAt?, finishedAt? }
JobResult  { jobId, fleet { profit?, fastest?, fuel? : FleetSolution }, perDriver [ { driverId, plans { <objective>: PlanSummary[] } } ],
             baselines { baselineSingle: FleetSolution, baselineGreedy: FleetSolution }, rejections [ { driverId, offerId, stage, code, detail } ],
             warnings[], stats, disclaimer }
FleetSolution { objective, assignments [ { driverId, routePlanId } ], totals { netProfit: Money, fuelL, co2Kg, distanceKm, driversWithPlan } }
PlanSummary   { id, driverId, kind, variant, rank, offerIds[], rulesProfile, netProfit: Money, marginPct, distanceKm, emptyKm,
                fuelL, co2Kg, durationMin, finishAt, homeReached, warnings[] }
RoutePlan     { ...PlanSummary, revenue: Money, costTotal: Money, calculation { fuel, toll, driver, perDiem, accommodation, vehicle : Money,
                parameters { <name>: { value, provenance } } }, workMin, driveMin, waitMin,
                stops [ { sequence, kind, offerId?, label, lat, lon, arrivalAt, waitMin, serviceStartAt, departureAt, legKm, legDriveMin,
                          loadPalletEqAfter, loadKgAfter, counters { workToday, driveToday, workSinceBreak, driveSinceBreak } } ],
                geometry? (GeoJSON), disclaimer }
Assignment    { id, routePlanId, driverId, status ("active"|"cancelled"), approvedBy, approvedAt, agentRunId?, createdAt }
```

`disclaimer` is the fixed notice quoted at the top of this file (the UI shows its translated version).

### 6.2 `data/mock/routing-matrix.json`

```json
{ "version": 1, "source": "ors_driving_car_v1", "profile": "driving-car", "generatedAt": "2026-11-11T00:00:00Z",
  "cities": ["Katowice", "Wrocław"], "distanceM": [[0, 196000], [196000, 0]], "durationS": [[0, 7900], [7900, 0]] }
```

(The numbers in this example are placeholders that only show the shape.) `source` is `ors_driving_car_v1` (raw car durations; `van_speed_factor` is applied at load) or `haversine_v1` (values from FR-4, factor included). `cities` lists city names in the order of `cities.json`.

### 6.3 Data / migrations

Tables `optimization_jobs`, `route_plans`, `route_stops`, `assignments`, `routing_cache` with the columns of report §14 and the type conventions of `DEVELOPMENT.md` §5.2 (distances stored in metres, `fuel_l` in millilitres as INTEGER, `co2_kg` in grams as INTEGER, money in minor units). Additions: `route_plans.co2_g`, `route_plans.fleet_role` (JSON: objectives in whose fleet solution the plan is used), `optimization_jobs.result` (JSON), `assignments` partial uniqueness "one active assignment per driver" enforced in the service (SQLite-portable). These tables are created by the initial migration of FEAT-001 (OQ-001-05).

### 6.4 Problem codes introduced here

`IDEMPOTENCY_KEY_REUSED` (409), `JOB_NOT_FINISHED` (409), `PLAN_NOT_ASSIGNABLE` (409). Job `error.code` values (not HTTP problems): `ENGINE_ERROR`, `ROUTING_ERROR`, `WORKER_RESTARTED`.

### 6.5 Configuration

`ORS_API_KEY` (optional), `ORS_BASE_URL` (default: the public ORS API), `ROUTING_MATRIX_PATH` (default `data/mock/routing-matrix.json`), `WORKER_POLL_INTERVAL_MS` (default 500), `JOB_HEARTBEAT_STALE_S` (default 60), engine parameters of FEAT-003 §5.

### 6.6 Agent tools

No change here. FEAT-006 wraps `JobService`, `PlanService` and `AssignmentService` as tools.

## 7. Acceptance criteria

**Routing**

- **AC-FEAT-004-01** [unit] Given the committed matrix file with source `ors_driving_car_v1` and `van_speed_factor = 1.08` When `matrix()` is asked for Katowice, Wrocław and Dresden (coordinates from `cities.json`) Then distances equal the file values in km (2 decimals), durations equal `ceil(duration_s × 1.08 / 60)`, `provider_id = "matrix_repo_v1"` and `fallback = false`.
- **AC-FEAT-004-02** [unit] Given `HaversineRoutingProvider` When a matrix is requested for demo cities Then Katowice → Wrocław is 210.45 km and 210 min, Wrocław → Dresden is 288.36 km and 288 min, a point to itself is 0 km and 0 min, and the matrix is symmetric (values from `specs/golden/README.md` G1–G3).
- **AC-FEAT-004-03** [unit] Given a point that is not within 1 km of any city and no ORS key When the composite provider builds a matrix Then it comes from haversine with `fallback = true`, and a plan computed on it carries `ROUTING_FALLBACK`.
- **AC-FEAT-004-04** [contract] Given recorded ORS matrix and directions responses as fixtures When `OrsRoutingProvider` parses them Then distances, durations (× `van_speed_factor`) and geometry are mapped correctly; a recorded rate-limit response leads to a retry and then to the fallback.
- **AC-FEAT-004-05** [db] Given an ORS response stored in `routing_cache` When the same points are requested again (also in a different coordinate precision beyond 5 decimals) Then no HTTP call is made and the cached value is returned.
- **AC-FEAT-004-06** [unit] Given no `ORS_API_KEY` and a transport that fails on any request When matrices and routes are requested Then no HTTP request is attempted and results come from the repo matrix or haversine.
- **AC-FEAT-004-07** [unit] Given an ORS duration of 6 000 s and `van_speed_factor = 1.08` When the travel matrix is built Then the matrix duration is 108 min; with factor 1.0 it is 100 min.
- **AC-FEAT-004-08** [unit] Given `data/mock/routing-matrix.json` and `data/mock/cities.json` When both files are loaded Then the matrix lists the same 39 cities in the same order, both tables are 39 × 39 with a zero diagonal and non-negative integers, and `source` is one of the two allowed values.

**Jobs**

- **AC-FEAT-004-09** [contract] Given a dispatcher session and seeded data When `POST /api/v1/optimization-jobs` is called with `{ "scope": "fleet", "driverIds": [] }` Then the status is `202`, `Location` points to the job, the body has `status = "queued"` and all three objectives; `scope = "driver"` with two ids returns `422`; an unknown driver id returns `404`.
- **AC-FEAT-004-10** [contract] Given a job created with `Idempotency-Key: K` When the same request is repeated with `K` Then the response is `202` with the same job id and only one row exists; When a different body is sent with `K` Then the status is `409` with `code = IDEMPOTENCY_KEY_REUSED`.
- **AC-FEAT-004-11** [integration] Given a queued fleet job on the seeded data with no API keys When the worker runs Then the job passes through `running` to `succeeded`, `progress.driversDone` reaches `driversTotal`, `stats` is filled, and every log line of the run contains the `job_id`.
- **AC-FEAT-004-12** [contract] Given a succeeded job When `GET …/result` is called Then the status is `200` and the body contains fleet solutions for the requested objectives, per-driver plan summaries, both baselines, the rejection list and the `disclaimer`; every `routePlanId` in it can be read with `GET /route-plans/{id}`.
- **AC-FEAT-004-13** [contract] Given a queued or running job When `GET …/result` is called Then the status is `409` with `code = JOB_NOT_FINISHED`; for a failed job the status is `404` and `GET /optimization-jobs/{id}` shows `error.code`.
- **AC-FEAT-004-14** [integration] Given a job left in `running` with a heartbeat older than 60 s and `attempts = 1` When the application starts Then the job is re-queued and completes; with `attempts = 2` it becomes `failed` with `error.code = WORKER_RESTARTED`.
- **AC-FEAT-004-15** [integration] Given two queued jobs When the worker runs Then they execute one after another (never two `running` at once), and `GET /health` answers within 200 ms while a job is running.
- **AC-FEAT-004-16** [db] Given a succeeded job When a driver, an offer and the cost profile are changed afterwards Then the stored snapshot, plans and stops are unchanged and no API method can modify a plan.
- **AC-FEAT-004-17** [contract] Given a stored plan When `GET /api/v1/route-plans/{id}` is called Then the body contains ordered stops with times, load after each stop and counters, the cost breakdown with parameter provenance, `fuelL`, `co2Kg`, warnings and the `disclaimer`; an unknown id returns `404`.

**Assignments**

- **AC-FEAT-004-18** [contract] Given an optimised plan whose offers are open When `POST /api/v1/assignments` is called Then the status is `201` with `Location`, the plan's offers have status `assigned`, an audit event exists and the driver's `DriverUsageChecker` answer is `"active"`; When the same plan or another plan with one of those offers is assigned Then the status is `409` with `code = PLAN_NOT_ASSIGNABLE`; a baseline plan is also refused with `409`.
- **AC-FEAT-004-19** [contract] Given an active assignment When `DELETE /api/v1/assignments/{id}` is called Then the status is `204`, the assignment is `cancelled`, the offers are `open` again, the checker answers `"historical"`, and a second `DELETE` returns `404`.
- **AC-FEAT-004-20** [contract] Given anonymous and logged-in callers When the endpoints of §6.1 are called Then anonymous calls return `401`, state-changing calls without a CSRF token return `403`, and a fourth simultaneous job of one user returns `429 RATE_LIMITED`.

## 8. Edge cases

- A fleet job with zero active drivers or zero open offers → succeeds with empty solutions and an empty or full rejection list.
- An offer edited between job creation and assignment → `409 PLAN_NOT_ASSIGNABLE` (version differs from the snapshot).
- ORS returns fewer rows than requested or a non-routable point → treated as an ORS failure → fallback.
- The matrix file is missing or malformed → startup warning; the provider chain skips it.
- Two browser tabs assign conflicting plans at the same moment → one `201`, one `409` (single transaction).
- The process stops between "result stored" and "status succeeded" → both are in the same transaction, so this cannot leave a half-written result.
- A job requested by a user who is deleted later → the job and plans stay; `requestedBy` remains as an id.
- Geometry request for a plan computed with haversine → straight lines with `approximate = true`.

## 9. Dependencies

- FEAT-001 (tables, sessions, CSRF), FEAT-002 (`cities.json`, seed), FEAT-003 (engine, result model).
- ADR-0005, ADR-0008.
- Libraries: httpx for ORS (version to be verified in the registry). No queue library.
- Creating the committed matrix needs one ORS request with the owner's key — an operation that needs human approval (`context.md` → Operations that need human confirmation).

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| 01–03, 06–08 | `apps/api/tests/unit/routing/` | a small matrix fixture; the committed files |
| 04 | `apps/api/tests/contract/test_ors_adapter.py` | recorded ORS responses in `apps/api/tests/fixtures/ors/` |
| 05, 16 | `apps/api/tests/db/` | in-memory SQLite |
| 09, 10, 12, 13, 17–20 | `apps/api/tests/api/test_jobs.py`, `test_route_plans.py`, `test_assignments.py` | seeded test database; a synchronous test worker |
| 11, 14, 15 | `apps/api/tests/integration/test_worker.py` | temporary SQLite file; `FixedClock` |

## 11. Open questions

**Owner decisions (2026-11-11):** all proposed defaults in this table are accepted. OQ-004-02: no ORS key is available, so the haversine variant of `routing-matrix.json` (`source = haversine_v1`) is committed and replaced after the MVP.

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-004-01 | `provider_id` values: `context.md` has `"ors_driving_car_v1" | "haversine_v1"`, report §15.2 has `"ors_v2_driving_car"`, and the repo matrix needs an id. | `ors_driving_car_v1` (`context.md` wins), `haversine_v1`, and the new `matrix_repo_v1`. | naming in results and tests |
| OQ-004-02 | Who creates `routing-matrix.json` and from which source? It needs an ORS key once. | The owner runs the script with a key before FEAT-004 is merged; if no key is available, commit the haversine variant (`source = haversine_v1`) and replace it later. | AC-FEAT-004-01, 08 |
| OQ-004-03 | ORS request and response shapes are not quoted in the report (only profile, options and limits). | Record real responses as fixtures during implementation; do not write the adapter from memory. | AC-FEAT-004-04 |
| OQ-004-04 | Should the HTTP `POST /assignments` exist next to the agent flow, given "the only write tool is `assign_plan` after `interrupt`"? | Yes: that rule limits runtime agents. A human using the manual optimizer assigns directly; both paths call the same service. | AC-FEAT-004-18 |
| OQ-004-05 | Should assigning a plan create a new `DriverState` (position and counters after the plan)? | No in the MVP; the state stays as entered. | fleet view after assignment |
| OQ-004-06 | Job progress to the UI: polling or SSE? | Polling `GET /optimization-jobs/{id}` every second; SSE is used only for agent runs. | FEAT-005 optimizer screen |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-09 | Initial draft |
| 2 | 2026-11-11 | Owner decisions on the open questions recorded (§11) |
| 3 | 2026-11-11 | Status `draft` → `approved` by the owner |
