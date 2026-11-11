# FEAT-003 — Optimizer and working time (pure core). Sourced by scripts/create_github_issues.sh.
# shellcheck shell=bash disable=SC2034

s_003_1() {
  I_ID="003/1"; I_FEAT="003"; I_TITLE="compliance: DriverRules port with pl_domestic_employee_v1 and eu561_van_international_v1"
  I_AREA="engine"; I_SIZE="L"; I_DAY="2026-11-11"; I_CATCHUP="2026-11-12"
  I_ACS="14 15 16 17 18"; I_DEPS="001/1"
  I_GATES="make check, make test-props"
  I_LOCK="—"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-003-driver-rules"; I_REQS="REQ-012"; I_ADRS="0011"; I_SCOPE_TAG="compliance"
  txt T_GOAL <<'EOF'
A pure, deterministic model of the two working-time profiles that inserts breaks and daily rests exactly where the simplified rules require them and reports infeasibility when a weekly limit is reached. Every schedule of the engine, the validators and the oracles is built on it.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-003-optimizer-and-working-time.md` §4.1 (port, FR-1 profile choice, FR-2 limits table, FR-3 … FR-9), §8 (break and rest at the same minute, `work_today > 0` without rest end), §11 OQ-003-04, OQ-003-06, OQ-003-07, OQ-003-08
- `specs/golden/README.md` conventions G4 … G8 (PL and 561 breaks, forward schedule, waiting, start deferral)
- `context.md` → Core Domain Rules 6–10, Glossary (DriverState, Legal profile, Working time)
- `docs/adr/ADR-0011-driver-working-time.md`, `docs/report.md` §20.1
EOF
  txt T_SCOPE <<'EOF'
- `DriverRules` port and the engine's rules state (`t`, `work_today`, `drive_today`, `work_since_break`, `drive_since_break`, `breaks_today`, `work_week`, `drive_week`, `drive_prev_week`, `day_start_at`, `sleeper_cab`); `Outcome = Ok(state, elapsed_min, events) | Infeasible(code)`; `Remaining`.
- Profile choice (FR-1): more than one country among start position, stops and `END` base ⇒ `eu561_van_international_v1`; unresolved start country counts as foreign.
- Limits of FR-2 for both profiles (work without break 360; 561 driving without break 270; breaks 30 (+15 top-up) / 45; PL daily work 720 (parameter `max_daily_work_min`); 561 daily driving 540; day span 780; daily rest 660; weekly work 3 600; 561 weekly driving 3 360 and two-week 5 400).
- `advance_drive` (FR-3, splittable), `advance_work` (FR-4, atomic service, break or rest before it), `advance_wait` (FR-7: ≥ 660 min = one rest; otherwise work, splittable), breaks (FR-5), daily rest (FR-6), initial state (FR-8), week boundary Monday 00:00 in the base time zone with `drive_prev_week` roll-over, no weekly rest inside a plan (FR-9).
EOF
  txt T_OUT <<'EOF'
- Split breaks, reduced or split rests, 10-hour driving extensions, night work (P1, Q14), weekly-rest compensation, double crew, ferry/train, posting rules.
- Schedule construction over offers (003/5) and validators (003/4).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/compliance/{__init__.py,ports.py,state.py,profiles.py,pl_domestic.py,eu561.py}` (*suggested* split) — new
- `apps/api/tests/unit/compliance/{test_profile_choice.py,test_pl_domestic.py,test_eu561.py,test_weekly.py,test_wait_and_service.py}` — new
- `apps/api/tests/factories_rules.py` (*suggested* state factories) — new
EOF
  txt T_IFACE <<'EOF'
```python
class DriverRules(Protocol):               # compliance/ports.py — pure implementations
    profile_id: str                        # "pl_domestic_employee_v1" | "eu561_van_international_v1"
    def advance_drive(self, s: DriverState, minutes: int) -> Outcome: ...
    def advance_work(self, s: DriverState, minutes: int) -> Outcome: ...
    def advance_wait(self, s: DriverState, minutes: int) -> Outcome: ...
    def remaining(self, s: DriverState) -> Remaining: ...

Outcome = Ok | Infeasible
@dataclass(frozen=True)
class Ok:          state: DriverState; elapsed_min: int; events: tuple[RuleEvent, ...]   # BREAK / DAILY_REST with start, length, reason
@dataclass(frozen=True)
class Infeasible:  code: str                                                             # e.g. "WEEKLY_LIMIT_REACHED"

def choose_profile(countries: set[str] | None, home_country: str) -> DriverRules: ...   # suggested helper for FR-1
```
EOF
  txt T_TESTS <<'EOF'
- `test_profile_choice.py` — (a) all Poland → PL, (b) one delivery in Germany → 561, (c) domestic stops but start in Czechia → 561. → AC-14
- `test_pl_domestic.py` — fresh PL state: `advance_work(30)` then `advance_drive(568)`: 30-min break after 330 min of driving, 15-min break after 180 more, elapsed 613, `work_today = 598`; continuing to 720 → a 660-min `DAILY_REST` before the next driving minute, counters reset. → AC-15
- `test_eu561.py` — `advance_drive(288)` → one 45-min break after 270, elapsed 333; `drive_today = 499`, `drive_since_break = 259`, `advance_drive(126)` → break after 11, rest after 30 more; `work_since_break = 331`, `advance_drive(60)` → 45-min break after 29. → AC-16
- `test_weekly.py` — `work_week = 3 590` + `advance_drive(30)` → `Infeasible(WEEKLY_LIMIT_REACHED)` in both profiles; 561 with two-week 5 390 → same; crossing Monday 00:00 base time rolls `drive_prev_week`. → AC-17
- `test_wait_and_service.py` — `work_since_break = 350` + `advance_work(30)` → break first, service not split; wait 700 → one `DAILY_REST` of 700; wait 120 → all work counters + 120; first stop needing 45 min of waiting → departure 45 min after `available_from`, `wait_min = 0`. → AC-18
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/unit/compliance -q
uv run lint-imports   # compliance imports only shared
make check && make test-props
```
EOF
  txt T_TIPS <<'EOF'
- "A rest and a break due at the same minute → only the rest" (FR-3) is easy to get wrong; write that test first.
- The start deferral of AC-18 is a schedule-builder rule (FR-20); implement the rules-side behaviour here and keep the test where the spec's test plan puts it, reusing it from 003/5.
- No clock, no IO, no environment: the time zone of the base is passed in (an IANA name), and `zoneinfo` is pure enough for week boundaries.
- Changes to legal rules need human approval — if a rule of FR-2 looks wrong or unclear, stop and ask; never "fix" it silently.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-003-04 (option a, accepted): PL break 30 min at the 6-hour mark + 15-min top-up when daily work passes 9 h.
- OQ-003-06 / OQ-003-07 / OQ-003-08 (accepted): waiting and deferral as FR-4/FR-7/FR-20; `day_start_at` = first activity after a rest for both profiles; week boundary Monday 00:00 in the home-base time zone.
EOF
}
register s_003_1

s_003_2() {
  I_ID="003/2"; I_FEAT="003"; I_TITLE="Cost model: fuel with speed curve, CO₂, tolls, driver cost, per diems, accommodation, vehicle cost"
  I_AREA="engine"; I_SIZE="M"; I_DAY="2026-11-11"; I_CATCHUP="2026-11-12"
  I_ACS="19 20"; I_DEPS="001/1"
  I_GATES="make check, make test-props"
  I_LOCK="—"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-003-cost-model"; I_REQS="REQ-009, REQ-031"; I_ADRS="0004 0010"; I_SCOPE_TAG="engine"
  txt T_GOAL <<'EOF'
An exact, integer-money cost model whose every component can be recomputed from a plan's stops: fuel with load and speed, CO₂ from fuel, tolls, driver cost, per diems under the Act, accommodation and vehicle cost — with every assumption labelled.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-003-optimizer-and-working-time.md` §4.2 FR-10 … FR-14, §8 (PLN revenue, 0-km legs), §11 OQ-003-02, OQ-003-03, OQ-003-05, OQ-003-12, OQ-003-15
- `specs/golden/README.md` conventions (rounding, G9 per diem, `GOLD-CP-1` cost profile)
- `context.md` → Core Domain Rules 1, 11, 12, 17
- `docs/report.md` §19.1 (formulas), §17.4 (parameters)
EOF
  txt T_SCOPE <<'EOF'
- Fuel (FR-10): per leg with `drive_min > 0`, `v = distance_km × 60 / drive_min`; `L100 = (c_empty + (c_full − c_empty) × load_kg / payload_kg) × speed_curve(v)`; `leg_fuel_l = round_half_up(distance_km × L100 / 100, 3)`; curve `VAN_DEFAULT_V1` (50 → 1.10, 70 → 0.95, 90 → 1.00, 110 → 1.18, 130 → 1.35), linear between points, constant outside.
- CO₂ (FR-11): `co2_kg = round_half_up(fuel_l × CO2_FACTOR_KG_PER_L, 2)`, factor from the snapshot (default 2.6).
- Components (FR-12), each rounded half-up once: fuel cost, tolls by destination country of each leg (vignette countries 0 + `VIGNETTE_ASSUMED_ANNUAL`), driver cost on drive + service + wait minutes, per diem (0 for any plan with a stop abroad; domestic multiplier rules of Art. 21a on `T = finish_at − departure`), accommodation per `DAILY_REST` away from base without sleeper cab, vehicle cost per km.
- Profit and margin (FR-13); revenue in another currency converted once with `fx_rates`, half-up; the breakdown stored in the plan's `calculation` block with parameter provenance (FR-14).
EOF
  txt T_OUT <<'EOF'
- Toll attribution by route geometry (post-MVP; OQ-003-12 charges the whole leg at the destination country).
- Choosing roads (FEAT-008, P1).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/{cost_model.py,fuel.py}` (*suggested*) — new
- `apps/api/tests/unit/engine/{test_cost_model.py,test_fuel.py}`, `apps/api/tests/fixtures/engine/gold_cp_1.py` (*suggested*) — new
EOF
  txt T_IFACE <<'EOF'
```python
def speed_curve(name: str, v_kmh: Decimal) -> Decimal: ...                      # "VAN_DEFAULT_V1"
def leg_fuel_l(distance_km: Decimal, drive_min: int, load_kg: int, vehicle: VehicleSpec) -> Decimal: ...
class CostModel:                                                                 # shared by search, validators, baselines, oracles
    def breakdown(self, plan_timeline: Timeline, profile: CostProfileSpec, vehicle: VehicleSpec) -> CostBreakdown: ...
```
(*suggested* names; the formulas and rounding points of FR-10 … FR-13 are binding.)
EOF
  txt T_TESTS <<'EOF'
- `tests/unit/engine/test_cost_model.py` — a plan with known legs, work minutes, one foreign service date and one rest away from base without sleeper cab: each component equals the hand calculation in minor units with `GOLD-CP-1`; changing one "assumption" parameter changes only its component. → AC-19
- `tests/unit/engine/test_fuel.py` — `speed_curve(60) = 1.025`, `(40) = 1.10`, `(140) = 1.35`; `L100` strictly grows with `load_kg`; a 0-minute leg burns 0 l; 76.601 l × 2.6 = 199.16 kg. → AC-20
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/unit/engine/test_cost_model.py tests/unit/engine/test_fuel.py -q && make check
```
EOF
  txt T_TIPS <<'EOF'
- Use `Decimal` everywhere; never `float` for money or litres. Round half-up exactly at the points the spec names — the golden values depend on it.
- Per diems are 0 on international plans (Art. 26f) — owner decision of 2026-11-11 that replaced OQ-003-05's earlier default.
- `GOLD-CP-1` is defined in the golden conventions; copy it into a test fixture with the source file in the docstring.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-003-05 (owner, 2026-11-11): per diems follow the Act (Dz.U. 2026 poz. 477, Art. 21a and 26f) — see FR-12 and golden convention G9.
- OQ-003-12, OQ-003-15 (accepted): tolls charged at the destination country of the leg; accommodation for every daily rest away from base without sleeper cab, 0 with one.
EOF
}
register s_003_2

