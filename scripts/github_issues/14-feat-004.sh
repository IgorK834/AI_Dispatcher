# FEAT-004 — Routing and jobs. Sourced by scripts/create_github_issues.sh.
# shellcheck shell=bash disable=SC2034

s_004_1() {
  I_ID="004/1"; I_FEAT="004"; I_TITLE="RoutingProvider: repo matrix, haversine, composite fallback, committed routing-matrix.json"
  I_AREA="backend"; I_SIZE="M"; I_DAY="2026-11-11"; I_CATCHUP="2026-11-13"
  I_ACS="01 02 03 06 07 08"; I_DEPS="002/1"
  I_GATES="make check"
  I_LOCK="\`data/mock/routing-matrix.json\`, \`apps/api/.env.example\` (\`ROUTING_MATRIX_PATH\`)"
  I_BRANCH="feat/FEAT-004-routing-providers"; I_REQS="REQ-020"; I_ADRS="0005"; I_SCOPE_TAG="routing"
  txt T_GOAL <<'EOF'
The application gets distances and driving times offline: from a committed city matrix when all points are demo cities, otherwise from a deterministic haversine estimate that is clearly flagged — with the port shaped so that OpenRouteService can plug in later.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-004-routing-and-jobs.md` §4.1 FR-1, FR-2, FR-4, FR-5, FR-6, FR-7, §6.2 (matrix file shape), §6.5 (configuration), §8 (missing or malformed matrix file), §11 OQ-004-01, OQ-004-02
- `specs/golden/README.md` G1–G3 (haversine formula and rounding)
- `context.md` → External Integration Contracts (`RoutingProvider`), Architecture Principle 8 (`ROUTING_FALLBACK`)
- `docs/adr/ADR-0005-routing.md`
EOF
  txt T_SCOPE <<'EOF'
- Port `RoutingProvider` with `TravelMatrix` (`distance_km` Decimal 2, `duration_min` int, `provider_id`, `fallback`), `RouteResult` (`distance_km`, `duration_min`, GeoJSON `geometry`, `approximate`), `RouteVariant.FASTEST` (FR-1).
- `MatrixFileRoutingProvider` (`matrix_repo_v1`): loads the file once; a point matches a city within 1 km; answers only when every point matches; durations `ceil(duration_s × van_speed_factor / 60)` for an ORS-sourced file, as stored for a haversine file (FR-2).
- `HaversineRoutingProvider` (`haversine_v1`): `round_half_up(haversine × 1.25, 2)`, `ceil(km × 60 × factor / 65)`, same point 0/0; `route()` straight lines with `approximate = true` (FR-4).
- `CompositeRoutingProvider`: repo matrix → (ORS when 004/2 adds it and a key is set) → haversine with `fallback = true`; `route()`: cache → ORS (if key) → straight lines + `GEOMETRY_APPROXIMATE` (FR-5).
- A generator script and the committed `data/mock/routing-matrix.json` for the 39 cities in `cities.json` order — haversine variant (`source = haversine_v1`, OQ-004-02).
- No HTTP request at all without `ORS_API_KEY` (AC-06).
EOF
  txt T_OUT <<'EOF'
- `OrsRoutingProvider` and `routing_cache` (004/2); road alternatives (FEAT-008); the fuel model (it lives in the engine, FR-7).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/routing/{ports.py,matrix_file.py,haversine.py,composite.py}` — new
- `scripts/generate_routing_matrix.py` (*suggested* name) — new
- `data/mock/routing-matrix.json` — new (generated, committed)
- `apps/api/tests/unit/routing/{test_matrix_file.py,test_haversine.py,test_composite.py,test_matrix_files_consistency.py}`, `apps/api/tests/fixtures/routing/matrix_ors_small.json` — new
EOF
  txt T_IFACE <<'EOF'
```python
class RoutingProvider(Protocol):           # routing/ports.py
    provider_id: str                        # "matrix_repo_v1" | "ors_driving_car_v1" | "haversine_v1"
    def matrix(self, points: Sequence[GeoPoint]) -> TravelMatrix: ...
    def route(self, waypoints: Sequence[GeoPoint], *, variant: RouteVariant) -> RouteResult: ...
```
Matrix file: `{ "version": 1, "source": "ors_driving_car_v1" | "haversine_v1", "profile": "driving-car", "generatedAt", "cities": [...], "distanceM": [[...]], "durationS": [[...]] }`.
EOF
  txt T_TESTS <<'EOF'
- `test_matrix_file.py` — with an ORS-sourced fixture matrix and factor 1.08: Katowice/Wrocław/Dresden distances equal the file in km (2 decimals), durations `ceil(s × 1.08 / 60)`, `provider_id = matrix_repo_v1`, `fallback = false` → AC-01; ORS duration 6 000 s → 108 min with 1.08, 100 min with 1.0 → AC-07.
- `test_haversine.py` — Katowice → Wrocław 210.45 km / 210 min, Wrocław → Dresden 288.36 km / 288 min, self 0/0, symmetric (golden G1–G3). → AC-02
- `test_composite.py` — a point not within 1 km of any city, no key → haversine with `fallback = true` and plans carry `ROUTING_FALLBACK` → AC-03; no key + a transport that fails on any request → no HTTP attempted, results from repo matrix or haversine → AC-06.
- `test_matrix_files_consistency.py` — `routing-matrix.json` and `cities.json` list the same 39 cities in the same order, 39 × 39, zero diagonal, non-negative integers, allowed `source`. → AC-08
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run python ../scripts/generate_routing_matrix.py --source haversine --out ../data/mock/routing-matrix.json
git diff --exit-code ../data/mock/routing-matrix.json
uv run pytest tests/unit/routing -q && make check
```
EOF
  txt T_TIPS <<'EOF'
- AC-01 says "the committed matrix file with source `ors_driving_car_v1`", but OQ-004-02 commits the haversine variant. Test AC-01 on a small ORS-shaped fixture (the test plan allows "a small matrix fixture"); if the owner switches the committed file to ORS (O-5, step 5), extend the test to the real file. Mention this in the report.
- The haversine file stores durations with the factor already included — do not apply it twice.
- The engine receives the matrix as a value; `routing` must not import the engine and vice versa.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-004-01 (accepted): provider ids `ors_driving_car_v1`, `haversine_v1`, `matrix_repo_v1`.
- OQ-004-02 (accepted): commit the haversine variant of `routing-matrix.json`; replace later. See owner action O-5 for a possible switch.
EOF
}
register s_004_1

s_004_2() {
  I_ID="004/2"; I_FEAT="004"; I_TITLE="OrsRoutingProvider (driving-car) with retries, fallback and routing_cache"
  I_AREA="backend"; I_SIZE="M"; I_DAY="2026-11-11"; I_CATCHUP="2026-11-13"
  I_ACS="04 05"; I_DEPS="004/1 O-5"
  I_GATES="make check, uv run pytest tests/contract/test_ors_adapter.py, make test-db"
  I_LOCK="🔒 recorded ORS fixtures (\`apps/api/tests/fixtures/ors/\`; external calls with the owner's approval, no key in any file), \`apps/api/uv.lock\` (httpx)"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-004-ors-adapter"; I_REQS="REQ-020"; I_ADRS="0005"; I_SCOPE_TAG="routing"
  txt T_GOAL <<'EOF'
With an optional `ORS_API_KEY`, real road distances, durations and geometry come from OpenRouteService — cached forever per request, retried on transient errors, never blocking the app when ORS fails, and never leaking the key.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-004-routing-and-jobs.md` §4.1 FR-3, FR-5, §6.5, §8 (fewer rows, non-routable point), §10 row 04, §11 OQ-004-03
- `context.md` → External Integration Contracts (ORS: key on the server, cache, fixtures, tests never call ORS), Operations that need human confirmation (ORS console / external calls)
- Owner action O-5 (key and recording approval)
EOF
  txt T_SCOPE <<'EOF'
- `OrsRoutingProvider` (`ors_driving_car_v1`) used only when `ORS_API_KEY` is set: profile `driving-car`; durations × `van_speed_factor`; one matrix request ≤ 3 500 elements; retries with backoff on transient errors; a per-minute request limit below the free plan's; on failure the composite falls back (FR-3, FR-5).
- `routing_cache` read/write: key `sha256(provider_id | profile | options | points rounded to 5 decimals)`; every response stored and served from the cache afterwards.
- `route()` returns distance, duration and GeoJSON geometry for `FASTEST`.
- A small recording script the owner runs once (with approval) that writes sanitised responses to `apps/api/tests/fixtures/ors/` — no key, no auth headers, no account data.
- Config: `ORS_API_KEY`, `ORS_BASE_URL`.
EOF
  txt T_OUT <<'EOF'
- `AVOID_HIGHWAYS` / alternatives (FEAT-008, P1); self-hosted routing (post-MVP).
- Any ORS call from tests or CI.
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/routing/{ors.py,cache.py}` — new; `routing/composite.py` — changed
- `scripts/record_ors_fixtures.py` (*suggested*) — new
- `apps/api/tests/contract/test_ors_adapter.py`, `apps/api/tests/db/test_routing_cache.py`, `apps/api/tests/fixtures/ors/*.json` — new
- `apps/api/.env.example` (`ORS_BASE_URL`) — changed
EOF
  txt T_TESTS <<'EOF'
- `tests/contract/test_ors_adapter.py` — recorded matrix and directions responses parse into correct distances, durations (× factor) and geometry; a recorded rate-limit response → retry, then fallback. → AC-04
- `tests/db/test_routing_cache.py` — a stored response is served for the same points (also with coordinates differing beyond 5 decimals) and no HTTP call is made. → AC-05
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/contract/test_ors_adapter.py tests/db/test_routing_cache.py -q && make check && make test-db
gitleaks detect --no-git --source tests/fixtures/ors   # fixtures contain no key
```
EOF
  txt T_TIPS <<'EOF'
- Verify the ORS request and response shapes against the official ORS documentation and the recordings — OQ-004-03 forbids writing the adapter from memory.
- Never log the key, the full URL with the key, or request headers; mask them in exceptions too.
- Treat "fewer rows than requested" or a non-routable point as an ORS failure → fallback (§8).
- A transport stub in tests makes "no network in CI" structural.
EOF
  txt T_DECISIONS <<'EOF'
- 2026-11-11: the owner gets an ORS key (O-5); this slice waits for the key and the approved recording.
- OQ-004-03 (accepted): record real responses as fixtures during implementation.
EOF
}
register s_004_2

s_004_3() {
  I_ID="004/3"; I_FEAT="004"; I_TITLE="Optimisation jobs: create with idempotency, in-process worker, result storage, recovery, limits"
  I_AREA="backend"; I_SIZE="L"; I_DAY="2026-11-11"; I_CATCHUP="2026-11-13"
  I_ACS="09 10 11 13 14 15"; I_DEPS="003/6 004/1 002/5"
  I_GATES="make check, uv run pytest tests/api/test_jobs.py, uv run pytest -m integration tests/integration/test_worker.py, make openapi"
  I_LOCK="\`contracts/openapi.json\`, \`apps/api/.env.example\` (worker settings)"
  I_BRANCH="feat/FEAT-004-jobs-worker"; I_REQS="REQ-009, REQ-010, NFR-011"; I_ADRS="0008"; I_SCOPE_TAG="jobs"
  txt T_GOAL <<'EOF'
A dispatcher (or an agent tool) can request a driver or fleet optimisation and get a job back at once; one worker inside the API process runs the pure engine in a separate process on an immutable snapshot, stores immutable plans and survives restarts.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-004-routing-and-jobs.md` §4.2 FR-8 … FR-14, §4.3 (storage parts of FR-11), §6.1 (`JobCreate`, `Job`, `JobResult` …), §6.3 (tables), §6.4 (codes), §6.5 (configuration), §8 (edge cases), §10 rows 09–15
- `docs/adr/ADR-0008-async-processing.md`, `DEVELOPMENT.md` §4.6 (idempotency)
- `context.md` → Selected Technology Stack (jobs row), Known Risks (SQLite write concurrency)
EOF
  txt T_SCOPE <<'EOF'
- `POST /optimization-jobs` (FR-8): validate `JobCreate` (`scope = driver` needs exactly one id; unknown driver/offer id → `404`), build the snapshot (drivers with latest states, vehicles, cost profiles, offers with versions, parameters, `CO2_FACTOR_KG_PER_L`, reference time from the `Clock`), store it in `optimization_jobs.request` with `input_sha256`, status `queued`, return `202` + `Location`.
- `Idempotency-Key` (FR-9): same key + same body → same job (`202`); same key + different body → `409 IDEMPOTENCY_KEY_REUSED`.
- `GET /optimization-jobs/{id}`.
- Worker (FR-10): an `asyncio` task in the lifespan polls `queued` jobs oldest first, one at a time; `running` → resolve the matrix through `CompositeRoutingProvider` → `optimize(snapshot)` in `ProcessPoolExecutor(max_workers=1)` → heartbeat and `progress` while waiting → store result → `succeeded`; an engine exception → `failed` with `error {code, message}`.
- Result storage (FR-11) in one transaction: `route_plans` + `route_stops` for every returned plan (per-driver top-K per objective and both baselines) and the result document (fleet solutions referencing plan ids, rejections, warnings, stats).
- Recovery (FR-12): on start, a `running` job with a heartbeat older than 60 s is re-queued if `attempts < 2`, else `failed` with `WORKER_RESTARTED`.
- Logging (FR-13): every job log line carries `job_id`; the creating request also `request_id`.
- Limit (FR-14): ≤ 3 queued or running jobs per user, else `429 RATE_LIMITED`.
EOF
  txt T_OUT <<'EOF'
- `GET …/result` and `GET /route-plans/{id}` (004/4); assignments (004/5); job cancellation endpoints (not in the spec).
- A separate worker process or container, `SKIP LOCKED`, queue brokers (post-MVP; Redis/Celery forbidden).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/jobs/{api,service,domain,repository}/**`, `apps/api/src/routepilot/optimization/jobs/worker.py` — new
- `apps/api/src/routepilot/main.py` (worker start in lifespan, recovery) — changed
- `apps/api/tests/api/test_jobs.py`, `apps/api/tests/integration/test_worker.py` — new
- `contracts/openapi.json` — regenerated
EOF
  txt T_IFACE <<'EOF'
```text
JobCreate  { scope ("driver"|"fleet"), driverIds[] (exactly 1 for "driver"; empty = all active drivers for "fleet"),
             offerIds?[] (restrict the pool), objectives?[] (subset of "profit","fastest","fuel"; default all three),
             params? { horizonDays?, maxOffersPerPlan?, topKPerDriver? } }
Job        { id, status ("queued"|"running"|"succeeded"|"failed"|"cancelled"), scope, objectives[],
             progress { phase ("queued"|"routing"|"search"|"assignment"|"saving"), driversDone, driversTotal },
             stats? { nodes, truncated, poolTruncated, runtimeMs }, error? { code, message },
             requestedBy, createdAt, startedAt?, finishedAt? }
```
```python
class JobService:                       # reused by the agent tools optimize_driver / optimize_fleet (FEAT-006)
    def create(self, request: JobCreate, requested_by: UUID, idempotency_key: str | None) -> Job: ...
    def get(self, job_id: UUID) -> Job: ...
```
Configuration: `WORKER_POLL_INTERVAL_MS` (500), `JOB_HEARTBEAT_STALE_S` (60), engine parameters of FEAT-003.
EOF
  txt T_TESTS <<'EOF'
- `tests/api/test_jobs.py` — fleet job `202` + `Location`, `status = queued`, all three objectives; `scope = driver` with two ids → `422`; unknown driver → `404` → AC-09; idempotent repeat with the same key → same job, one row; different body → `409 IDEMPOTENCY_KEY_REUSED` → AC-10; queued/running → `GET …/result` gives `409 JOB_NOT_FINISHED`, failed → `404` and `error.code` visible → AC-13 (the result endpoint stub returns these codes; the success body is 004/4).
- `tests/integration/test_worker.py` — seeded data, no keys: `queued → running → succeeded`, `driversDone = driversTotal`, `stats` set, every log line has `job_id` → AC-11; stale `running` with `attempts = 1` re-queued and completes, with `attempts = 2` → `failed WORKER_RESTARTED` → AC-14; two queued jobs run one after another and `GET /health` answers within 200 ms meanwhile → AC-15.
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/api/test_jobs.py -q && uv run pytest -m integration tests/integration/test_worker.py -q
make check && make openapi
```
EOF
  txt T_TIPS <<'EOF'
- AC-13 needs the `…/result` route to answer `409`/`404` for unfinished or failed jobs; add that minimal route here so AC-13 is testable, and let 004/4 fill the success body.
- Use a synchronous test worker for API tests and the real worker only in the integration tests (test plan of §10).
- The snapshot must contain offer versions: an assignment later compares them (FR-16).
- Keep transactions short; the CPU work happens outside any DB transaction.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-004-06 (accepted): the UI polls `GET /optimization-jobs/{id}` every second; SSE is used only for agent runs.
EOF
}
register s_004_3

s_004_4() {
  I_ID="004/4"; I_FEAT="004"; I_TITLE="Job results and route plans: GET …/result, GET /route-plans/{id} with geometry, immutability"
  I_AREA="backend"; I_SIZE="M"; I_DAY="2026-11-11"; I_CATCHUP="2026-11-13"
  I_ACS="12 16 17"; I_DEPS="004/3"
  I_GATES="make check, uv run pytest tests/api/test_route_plans.py, make test-db, make openapi"
  I_LOCK="\`contracts/openapi.json\`"
  I_BRANCH="feat/FEAT-004-results-plans"; I_REQS="REQ-009, REQ-031"; I_ADRS="0004 0005"; I_SCOPE_TAG="jobs"
  txt T_GOAL <<'EOF'
The UI and the agents can read a finished optimisation: fleet solutions per objective, per-driver plan summaries, both baselines and the rejection list, and every plan in full detail with stops, load, counters, cost breakdown with provenance, fuel, CO₂, warnings, geometry and the legal notice.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-004-routing-and-jobs.md` §4.3 FR-15, §6.1 (`JobResult`, `FleetSolution`, `PlanSummary`, `RoutePlan`, `disclaimer`), §8 (haversine geometry), §10 rows 12, 16, 17
- `context.md` → Core Domain Rule 15 (mandatory notice — exact text)
EOF
  txt T_SCOPE <<'EOF'
- `GET /optimization-jobs/{id}/result` → `200 JobResult` for a succeeded job (fleet solutions, per-driver summaries, baselines, rejections, warnings, stats, `disclaimer`); every `routePlanId` in it is readable.
- `GET /route-plans/{id}` → `200 RoutePlan` with ordered stops (times, load after each stop, counters), cost breakdown with parameter provenance, `fuelL`, `co2Kg`, warnings, `disclaimer`; `geometry` computed on first request through `route()` and cached (straight lines + `approximate` for haversine).
- Mapping between engine `RoutePlan` and the stored rows (metres, millilitres, grams, minor units) and back to the API shape.
- No API method can modify a plan; plans and snapshots stay unchanged after drivers, offers or profiles change.
EOF
  txt T_OUT <<'EOF'
- Assignments (004/5); explanations (006/4); road alternatives (FEAT-008).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/jobs/{api,service}/**` (results, plans) — changed or new
- `apps/api/tests/api/test_route_plans.py`, `apps/api/tests/db/test_plan_immutability.py` — new
- `contracts/openapi.json` — regenerated
EOF
  txt T_IFACE <<'EOF'
```text
JobResult     { jobId, fleet { profit?, fastest?, fuel? : FleetSolution }, perDriver [ { driverId, plans { <objective>: PlanSummary[] } } ],
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
class PlanService:   # reused by agent tools get_plan / compare_plans / check_plan_rules (FEAT-006)
    def get(self, plan_id: UUID) -> RoutePlan: ...
```
`disclaimer` = the fixed notice of Core Domain Rule 15.
EOF
  txt T_TESTS <<'EOF'
- `tests/api/test_route_plans.py` — a succeeded job's result has fleet solutions for the requested objectives, per-driver summaries, both baselines, rejections and `disclaimer`; every `routePlanId` is readable → AC-12; a stored plan has ordered stops with times, load and counters, breakdown with provenance, `fuelL`, `co2Kg`, warnings, `disclaimer`; unknown id `404` → AC-17.
- `tests/db/test_plan_immutability.py` — after changing a driver, an offer and the cost profile, the stored snapshot, plans and stops are unchanged; no route modifies a plan. → AC-16
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/api/test_route_plans.py tests/db/test_plan_immutability.py -q && make check && make test-db && make openapi
```
EOF
  txt T_TIPS <<'EOF'
- Quote the disclaimer from one constant; the UI shows a translated version (FEAT-005).
- Converting millilitres/grams back to litres/kg must not change the values the engine produced (P6, P17 reconstruct from the stored breakdown).
EOF
}
register s_004_4

s_004_5() {
  I_ID="004/5"; I_FEAT="004"; I_TITLE="Assignments: POST/DELETE /assignments, DriverUsageChecker, auth test over FEAT-004 endpoints"
  I_AREA="backend"; I_SIZE="M"; I_DAY="2026-11-11"; I_CATCHUP="2026-11-13"
  I_ACS="18 19 20"; I_DEPS="004/4"
  I_GATES="make check, uv run pytest tests/api/test_assignments.py tests/security, make openapi"
  I_LOCK="\`contracts/openapi.json\`"
  I_BRANCH="feat/FEAT-004-assignments"; I_REQS="REQ-017"; I_ADRS="0004 0012"; I_SCOPE_TAG="jobs"
  txt T_GOAL <<'EOF'
A human approves a plan by assigning it: one transaction checks that every offer is still open and unchanged and that the driver is free, then marks the offers assigned and records who approved. The same service later serves the agents' only write tool.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-004-routing-and-jobs.md` §4.3 FR-16 … FR-19, §6.1 (assignments endpoints, `Assignment`), §6.4 (`PLAN_NOT_ASSIGNABLE`), §8 (edited offer, two tabs), §11 OQ-004-04, OQ-004-05
- `specs/FEAT-001-domain-sqlite-crud-auth.md` §6.3 (`DriverUsageChecker`)
- `context.md` → Glossary (Assignment), AI Architecture Rule 3 (why the same service backs `assign_plan`)
EOF
  txt T_SCOPE <<'EOF'
- `GET /assignments` (filters `driverId`, `status`, cursor), `POST /assignments {routePlanId}`, `GET /assignments/{id}`, `DELETE /assignments/{id}`.
- `AssignmentService.assign(plan_id, approved_by, agent_run_id=None)` (FR-16, FR-18): plan exists and is `optimized` (baselines refused); every offer `open` and at the snapshot version; driver exists, not deleted, no active assignment; any failure → `409 PLAN_NOT_ASSIGNABLE` with `errors[]` naming the reason; success → `assignments` row (`active`, `approved_by`, `approved_at`), offers `assigned`, audit event, `201` + `Location`.
- Cancel (FR-17): `status = cancelled`, offers back to `open`, audit, `204`; second cancel → `404`.
- `DriverUsageChecker` implementation (FR-19) wired in `main.py` instead of the stub: `active` / `historical` / `none`.
- Security test over every endpoint of FEAT-004 §6.1: anonymous `401`, missing CSRF `403`, the fourth simultaneous job of one user `429 RATE_LIMITED`.
EOF
  txt T_OUT <<'EOF'
- Updating `DriverState` after an assignment (OQ-004-05: no in the MVP); the agent approval flow (006/3).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/jobs/{api,service,repository}/**` (assignments, usage checker) — new or changed
- `apps/api/src/routepilot/main.py` (inject the real checker) — changed
- `apps/api/tests/api/test_assignments.py`, `apps/api/tests/security/test_jobs_auth.py` — new
- `contracts/openapi.json` — regenerated
EOF
  txt T_IFACE <<'EOF'
```text
Assignment { id, routePlanId, driverId, status ("active"|"cancelled"), approvedBy, approvedAt, agentRunId?, createdAt }
```
```python
class AssignmentService:
    def assign(self, plan_id: UUID, approved_by: UUID, agent_run_id: UUID | None = None) -> Assignment: ...
    def cancel(self, assignment_id: UUID, by: UUID) -> None: ...
```
EOF
  txt T_TESTS <<'EOF'
- `tests/api/test_assignments.py` — assign an optimised plan with open offers → `201` + `Location`, offers `assigned`, audit row, checker `active`; the same plan again or another plan sharing an offer → `409 PLAN_NOT_ASSIGNABLE`; a baseline plan → `409` → AC-18; cancel → `204`, `cancelled`, offers `open`, checker `historical`, second cancel `404` → AC-19.
- `tests/security/test_jobs_auth.py` — every endpoint of §6.1: anonymous `401`; state-changing without CSRF `403`; fourth simultaneous job of one user `429 RATE_LIMITED`. → AC-20
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/api/test_assignments.py tests/security/test_jobs_auth.py -q && make check && make openapi
```
EOF
  txt T_TIPS <<'EOF'
- Do all checks and writes inside one transaction so two tabs assigning conflicting plans give one `201` and one `409` (§8).
- "One active assignment per driver" is enforced in the service (portable to PostgreSQL), not by a SQLite partial index.
- Add the new endpoints to the permission-matrix test of 001/7.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-004-04 (accepted): the HTTP `POST /assignments` exists next to the agent flow; both call the same service.
- OQ-004-05 (accepted): no new `DriverState` after an assignment in the MVP.
EOF
}
register s_004_5