s_003_3() {
  I_ID="003/3"; I_FEAT="003"; I_TITLE="Engine snapshot and result models, prefilter with rejection codes, rejection report"
  I_AREA="engine"; I_SIZE="M"; I_DAY="2026-11-11"; I_CATCHUP="2026-11-12"
  I_ACS="21 22"; I_DEPS="003/1 003/2 002/1"
  I_GATES="make check, make test-props"
  I_LOCK="—"
  I_BRANCH="feat/FEAT-003-snapshot-prefilter"; I_REQS="REQ-009, REQ-014"; I_ADRS="0004 0014"; I_SCOPE_TAG="engine"
  txt T_GOAL <<'EOF'
The engine's pure input and output contract plus the first stage: every offer that cannot work for a driver leaves that driver's pool with exactly one stable reason code, and `optimize()` always returns a valid result — even when nothing is feasible.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-003-optimizer-and-working-time.md` §4.3 FR-15 … FR-19, §4.9 (engine interface and result), §8 (empty lists), §11 OQ-003-10, OQ-003-11
- `context.md` → Core Domain Rules 4–5, Optimization Engine Invariant 9, default parameters
- `docs/adr/ADR-0014-van-capacity.md`
EOF
  txt T_SCOPE <<'EOF'
- `EngineSnapshot` (reference time, parameters, objectives, `CO2_FACTOR_KG_PER_L`, drivers with home base, rules state, vehicle and cost profile, offers with stops and provenance, travel matrix with provider id and fallback flag, `solver_version`) and `EngineResult` (`per_driver`, `fleet`, `baselines`, `rejections`, `warnings`, `stats`) and `RoutePlan` (§4.9) as immutable value objects.
- Prefilter (FR-15) in the fixed order of the 12 checks with codes `OFFER_NOT_OPEN` … `PICKUP_WINDOW_UNREACHABLE`; the first failing check wins.
- Pallet equivalents (FR-16): EUR 1.0, half 0.5, industrial 1.5, unknown 1.0 + `PALLET_TYPE_UNKNOWN`; count by provenance (`source`/`user`/`generated_mock` as is, missing → `ceil(length × 2.4)` + `PALLETS_DERIVED`, `ai` → `max(derived, ai)` + flag, nothing → `MISSING_CAPACITY_DATA`).
- Pool size cut (FR-17) by `revenue / (deadhead_km + loaded_km)`, ties by id, `pool_truncated`.
- Rejection report (FR-19) with `stage = prefilter` entries; the `search` stage codes of FR-18 are produced in 003/5.
- `optimize(snapshot)` entry point that runs the prefilter and returns an `EngineResult` (search added in 003/5).
EOF
  txt T_OUT <<'EOF'
- Search, schedules and plans (003/5), validators (003/4), fleet assignment and baselines (003/6).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/{models.py,snapshot.py,prefilter.py,rejections.py,api.py}` (*suggested*) — new
- `apps/api/tests/unit/engine/{test_prefilter.py,test_empty_result.py}` — new
EOF
  txt T_IFACE <<'EOF'
```python
def optimize(snapshot: EngineSnapshot) -> EngineResult: ...      # pure; the only public entry point of the engine
```
Rejection entry: `{driver_id, offer_id, stage: "prefilter" | "search", code, detail}` — exactly one per (driver, offer) not in any returned plan of that driver.
EOF
  txt T_TESTS <<'EOF'
- `tests/unit/engine/test_prefilter.py` — one offer per row of the FR-15 table failing only that check → exactly that code; an offer failing checks 5 and 8 → `MISSING_REVENUE`; pallets with provenance `ai` = 3 and derived 5 → 5 equivalents. → AC-21
- `tests/unit/engine/test_empty_result.py` — a snapshot with no feasible offer for a driver → empty plan lists, a valid `EngineResult`, no exception, one rejection per offer with stage and code. → AC-22
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/unit/engine -q && uv run lint-imports && make check
```
EOF
  txt T_TIPS <<'EOF'
- Keep the models free of SQLAlchemy and Pydantic-IO concerns; plain frozen dataclasses (or Pydantic models without IO) are fine — FEAT-004 maps them to tables.
- The engine receives the travel matrix; it never imports `routing`.
- Sort inputs by id at the boundary so that the shuffled-input property (P7, 003/5) holds by construction.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-003-10, OQ-003-11 (accepted): pool ranking by revenue per km, ties by id; prefilter order and codes as FR-15 / FR-18 (FEAT-005 translates these codes).
EOF
}
register s_003_3

s_003_4() {
  I_ID="003/4"; I_FEAT="003"; I_TITLE="RouteValidator and FleetValidator (independent of the search)"
  I_AREA="engine"; I_SIZE="M"; I_DAY="2026-11-11"; I_CATCHUP="2026-11-12"
  I_ACS="25"; I_DEPS="003/3"
  I_GATES="make check, make test-props"
  I_LOCK="—"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-003-validators"; I_REQS="REQ-012, NFR-003"; I_ADRS="0004"; I_SCOPE_TAG="engine"
  txt T_GOAL <<'EOF'
Two validators that re-check every engine result from scratch — replaying the recorded timeline against the rules and the matrix and recomputing all money — so that a plan breaking any invariant can never leave the engine.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-003-optimizer-and-working-time.md` §4.7 FR-32 … FR-34, §4.10 (invariants), §4.9 (`RoutePlan` stops)
- `context.md` → Optimization Engine Invariants (1–7, 12, 13, 14, 17) and the rule "Validators and search are separate implementations"
EOF
  txt T_SCOPE <<'EOF'
- `RouteValidator(snapshot, plan)` (FR-32): without calling the search or its schedule builder, re-checks invariants 1–7, 13, 14 and 17 — replays stops and inserted breaks/rests, compares every counter with the profile limits (through `DriverRules`), recomputes leg times from the matrix, the cost breakdown through `CostModel` and `co2_kg`.
- `FleetValidator(snapshot, solution, plans)` (FR-33): invariant 12 and that every referenced plan passed `RouteValidator`.
- `EngineInvariantError` (FR-34): raised when an engine result fails validation — the engine never returns such a plan.
- Distinct error codes per violated invariant (so AC-25 can tell mutations apart).
EOF
  txt T_OUT <<'EOF'
- The search itself (003/5). Any relaxation of a check to make a result pass is forbidden.
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/validators.py` — new
- `apps/api/tests/unit/engine/{test_route_validator.py,test_fleet_validator.py}`, `apps/api/tests/fixtures/engine/plan_mutators.py` (*suggested*) — new
EOF
  txt T_IFACE <<'EOF'
```python
class RouteValidator:
    def validate(self, snapshot: EngineSnapshot, plan: RoutePlan) -> ValidationReport: ...   # ok, violations[(invariant, code, message)]
class FleetValidator:
    def validate(self, snapshot: EngineSnapshot, solution: FleetSolution, plans: Mapping[PlanRef, RoutePlan]) -> ValidationReport: ...
class EngineInvariantError(RuntimeError): ...
```
(*suggested*; FEAT-006's `check_plan_rules` tool reports `violations[{invariant, message}]` from this report.)
EOF
  txt T_TESTS <<'EOF'
- `tests/unit/engine/test_route_validator.py` — a valid plan passes; each mutation is rejected with a distinct error: load above capacity, delivery before pickup, service start after window end, removed `BREAK`, changed profit, changed `co2_kg`, missing `END` with `home_by` set, PL profile on an international plan. → AC-25
- `tests/unit/engine/test_fleet_validator.py` — a fleet solution with a duplicated offer is rejected. → AC-25
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/unit/engine/test_route_validator.py tests/unit/engine/test_fleet_validator.py -q && make check
```
EOF
  txt T_TIPS <<'EOF'
- Shared with the search: data models, `CostModel`, `DriverRules` — nothing else. In particular, do not reuse the schedule builder.
- Build the valid fixture plan by hand from a golden case (for example GOLD-007) so the validator is tested before the search exists.
- Changes to validators need human approval; mention it in the PR.
EOF
}
register s_003_4

s_003_5() {
  I_ID="003/5"; I_FEAT="003"; I_TITLE="Per-driver Branch-and-Bound, objectives and tie-breakers, oracle and property tests P1–P9, P11"
  I_AREA="engine"; I_SIZE="L"; I_DAY="2026-11-11"; I_CATCHUP="2026-11-13"
  I_ACS="01 02 03 04 05 06 07 08 09 11 23 27"; I_DEPS="003/4"
  I_GATES="make check, make test-props (Hypothesis profile ci)"
  I_LOCK="—"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-003-branch-and-bound"; I_REQS="REQ-009, REQ-011, REQ-012, REQ-013, NFR-001, NFR-003"; I_ADRS="0004 0011"; I_SCOPE_TAG="engine"
  txt T_GOAL <<'EOF'
The heart of the product: for each driver, an exact and deterministic search over consolidated loads and order chains within the horizon that returns the top-K feasible plans per objective (`profit`, `fastest`, `fuel`), proven equal to a brute-force oracle on small instances and safe under every invariant.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-003-optimizer-and-working-time.md` §4.4 FR-20 … FR-26 (schedule construction, labels, moves, profile passes, bounds, budget, top-K), §4.5 FR-27, FR-28 (objectives, tie-breakers), §4.3 FR-18, FR-19 (search-stage rejections), §4.9 (plan warnings), §6 (test-only oracle, golden routing provider), §8 (edge cases), §10 (test plan, Hypothesis profiles)
- `specs/golden/README.md` G1–G3 (golden routing provider) and the other conventions
- `context.md` → Optimization Engine Invariants, default parameters, Core Domain Rule 13
- `docs/adr/ADR-0004-optimization-engine.md`
EOF
  txt T_SCOPE <<'EOF'
- Schedule construction (FR-20) used by search, baselines and oracles: drive → wait → window check → service → load update; start deferral; `END` at base before `home_by` when `home_by` ≤ horizon end.
- Labels and moves (FR-21, FR-22): `PICKUP` (first pickup within `max_first_deadhead_km`, capacity after it, ≤ `max_offers_per_plan`) and `DELIVERY`; a label is complete with nothing on board and ≥ 1 offer done.
- Domestic pass (PL) and international pass (561, only international plans), merged (FR-23).
- Admissible bounds for each objective (FR-24); deterministic expansion order; `node_budget_per_driver` and `wall_clock_safety_s` → `truncated` (FR-25).
- Top-K per objective with distinct offer sets, best sequence per set, thresholds `min_profit` / `min_margin_pct` (FR-26); lexicographic keys and tie-breakers (FR-27, FR-28).
- Search-stage rejection codes and `NOT_IN_TOP_K` (FR-18, FR-19); plan warnings (`LOADING_ORDER_NOT_MODELLED` always for curtain-siders, others when they apply).
- Every returned plan passes `RouteValidator`; otherwise `EngineInvariantError`.
- Test-only `optimization/engine/oracle.py` (brute force for N ≤ 5, K ≤ 3) and the golden routing provider fixture; Hypothesis strategies for small instances (1–3 drivers, 0–5 offers, cities from `cities.json`).
EOF
  txt T_OUT <<'EOF'
- Fleet assignment, `fastest`/`fuel` fleet solutions and baselines (003/6); golden tests (003/7); benchmark (003/8).
- Label dominance (P1), OR-Tools (post-MVP), road choice (FEAT-008).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/{schedule.py,search.py,objectives.py,bounds.py}` (*suggested*) — new
- `apps/api/src/routepilot/optimization/engine/oracle.py` — new (test-only; importing it outside `tests/` is forbidden)
- `apps/api/src/routepilot/optimization/engine/api.py` — changed (`optimize` runs the search)
- `apps/api/tests/props/{strategies.py,test_engine_invariants.py,test_rules_props.py}`, `apps/api/tests/fixtures/engine/golden_routing.py`, `apps/api/tests/unit/engine/{test_ranking.py,test_budget.py}` — new
EOF
  txt T_IFACE <<'EOF'
| Objective | Key (best first) |
|---|---|
| `profit` | larger `net_profit` → earlier `finish_at` → smaller `fuel_l` |
| `fastest` | earlier `finish_at` → larger `net_profit` |
| `fuel` | smaller `fuel_l` → larger `net_profit` |

Tie-breakers (FR-28): same offer set → action sequences compared position by position, `DELIVERY` before `PICKUP`, then smaller offer id; different sets → sorted tuple of offer ids. Defaults: `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`, `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`, `wall_clock_safety_s=30`.
EOF
  txt T_TESTS <<'EOF'
- `tests/props/test_engine_invariants.py` — P1 load within capacity → AC-01; P2 one pickup + one delivery in order, revenue = Σ prices → AC-02; P3 service inside windows → AC-03; P4 monotonic time and arrival arithmetic → AC-04; P5 independent replay within profile limits, multi-country ⇒ 561 → AC-05; P6 profit and CO₂ reconstruct exactly → AC-06; P7 identical results on rerun and on shuffled input (except `runtimeMs`) → AC-07; P8 distinct, sorted top-K; empty list + full rejection report when infeasible → AC-08; P9 equals `oracle.py` for N ≤ 5, K ≤ 3 per objective → AC-09; P11 `home_by` inside horizon ⇒ every plan ends at base in time → AC-11.
- `tests/unit/engine/test_ranking.py` — three equal-profit plans ordered by finish, then fuel; same set with equal keys → the `DELIVERY`-first order wins. → AC-23
- `tests/unit/engine/test_budget.py` — `node_budget_per_driver = 50` → `truncated = true`, every returned plan still valid, invariant-15 check skipped. → AC-27
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && HYPOTHESIS_PROFILE=ci uv run pytest tests/props tests/unit/engine -q
uv run lint-imports   # oracle imported only from tests/
make check && make test-props
```
EOF
  txt T_TIPS <<'EOF'
- Write the oracle first and keep it obviously correct (brute force over all pickup/delivery orders); then grow the B&B until P9 agrees.
- Bounds must be admissible — an over-optimistic profit bound is fine, an under-estimate is a bug that P9 will catch.
- A failing Hypothesis example is kept in the repository's Hypothesis database for regression; never lower the example count to make a run pass.
- If an invariant cannot be satisfied or a rule looks contradictory, stop and report (`blocked`) — do not weaken the validator.
- Watch the 400-line PR guideline: this slice is large; justify the size in the PR or split oracle/strategies into a preparatory PR inside this issue.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-003-01 … OQ-003-03 (accepted): fallback routing formula, speed-curve use and rounding points as specified; they drive every golden value.
- OQ-003-09 (accepted): `min_profit = 0`, `min_margin_pct = 0`.
- OQ-003-13 (accepted): `fastest` and `fuel` keep the definition of Core Domain Rule 13; the UI shows Δ profit next to each variant.
EOF
}
register s_003_5

s_003_6() {
  I_ID="003/6"; I_FEAT="003"; I_TITLE="Fleet assignment, fastest/fuel fleet solutions, baseline_single and baseline_greedy, fleet oracle"
  I_AREA="engine"; I_SIZE="L"; I_DAY="2026-11-11"; I_CATCHUP="2026-11-13"
  I_ACS="10 12 13 24 26"; I_DEPS="003/5"
  I_GATES="make check, make test-props"
  I_LOCK="—"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-003-fleet-assignment"; I_REQS="REQ-010, REQ-011, REQ-014"; I_ADRS="0004"; I_SCOPE_TAG="engine"
  txt T_GOAL <<'EOF'
Turn per-driver candidate plans into the best fleet solution per objective — no offer twice, at most one plan per driver — and prove its value against two simple baselines that a dispatcher would otherwise use.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-003-optimizer-and-working-time.md` §4.6 FR-29 … FR-31, §4.8 FR-35 … FR-37, §4.10 invariants 12, 15, 16, §11 OQ-003-14, OQ-003-16
- `specs/golden/GOLD-009.md` (exact assignment beats greedy)
- `context.md` → Core Domain Rule 14, Optimization Engine Invariants 12, 15, 16
EOF
  txt T_SCOPE <<'EOF'
- `profit`: maximise Σ `net_profit`; ties → smaller Σ finish offset → smaller Σ fuel → driver/plan ids (FR-29).
- `fastest` / `fuel`: candidates = union of the driver's top-K for that objective and for `profit`; every driver with a plan in the `profit` solution keeps a plan; minimise Σ (`finish_at` − reference time) or Σ `fuel_l`; ties → larger Σ profit → ids.
- Exact depth-first search over drivers ordered by candidate count with conflict pruning and the sum-of-best bound (FR-30); `FleetSolution {objective, assignments, totals}` (FR-31); `FleetValidator` on every solution.
- `baseline_single` (FR-35) and `baseline_greedy` (FR-36), returned as plans with `kind = baseline_single | baseline_greedy` that pass the validators (FR-37), with fleet totals.
- Test-only `fleet_oracle.py` (all combinations for ≤ 3 drivers × ≤ 4 plans).
EOF
  txt T_OUT <<'EOF'
- Persisting plans and solutions (004/3); the UI comparison (005/5, 005/6).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/{fleet.py,baselines.py}` (*suggested*) — new
- `apps/api/src/routepilot/optimization/engine/fleet_oracle.py` — new (test-only)
- `apps/api/tests/props/test_fleet_assignment.py`, `apps/api/tests/unit/engine/{test_fleet_variants.py,test_baselines.py}` — new
EOF
  txt T_TESTS <<'EOF'
- `tests/props/test_fleet_assignment.py` — P10 no offer twice, no driver twice, equal to `fleet_oracle.py` for ≤ 3 drivers × ≤ 4 plans → AC-10; P12 with `truncated = false` the `profit` fleet profit ≥ both baselines → AC-12; P13 rank 1 `fastest` finishes no later and rank 1 `fuel` burns no more than rank 1 `profit` per driver, and the fleet sums hold over the `profit` drivers → AC-13.
- `tests/unit/engine/test_fleet_variants.py` — a `profit` solution covering D1 and D2 → `fastest` and `fuel` both give plans to D1 and D2, minimise their sums over the union of candidates, never reuse an offer. → AC-24
- `tests/unit/engine/test_baselines.py` — a two-driver instance returns `baseline_single` and `baseline_greedy` built by FR-35/36, both valid, with totals. → AC-26
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && HYPOTHESIS_PROFILE=ci uv run pytest tests/props/test_fleet_assignment.py tests/unit/engine -q && make check && make test-props
```
EOF
  txt T_TIPS <<'EOF'
- The greedy baseline inserts into existing sequences at every position pair — use the same schedule builder as the search (FR-20) and the validators afterwards.
- Invariant 15 is checked only when `truncated = false`.
- GOLD-009 is the reference example of greedy losing to the exact assignment; use it as a unit fixture early.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-003-14 (accepted): `baseline_greedy` exactly as FR-36.
- OQ-003-16 (accepted): every driver of the `profit` solution keeps a plan in `fastest`/`fuel`; candidates are the union with the `profit` lists.
EOF
}
register s_003_6

s_003_7() {
  I_ID="003/7"; I_FEAT="003"; I_TITLE="Golden tests GOLD-001 … GOLD-010 through the production engine"
  I_AREA="engine"; I_SIZE="M"; I_DAY="2026-11-11"; I_CATCHUP="2026-11-13"
  I_ACS="30 31 32 33 34 35 36 37 38 39"; I_DEPS="003/6"
  I_GATES="make check, uv run pytest tests/golden"
  I_LOCK="🔒 golden values (\`specs/golden/*\`) — read only; any change needs the owner"; I_APPROVAL="yes"
  I_BRANCH="test/FEAT-003-golden"; I_REQS="REQ-009, REQ-012, REQ-013, REQ-014, NFR-003"; I_ADRS="0004 0011 0014"; I_SCOPE_TAG="test"
  txt T_GOAL <<'EOF'
The ten hand-checked scenarios run through the production engine with the golden routing provider and reproduce every asserted number exactly — the strongest evidence that the engine, the rules and the cost model mean what the specification says.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/golden/README.md` (conventions G1–G14 and the index) and every `specs/golden/GOLD-00N.md` §4 (assertions)
- `specs/FEAT-003-optimizer-and-working-time.md` §7 golden ACs, §10 (one fixture module per golden file, values copied with the file path in the docstring)
- `context.md` → Testing Standards (Golden row)
EOF
  txt T_SCOPE <<'EOF'
- One test module per golden case: `tests/golden/test_gold_001.py` … `test_gold_010.py`, each with a fixture module that copies the inputs (drivers, vehicles, offers, states, cost profile) from the `.md` file and names that file in its docstring.
- Every assertion of each case's §4 is a separate assert with a readable message.
- The golden routing provider (G1–G3) from 003/5 as the matrix source.
EOF
  txt T_OUT <<'EOF'
- Editing any golden value or convention. A mismatch is reported to the owner with both numbers and the suspected cause (engine bug vs. spec error); the test is never relaxed.
EOF
  txt T_FILES <<'EOF'
- `apps/api/tests/golden/{__init__.py,conftest.py,test_gold_001.py … test_gold_010.py}` — new
- `apps/api/tests/golden/fixtures/gold_001.py … gold_010.py` (*suggested*) — new
- `apps/api/src/routepilot/optimization/engine/**` — changed only to fix a defect a golden test exposes (with owner approval if it touches invariants, objectives, rules or validators)
EOF
  txt T_TESTS <<'EOF'
- `test_gold_001.py` … `test_gold_010.py` — every assertion of GOLD-00N §4 holds. → AC-30 … AC-39 (one AC per file, in order).
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/golden -q && make check
```
EOF
  txt T_TIPS <<'EOF'
- GOLD-001 returns five plans after the per-diem recalculation of 2026-11-11 — check the current file, not an older note.
- Money assertions are integers in minor units; litres compare as `Decimal` with the shown precision.
- If a golden number cannot be reached, collect the full timeline and breakdown for that case and put it in the `blocked` report — that is what the owner needs to decide.
EOF
}
register s_003_7

s_003_8() {
  I_ID="003/8"; I_FEAT="003"; I_TITLE="Engine purity contract and fleet benchmark (bench/fleet_5x60.py)"
  I_AREA="engine infra"; I_SIZE="S"; I_DAY="2026-11-11"; I_CATCHUP="2026-11-13"
  I_ACS="28 29"; I_DEPS="003/6"
  I_GATES="make check, make bench"
  I_LOCK="\`Makefile\` (\`bench\`)"
  I_BRANCH="test/FEAT-003-purity-bench"; I_REQS="NFR-002, NFR-013"; I_ADRS="0004"; I_SCOPE_TAG="bench"
  txt T_GOAL <<'EOF'
Lock in the engine's purity with an import contract and measure its real performance on a five-driver fleet with 60-offer pools, so that NFR-002 (p95 ≤ 15 s) is recorded as met or not met instead of assumed.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-003-optimizer-and-working-time.md` §5 (NFR-002 measure), §6 (test-only modules), §7 AC-28, AC-29
- `context.md` → Module Boundaries (`optimization.engine` row), Known Risks (engine performance), Delivery Deadline fallback (horizon 3 days, ≤ 4 offers)
EOF
  txt T_SCOPE <<'EOF'
- import-linter contracts: `optimization.engine` and `compliance` import no FastAPI, SQLAlchemy, httpx, `os.environ`, `routing` adapters or `agents`; `oracle.py` and `fleet_oracle.py` are imported only from `tests/`.
- `bench/fleet_5x60.py` (pytest marker `bench`, not in `ci-fast`): 20 runs with fixed seeds on generated instances (5 drivers, pools of 60 offers, 5-day horizon), prints p50/p95 runtime, node counts and `truncated` flags, writes them to `bench/results/`, states whether p95 ≤ 15 s.
- `make bench` target.
EOF
  txt T_OUT <<'EOF'
- Performance tuning beyond pruning (label dominance is P1); weakening constraints to get faster is forbidden.
EOF
  txt T_FILES <<'EOF'
- `apps/api/pyproject.toml` (import-linter contracts, `bench` marker) — changed
- `bench/fleet_5x60.py`, `bench/README.md` — new; `bench/results/` — generated
- `apps/api/tests/unit/test_import_contracts.py` — changed
- `Makefile` — changed
EOF
  txt T_TESTS <<'EOF'
- `tests/unit/test_import_contracts.py` — the engine/compliance purity contracts and the oracle rule are present and `lint-imports` passes. → AC-28
- `bench/fleet_5x60.py` — run 20 times with fixed seeds; output and `bench/results/` file contain p50/p95, nodes, `truncated`, and the met/not-met line. → AC-29
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run lint-imports && uv run pytest -m bench ../../bench/fleet_5x60.py -q -s
make bench
```
EOF
  txt T_TIPS <<'EOF'
- Whether `bench/results/` is committed is not fixed by the spec — ask the owner (machine-specific timings may not belong in git); `docs/metrics.md` (007/5) is the committed summary.
- If p95 > 15 s, report it honestly with the numbers and propose the fallback parameters of the day plan; do not change defaults silently.
EOF
}
register s_003_8
