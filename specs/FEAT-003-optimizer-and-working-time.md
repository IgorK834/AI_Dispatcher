---
id: FEAT-003
title: Optimizer engine and driver working-time rules
status: approved
owner: project owner
requirements: [REQ-009, REQ-010, REQ-011, REQ-012, REQ-013, REQ-014, REQ-031, NFR-001, NFR-002, NFR-003, NFR-013]
adrs: [ADR-0004, ADR-0010, ADR-0011, ADR-0014]
modules: [compliance, optimization.engine, bench]
revision: 1
---

# FEAT-003: Optimizer engine and driver working-time rules

Priority: **P0**. Nothing in this specification is implemented yet.

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Goal

A pure, deterministic engine that, for a snapshot of drivers, vans, offers, costs and a travel matrix, returns the best plans per driver and per objective (`profit`, `fastest`, `fuel`), an exact fleet assignment, baselines for comparison and a rejection report — with every plan checked by independent validators and every schedule built through the `DriverRules` port.

## 2. Business context

This is the core of the product's credibility: agents and the UI only present what this engine computes ([`context.md`](../context.md) → Product Mission). Working time decides whether a van can take a load at all (report §1, fact 2). Background: [`docs/report.md`](../docs/report.md) §18 (algorithm, plain-language description in §18.4), §19 (objective and constraints), §20 (working time).

## 3. Scope / Out of scope

**In scope:** `compliance` (port `DriverRules`, profiles `pl_domestic_employee_v1` and `eu561_van_international_v1`); `optimization.engine` (snapshot models, cost model with fuel and CO₂, prefilter, per-driver Branch-and-Bound, fleet assignment, objectives, `RouteValidator`, `FleetValidator`, baselines, rejection report); test oracles; property tests P1–P13; golden cases GOLD-001 … GOLD-010; the benchmark.

**Out of scope:** any IO — database, HTTP, environment, system clock (the engine receives a snapshot; jobs and persistence are FEAT-004); road choice between alternatives and risk rating (FEAT-008, P1); split breaks, reduced or split rests, 10-hour driving extensions, night work, weekly-rest compensation, double crew, ferry/train, posting rules (outside the MVP, report §20.2); label dominance (P1); 2D pallet geometry (P2); OR-Tools (post-MVP).

## 4. Functional requirements

### 4.1 Driver working-time rules (`compliance`)

**Port** (pure; `context.md` → External Integration Contracts):

```python
class DriverRules(Protocol):
    profile_id: str        # "pl_domestic_employee_v1" | "eu561_van_international_v1"
    def advance_drive(self, s: DriverState, minutes: int) -> Outcome: ...
    def advance_work(self, s: DriverState, minutes: int) -> Outcome: ...
    def advance_wait(self, s: DriverState, minutes: int) -> Outcome: ...
    def remaining(self, s: DriverState) -> Remaining: ...
```

`Outcome` = `Ok(state, elapsed_min, events)` or `Infeasible(code)`. `events` are the inserted `BREAK` / `DAILY_REST` records with start, length and reason. `DriverState` here is the engine's rules state: clock `t`, `work_today`, `drive_today`, `work_since_break`, `drive_since_break`, `breaks_today`, `work_week`, `drive_week`, `drive_prev_week`, `day_start_at` (may be unset), `sleeper_cab`. `Remaining` reports minutes left before each limit. Implementations never read a clock and never do IO.

**FR-1 Profile choice.** A plan is *international* if the set of countries of its start position, all its pickup and delivery stops and (when present) its `END` base has more than one element. International ⇒ the whole plan uses `eu561_van_international_v1`; otherwise `pl_domestic_employee_v1` (Core Domain Rule 6). A start position whose country cannot be resolved counts as foreign.

**FR-2 Limits.**

| Limit (minutes) | `pl_domestic_employee_v1` | `eu561_van_international_v1` | Source (report §20.1) |
|---|---|---|---|
| Work without a break (`work_since_break`) | ≤ 360 | ≤ 360 | Act Art. 13 |
| Driving without a break (`drive_since_break`) | — | ≤ 270 | 561 Art. 7 |
| Break length | 30; total 45 on a day with > 540 work | 45 | Act Art. 13; 561 Art. 7 |
| Daily work (`work_today`) | ≤ 720 (parameter `max_daily_work_min`; 480 in the basic system) | — (bounded by the span) | Act Art. 11, 15 |
| Daily driving (`drive_today`) | — | ≤ 540 | 561 Art. 6 |
| Day span: start of work → start of daily rest | ≤ 780 | ≤ 780 | 24 h − 11 h |
| Daily rest | 660 | 660 | Act Art. 14; 561 Art. 8 |
| Weekly work (`work_week`) | ≤ 3 600 | ≤ 3 600 | Act Art. 12 |
| Weekly driving (`drive_week`) | — | ≤ 3 360 | 561 Art. 6 |
| Two-week driving (`drive_week + drive_prev_week`) | — | ≤ 5 400 | 561 Art. 6 |
| Weekly rest | 35 h, planned at base after `END` | at base after `END` | Act Art. 14; 561 Art. 8 |

Work = driving + service + waiting (Core Domain Rule 9). Breaks and rests are not work.

**FR-3 `advance_drive(s, D)`** — driving is splittable. Repeat until `D` minutes are driven:
1. If `day_start_at` is unset, set it to `t`.
2. Compute the minutes available before each limit of the profile (table above, plus for PL the top-up point of FR-5).
3. Drive `step = min(remaining D, all limits)`; add `step` to the clock and to every work counter and driving counter.
4. If driving remains: a weekly or two-week limit reached → `Infeasible(WEEKLY_LIMIT_REACHED)`; a daily limit or the span reached → insert `DAILY_REST`; otherwise a break limit reached → insert `BREAK` (FR-5). When a rest and a break fall due at the same minute, only the rest is inserted.

**FR-4 `advance_work(s, S)`** — service is atomic. If `S` would cross the weekly work limit → `Infeasible`. If `S` would cross the daily work limit (PL) or end after the day span → insert `DAILY_REST` first. Otherwise, if `work_since_break + S > 360` → insert a `BREAK` first (PL: 30 min, or `max(30, 45 − breaks_today)` when `work_today + S > 540`; 561: 45 min); else, for PL, if `work_today < 540 < work_today + S` and `breaks_today < 45` → insert the top-up break first. Then add `S` to the clock and the work counters.

**FR-5 Breaks.**
- PL: the break inserted at the 6-hour mark is 30 min (45 − `breaks_today`, at least 30, if `work_today ≥ 540` at that moment). When `work_today` reaches 540 and more work follows that day and `breaks_today < 45`, a top-up `BREAK` of `45 − breaks_today` minutes is inserted. A break of ≥ 30 min resets `work_since_break`.
- 561: every break is 45 min; it resets `drive_since_break` and `work_since_break`.

**FR-6 `DAILY_REST`** lasts 660 min and resets `work_today`, `drive_today`, `work_since_break`, `drive_since_break`, `breaks_today` and `day_start_at`. Its location is the stop where it is taken or "en route" on a leg.

**FR-7 `advance_wait(s, W)`.** If `W ≥ 660`: the wait is taken as a `DAILY_REST` of length `W`. Otherwise the wait counts as work for all work counters and is splittable; a break that falls due inside the wait is taken inside it and does not extend it; a daily limit reached inside the wait starts a 660-minute `DAILY_REST`.

**FR-8 Initial state.** Counters come from the driver's `DriverState` snapshot. If `work_today_min > 0`, `day_start_at = last_daily_rest_end`; otherwise it is unset until the first activity. `breaks_today` starts at 0. Weeks run Monday 00:00 – Sunday 24:00 in the time zone of the driver's home base; when the clock crosses that boundary, `drive_prev_week = drive_week` and the weekly counters reset.

**FR-9 Weekly rest.** The MVP never inserts a weekly rest inside a plan. Reaching a weekly limit makes the branch infeasible. A plan that ends at base carries an informational `WEEKLY_REST` marker after `END`.

### 4.2 Cost model, fuel and CO₂

Formulas: report §19.1; parameters: `CostProfile` and vehicle (report §17.4). All money is integer minor units of the profile currency; offer revenue in another currency is converted with `fx_rates` and rounded half-up.

- **FR-10 Fuel.** Per leg with `drive_min > 0`: `v = distance_km × 60 / drive_min`; `L100 = (c_empty + (c_full − c_empty) × load_kg / payload_kg) × speed_curve(v)`; `leg_fuel_l = round_half_up(distance_km × L100 / 100, 3)`. `load_kg` is the mass on board during the leg. `speed_curve` interpolates linearly between the points of the named curve and is constant outside them (`VAN_DEFAULT_V1`: 50 → 1.10, 70 → 0.95, 90 → 1.00, 110 → 1.18, 130 → 1.35). `fuel_l = Σ leg_fuel_l`.
- **FR-11 CO₂.** `co2_kg = round_half_up(fuel_l × CO2_FACTOR_KG_PER_L, 2)`; the factor (default 2.6) is part of the snapshot.
- **FR-12 Cost components** (each rounded half-up once):
  - `fuel_cost = fuel_l × fuel_price_minor_per_l`
  - `toll_cost = Σ legs distance_km × toll_per_km(country of the leg's destination)`; countries in `annual_vignettes` cost 0 and add the flag `VIGNETTE_ASSUMED_ANNUAL`
  - `driver_cost = (drive_min + service_min + wait_min) × driver_cost_minor_per_hour / 60`
  - `per_diem`: 0 for a plan with at least one stop outside the home country (a driver in international road transport is not on a business trip — Art. 26f of the Act on Drivers' Working Time); for a domestic plan `round_half_up(per_diem(home country) × m)`, where `T = finish_at − departure` and `m` is: for `T ≤ 24 h` — 0 below 8 h, 0.5 from 8 h to 12 h, 1 above 12 h; for `T > 24 h` — 1 per full 24 h plus, for a non-zero remainder, 0.5 up to 8 h and 1 above 8 h (Art. 21a; domestic rate 45 zł)
  - `accommodation = (number of DAILY_REST events not at the home base, when sleeper_cab = false) × accommodation_minor`
  - `vehicle_cost = distance_km × vehicle_cost_minor_per_km`
- **FR-13 Profit.** `net_profit = revenue − Σ components`; `revenue` = Σ prices of the plan's offers; `margin_pct = net_profit / revenue × 100` (2 decimals). The breakdown is stored with the plan so that invariants 7 and 17 can be re-checked from it.
- **FR-14 Assumption labels.** Every parameter that report §17.4 labels "assumption" keeps provenance `assumption` in the snapshot and in the plan's `calculation` block.

### 4.3 Prefilter and rejection codes

- **FR-15 Pool prefilter.** For each driver every offer is checked in this fixed order; the first failing check gives the code and the offer leaves the driver's pool:

| Order | Check | Code |
|---|---|---|
| 1 | offer status is `open` | `OFFER_NOT_OPEN` |
| 2 | vehicle type ∈ `required_vehicle_types` | `VEHICLE_TYPE_MISMATCH` |
| 3 | vehicle body ∈ `required_body_types` (when the list is not empty) | `BODY_TYPE_MISMATCH` |
| 4 | required equipment is present on the vehicle | `EQUIPMENT_MISSING` |
| 5 | revenue is known (and its currency convertible) | `MISSING_REVENUE` |
| 6 | both stops have coordinates | `MISSING_COORDINATES` |
| 7 | pallet equivalents can be determined (Core Domain Rule 4) | `MISSING_CAPACITY_DATA` |
| 8 | `weight_kg ≤ payload_kg` | `OVERWEIGHT` |
| 9 | pallet equivalents ≤ `pallet_places` | `PALLET_CAPACITY_EXCEEDED` |
| 10 | load length/height ≤ interior, when both are known | `DIMENSIONS_EXCEEDED` |
| 11 | pickup window starts before the horizon end (`reference_time + horizon_days`) | `OUTSIDE_HORIZON` |
| 12 | `available_from + drive_min(position → pickup) ≤ pickup window end` | `PICKUP_WINDOW_UNREACHABLE` |

- **FR-16 Pallet equivalents.** EUR 1.0, half 0.5, industrial 1.5, unknown type 1.0 + flag `PALLET_TYPE_UNKNOWN`. Pallet count: provenance `source`/`user`/`generated_mock` → use it; missing → `ceil(loading_length_m × 2.4)` + flag `PALLETS_DERIVED`; provenance `ai` → `max(derived, ai)` + flag; nothing → `MISSING_CAPACITY_DATA`.
- **FR-17 Pool size.** If more than `max_pool_per_driver` offers pass, keep those with the highest `revenue / (deadhead_km + loaded_km)`; ties by offer id; set `pool_truncated = true`.
- **FR-18 Search-stage codes.** `FIRST_DEADHEAD_TOO_LONG` (the first pickup of a plan is farther than `max_first_deadhead_km` from the start), `PICKUP_WINDOW_MISSED`, `DELIVERY_WINDOW_MISSED`, `WEEKLY_LIMIT_REACHED`, `HOME_BY_UNREACHABLE`, `BELOW_MIN_PROFIT`, `BELOW_MIN_MARGIN`, `NOT_IN_TOP_K`.
- **FR-19 Rejection report.** For every driver and every offer of the snapshot that is in none of that driver's returned plans there is exactly one entry `{driver_id, offer_id, stage: prefilter|search, code, detail}`. For search-stage entries the code is the outcome of the offer's single-offer plan (first-deadhead check, then schedule, then profit thresholds); an offer whose single-offer plan is feasible and profitable but not returned gets `NOT_IN_TOP_K`.

### 4.4 Per-driver search (Branch-and-Bound)

- **FR-20 Schedule construction** (the same for search, baselines and oracles). Start at the driver's position at `available_from`. For each action: drive (`advance_drive`), wait if the arrival is before the window start (`advance_wait`), check `service_start ≤ window_end`, serve (`advance_work`, `default_service_min` unless the stop has its own value), update the load. Start deferral: if the first stop would require waiting, the departure is delayed by that many minutes instead (idle time is not work; idle time ≥ 660 min counts as a daily rest at the start position). If `home_by` is set and not later than the horizon end, append the drive to the home base as an `END` stop and require `arrival ≤ home_by`; otherwise the plan ends after the last delivery.
- **FR-21 Labels.** Position, clock, load (EUR equivalents, kg), offers on board, offers done, rules state, accumulated cost components, revenue, fuel.
- **FR-22 Moves.** `PICKUP(o)` for a pool offer not yet picked (first pickup subject to `max_first_deadhead_km`; capacity must hold after it; at most `max_offers_per_plan` offers), `DELIVERY(o)` for an offer on board. A label is *complete* when nothing is on board and at least one offer is done.
- **FR-23 Profile passes.** The search runs a domestic pass (offers and start entirely in the home country, profile PL) and an international pass (all pool offers, profile 561, keeping only international plans). Results are merged.
- **FR-24 Bounds.** `profit`: upper bound = revenue so far + Σ revenue of pool offers that could still be added within `max_offers_per_plan` − cost so far; prune when the bound cannot enter the top-K. `fastest` / `fuel`: the clock / fuel so far is a lower bound; prune when it cannot enter the top-K. Bounds must be admissible (property P9 checks this against the oracle).
- **FR-25 Budget and determinism.** Expansion order is deterministic (moves sorted by kind then offer id). The search stops after `node_budget_per_driver` nodes or `wall_clock_safety_s`; then `truncated = true`. The result never depends on wall-clock time except through this flag and `runtimeMs`.
- **FR-26 Top-K.** For each objective the engine returns up to `top_k_per_driver` plans with **distinct offer sets** — for each set its best sequence — sorted by the objective and the tie-breakers of FR-28. Plans below `min_profit` or `min_margin_pct` are not returned.

### 4.5 Objectives

- **FR-27 Lexicographic keys** (no weights; Core Domain Rule 13):

| Objective | Key (best first) |
|---|---|
| `profit` | larger `net_profit` → earlier `finish_at` → smaller `fuel_l` |
| `fastest` | earlier `finish_at` → larger `net_profit` |
| `fuel` | smaller `fuel_l` → larger `net_profit` |

- **FR-28 Tie-breakers.** Between sequences of the same offer set: the action sequences are compared position by position, `DELIVERY` before `PICKUP`, then smaller offer id. Between offer sets: the sorted tuple of offer ids. `finish_at` = arrival at base (`END`) or the end of the last delivery service.

### 4.6 Fleet assignment

- **FR-29.** For each objective choose at most one plan per driver (or none) so that no offer appears twice.
  - `profit`: maximise Σ `net_profit`; ties → smaller Σ `finish_at` offset → smaller Σ `fuel_l` → driver/plan ids.
  - `fastest` / `fuel`: the candidate plans of a driver are the union of its top-K lists for that objective and for `profit`. Every driver that has a plan in the `profit` solution must have a plan. Minimise Σ (`finish_at` − reference time) for `fastest`, Σ `fuel_l` for `fuel`; ties → larger Σ `net_profit` → ids.
- **FR-30.** Exact depth-first search over drivers in the order of increasing candidate count (ties by driver id), with conflict pruning and a bound equal to the sum of each remaining driver's best candidate value.
- **FR-31.** The result per objective is a `FleetSolution {objective, assignments: [{driver_id, plan_ref}], totals: {net_profit, fuel_l, co2_kg, distance_km, drivers_with_plan}}`.

### 4.7 Validators

- **FR-32 `RouteValidator`** receives the snapshot and a plan and re-checks, without calling the search or its schedule builder: invariants 1–7, 13, 14 and 17. It replays the recorded timeline (stops, inserted breaks and rests) and compares every counter with the limits of the profile; it recomputes leg times from the matrix, the cost breakdown through `CostModel`, and `co2_kg`.
- **FR-33 `FleetValidator`** checks invariant 12 and that every referenced plan passed `RouteValidator`.
- **FR-34.** Every plan and fleet solution returned by the engine has passed the validators. A validation failure of an engine result is a bug: the engine raises `EngineInvariantError` (never returns the plan). Weakening a validator to let a result pass is forbidden.

### 4.8 Baselines

- **FR-35 `baseline_single`.** Drivers in ascending id order; each takes the single-offer plan (built with FR-20, including the return to base when required) with the best `profit` key among offers not yet taken, if it meets the profit thresholds.
- **FR-36 `baseline_greedy`.** Start with empty plans. Repeat: among all pairs (driver, unassigned offer) and all insertion positions of that offer's pickup and delivery into the driver's current sequence, take the feasible insertion with the largest positive increase of fleet `net_profit` (ties: driver id, offer id, earliest positions). Stop when no insertion increases the profit. Plans below the thresholds are dropped at the end.
- **FR-37.** Both baselines are returned as plans with `kind = baseline_single | baseline_greedy` and pass the validators.

### 4.9 Engine interface and result

```python
def optimize(snapshot: EngineSnapshot) -> EngineResult: ...          # pure
```

`EngineSnapshot`: reference time, parameters, objectives, `CO2_FACTOR_KG_PER_L`, drivers (id, home base, rules state, vehicle, cost profile), offers (normalised, with stops and provenance), travel matrix (km and minutes between all points, provider id, fallback flag), `solver_version`.
`EngineResult`: `per_driver[driver_id][objective] → [RoutePlan]`, `fleet[objective] → FleetSolution`, `baselines`, `rejections`, `warnings`, `stats {nodes, truncated, pool_truncated, runtimeMs}`.
`RoutePlan`: the fields of `route_plans` and `route_stops` in report §14 — `kind`, `variant`, `rank`, `offer_ids`, `rules_profile`, money totals and breakdown (`calculation`), `distance_km`, `empty_km`, `fuel_l`, `co2_kg`, `duration_min`, `work_min`, `drive_min`, `wait_min`, `finish_at`, `home_reached`, `warnings`, and stops (`START`, `PICKUP`, `DELIVERY`, `BREAK`, `DAILY_REST`, `WEEKLY_REST`, `END`) with arrival, wait, service start, departure, leg km and minutes, load after, counters after.

Plan warnings always include `LOADING_ORDER_NOT_MODELLED` for curtain-siders and, when they apply, `SERVICE_TIME_DEFAULTED`, `ROUTING_FALLBACK`, `PALLETS_DERIVED`, `PALLET_TYPE_UNKNOWN`, `VIGNETTE_ASSUMED_ANNUAL`, `TIME_WINDOW_DAY_ONLY`.

### 4.10 Invariants 1–17

The binding list is in [`context.md` → Optimization Engine Invariants](../context.md#optimization-engine-invariants). Summary: (1) load within capacity; (2) one pickup and one delivery per offer, in that order; (3) no foreign actions, revenue = Σ offers; (4) service start inside the window; (5) monotonic time, arrival = departure + driving + inserted events; (6) driver state conforms to the profile; (7) profit reconstructs from the breakdown; (8) determinism; (9) no feasible plan → empty list + rejection report; (10) top-K distinct and sorted; (11) search = brute-force oracle on small instances; (12) fleet: offer at most once, one plan per driver; (13) `home_by` respected; (14) international ⇒ 561 profile; (15) fleet `profit` ≥ both baselines when not truncated; (16) `fastest` finishes no later and `fuel` burns no more than `profit` — per driver for the rank 1 plans and as fleet sums over the drivers of the `profit` solution; (17) `co2_kg = fuel_l × factor`.

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| NFR-001 | Determinism | property P7; two runs on one snapshot give equal results except `runtimeMs` |
| NFR-002 | Performance | `bench/fleet_5x60.py`: 5 drivers, pool 60, default parameters; target p95 ≤ 15 s on a typical laptop, measured and recorded; if missed, apply the fallback parameters of report §18.3 (`max_offers_per_plan=4`, `horizon_days=3`, `top_k=5`) and record the decision |
| NFR-003 | Correctness | 0 invariant violations across property tests (Hypothesis `ci` 100 examples, `nightly` 1 000) and golden cases |
| NFR-013 | Purity | import-linter contract: `optimization.engine` and `compliance` import only `shared` (and `compliance` from the engine); no `datetime.now`, `os.environ`, DB, HTTP |
| — | Coverage | `optimization.engine`, `compliance` ≥ 90 % lines / 85 % branches |

Default parameters (configurable assumptions, not facts): `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`, `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`, `wall_clock_safety_s=30`.

## 6. Contracts (API, data/migrations, ports, agent tools)

- **API:** none (exposed through jobs in FEAT-004).
- **Data / migrations:** none. `route_plans` / `route_stops` are written by FEAT-004 from `RoutePlan`.
- **Ports:** `DriverRules` (§4.1). The engine receives a `TravelMatrix` value; it does not import `routing`.
- **Test-only modules:** `optimization/engine/oracle.py` (brute force over all pickup/delivery orders for N ≤ 5 offers, K ≤ 3) and `fleet_oracle.py` (all combinations for ≤ 3 drivers × ≤ 4 plans). Importing them outside `tests/` is forbidden.
- **Golden routing provider (test fixture):** `distance_km = round_half_up(haversine × 1.25, 2)`, `drive_min = ceil(distance_km × 60 × 1.08 / 65)`, as in [`specs/golden/README.md`](golden/README.md) G1–G3.
- **Agent tools:** No change (tools over this engine are specified in FEAT-006).

## 7. Acceptance criteria

**Property tests P1–P13** (random small instances: 1–3 drivers, 0–5 offers, cities from `cities.json`, random windows, loads and states; the golden routing provider)

- **AC-FEAT-003-01** [property] **P1** Given any generated instance When the engine returns plans Then after every stop of every plan the load is within `[0, pallet_places]` EUR equivalents and `[0, payload_kg]` kg (invariant 1).
- **AC-FEAT-003-02** [property] **P2** Given any returned plan When its stops are inspected Then each of its offers has exactly one `PICKUP` and one `DELIVERY` in that order, no stop refers to another offer, and `revenue` equals the sum of the offers' prices (invariants 2, 3).
- **AC-FEAT-003-03** [property] **P3** Given any returned plan When its stops are compared with the offers' windows Then every pickup and delivery service starts inside its time window (invariant 4).
- **AC-FEAT-003-04** [property] **P4** Given any returned plan When its timeline is read in order Then stop times never decrease and each arrival equals the previous departure plus the matrix driving time plus the lengths of the events inserted on that leg (invariant 5).
- **AC-FEAT-003-05** [property] **P5** Given any returned plan When its timeline is replayed by an independent checker Then no limit of FR-2 for its profile is exceeded at any minute, and a plan with stops in more than one country uses `eu561_van_international_v1` (invariants 6, 14).
- **AC-FEAT-003-06** [property] **P6** Given any returned plan When its cost breakdown is recomputed Then `net_profit_minor = revenue_minor − Σ breakdown` exactly (tolerance 1 minor unit), each component recomputes from the stops, and `co2_kg = round(fuel_l × factor, 2)` (invariants 7, 17).
- **AC-FEAT-003-07** [property] **P7** Given any snapshot When `optimize` runs twice (and once more with the offers and drivers supplied in a shuffled order) Then the results are equal except `stats.runtimeMs` (invariant 8).
- **AC-FEAT-003-08** [property] **P8** Given any result When its plan lists and rejection report are inspected Then every top-K list has pairwise distinct offer sets, is sorted by the objective key and tie-breakers of FR-27/28, and when a driver has no feasible plan its list is empty and every snapshot offer has a rejection entry for that driver (invariants 9, 10).
- **AC-FEAT-003-09** [property] **P9** Given instances with N ≤ 5 offers and K ≤ 3 When the Branch-and-Bound result is compared with `oracle.py` Then for each objective the offer sets, sequences and objective values of the top-K are identical (invariant 11).
- **AC-FEAT-003-10** [property] **P10** Given any fleet solution When it is inspected Then no offer occurs in two plans and no driver has two plans, and for ≤ 3 drivers × ≤ 4 plans the solution equals `fleet_oracle.py` (invariant 12).
- **AC-FEAT-003-11** [property] **P11** Given a driver whose `home_by` is inside the horizon When the engine returns plans for that driver Then every returned plan ends with an `END` stop at the home base with arrival ≤ `home_by` and `home_reached = true`; when no such plan exists the list is empty (invariant 13).
- **AC-FEAT-003-12** [property] **P12** Given a result with `truncated = false` When the fleet totals are compared Then the fleet profit of the `profit` solution is ≥ the fleet profit of `baseline_single` and of `baseline_greedy` (invariant 15).
- **AC-FEAT-003-13** [property] **P13** Given a result with `truncated = false` When the variants are compared Then for every driver the rank 1 `fastest` plan finishes no later than the rank 1 `profit` plan and the rank 1 `fuel` plan burns no more fuel; and over the drivers of the `profit` fleet solution Σ finish offsets (`fastest`) ≤ Σ finish offsets (`profit`) and Σ litres (`fuel`) ≤ Σ litres (`profit`) (invariant 16).

**Working-time rules**

- **AC-FEAT-003-14** [unit] Given plans (a) entirely in Poland from a Polish base, (b) with one delivery in Germany, (c) domestic stops but a start position in Czechia When the profile is chosen for each Then the profiles are PL, 561 and 561 respectively.
- **AC-FEAT-003-15** [unit] Given a fresh PL state When `advance_work(30)` then `advance_drive(568)` run Then a 30-minute `BREAK` is inserted after 330 minutes of driving, a 15-minute `BREAK` after 180 more, the elapsed time of the drive is 613 minutes, and `work_today = 598`; and When work continues to `work_today = 720` Then the next minute of driving is preceded by a 660-minute `DAILY_REST` that resets the daily counters.
- **AC-FEAT-003-16** [unit] Given a fresh 561 state When `advance_drive(288)` runs Then one 45-minute `BREAK` is inserted after 270 minutes and the elapsed time is 333 minutes; Given `drive_today = 499` and `drive_since_break = 259` When `advance_drive(126)` runs Then a `BREAK` follows after 11 minutes and a `DAILY_REST` after 30 more; Given `work_since_break = 331` When `advance_drive(60)` runs Then a 45-minute break is inserted after 29 minutes.
- **AC-FEAT-003-17** [unit] Given `work_week = 3 590` When `advance_drive(30)` runs under either profile Then the outcome is `Infeasible(WEEKLY_LIMIT_REACHED)`; Given a 561 state with `drive_week + drive_prev_week = 5 390` Then the same; and Given a clock that crosses Monday 00:00 in the base time zone Then `drive_prev_week` takes the old `drive_week` and the weekly counters restart.
- **AC-FEAT-003-18** [unit] Given `work_since_break = 350` When `advance_work(30)` runs Then the break is inserted before the service and the service is not split; Given a wait of 700 minutes Then it is recorded as one `DAILY_REST` of 700 minutes; Given a wait of 120 minutes Then all work counters grow by 120; Given a first stop that would need 45 minutes of waiting Then the plan's departure is 45 minutes after `available_from` and `wait_min = 0`.

**Cost model, prefilter, objectives, fleet, validators, baselines**

- **AC-FEAT-003-19** [unit] Given a plan with known legs, work minutes, one foreign service date and one rest away from base without a sleeper cab When the cost model runs with `GOLD-CP-1` Then each component equals the hand calculation of FR-12 in minor units, and changing a "assumption" parameter changes only its component.
- **AC-FEAT-003-20** [unit] Given the curve `VAN_DEFAULT_V1` When the fuel model is evaluated Then `speed_curve(60) = 1.025`, `speed_curve(40) = 1.10`, `speed_curve(140) = 1.35`; `L100` grows strictly with `load_kg`; a 0-minute leg burns 0 l; and `co2_kg` of 76.601 l with factor 2.6 is 199.16.
- **AC-FEAT-003-21** [unit] Given one offer per row of the FR-15 table that fails only that check When the prefilter runs Then the prefilter returns exactly that code; Given an offer that fails checks 5 and 8 Then the code is `MISSING_REVENUE` (first failing check); Given pallets with provenance `ai` = 3 and a derived value of 5 Then 5 equivalents are used.
- **AC-FEAT-003-22** [unit] Given a snapshot in which no offer is feasible for a driver When `optimize` runs Then the driver's plan lists are empty, the result is still a valid `EngineResult` (no exception), and the rejection report has one entry per offer with a stage and a code.
- **AC-FEAT-003-23** [unit] Given three complete plans with equal profit and different finish times When they are ranked Then `profit` orders them by finish time; Given equal finish times Then by fuel; Given two orders of the same set with equal keys Then the order with `DELIVERY` before `PICKUP` at the first difference wins.
- **AC-FEAT-003-24** [unit] Given a `profit` fleet solution that covers drivers D1 and D2 When the `fastest` and `fuel` solutions are computed Then both give a plan to D1 and D2, minimise their objective sum over the union of candidate lists, and never use an offer twice.
- **AC-FEAT-003-25** [unit] Given a valid plan When it is mutated in turn — a load above capacity, a delivery before its pickup, a service start after the window end, a removed `BREAK`, a changed profit, a changed `co2_kg`, a missing `END` with `home_by` set, the PL profile on an international plan — Then `RouteValidator` rejects each mutation with a distinct error; and a fleet solution with a duplicated offer is rejected by `FleetValidator`.
- **AC-FEAT-003-26** [unit] Given a two-driver instance When `optimize` runs Then the result contains `baseline_single` and `baseline_greedy` plans built by FR-35/36, each passing the validators, with their fleet totals.
- **AC-FEAT-003-27** [unit] Given `node_budget_per_driver = 50` on an instance that needs more nodes When `optimize` runs Then the result has `truncated = true`, every returned plan is still valid, and the invariant-15 check is skipped.
- **AC-FEAT-003-28** [contract] Given the import-linter configuration When `lint-imports` runs Then `optimization.engine` and `compliance` have no import of FastAPI, SQLAlchemy, httpx, `os.environ`, `routing` adapters or `agents`, and the oracles are imported only from `tests/`.
- **AC-FEAT-003-29** [integration] Given `bench/fleet_5x60.py` (marked `bench`, not part of `ci-fast`) When it runs 20 times with fixed seeds Then it prints p50/p95 runtime, node counts and `truncated` flags and writes them to `bench/results/`; the target p95 ≤ 15 s is recorded as met or not met.

**Golden cases** (exact values in [`specs/golden/`](golden/README.md))

- **AC-FEAT-003-30** [golden] Given the inputs of GOLD-001 When the engine runs Then every assertion of GOLD-001 §4 holds.
- **AC-FEAT-003-31** [golden] Given the inputs of GOLD-002 When the engine runs Then every assertion of GOLD-002 §4 holds.
- **AC-FEAT-003-32** [golden] Given the inputs of GOLD-003 When the engine runs Then every assertion of GOLD-003 §4 holds.
- **AC-FEAT-003-33** [golden] Given the inputs of GOLD-004 When the engine runs Then every assertion of GOLD-004 §4 holds.
- **AC-FEAT-003-34** [golden] Given the inputs of GOLD-005 When the engine runs Then every assertion of GOLD-005 §4 holds.
- **AC-FEAT-003-35** [golden] Given the inputs of GOLD-006 When the engine runs Then every assertion of GOLD-006 §4 holds.
- **AC-FEAT-003-36** [golden] Given the inputs of GOLD-007 When the engine runs Then every assertion of GOLD-007 §4 holds.
- **AC-FEAT-003-37** [golden] Given the inputs of GOLD-008 When the engine runs Then every assertion of GOLD-008 §4 holds.
- **AC-FEAT-003-38** [golden] Given the inputs of GOLD-009 When the engine runs Then every assertion of GOLD-009 §4 holds.
- **AC-FEAT-003-39** [golden] Given the inputs of GOLD-010 When the engine runs Then every assertion of GOLD-010 §4 holds.

## 8. Edge cases

- Pickup and delivery in the same city (0 km leg): 0 minutes, 0 litres; ties resolved by FR-28.
- An offer whose pickup window is already open at `available_from`: no wait, no deferral.
- A window that closes during a mandatory daily rest: the branch is infeasible (`*_WINDOW_MISSED`).
- A break and a daily rest due at the same minute: only the rest (FR-3).
- Driver state with `work_today > 0` and no `last_daily_rest_end`: `day_start_at = available_from − work_today` (conservative).
- `home_by` earlier than `available_from`: no plan; rejections `HOME_BY_UNREACHABLE`.
- `home_by` unset or after the horizon end: no `END` stop; `home_reached = false`.
- The driver starts away from the base with `home_by` set: the single action "drive home" is not a plan (a plan needs ≥ 1 offer).
- Revenue in PLN with `fx_rates`: converted once per offer, rounded half-up.
- `payload_kg` or `pallet_places` equal to the load exactly: allowed (GOLD-010).
- Empty offer list or empty driver list: empty result, no error.
- All plans of a driver below `min_profit`: empty list, rejections `BELOW_MIN_PROFIT` (GOLD-008).
- A matrix with the fallback flag: plans carry `ROUTING_FALLBACK`.

## 9. Dependencies

- FEAT-001 (domain value objects in `shared`: `Money`, units, ids); FEAT-002 (`cities.json` for test instances). The engine itself needs neither a database nor FEAT-004.
- ADR-0004, ADR-0010, ADR-0011, ADR-0014.
- Libraries: Hypothesis, pytest (versions in report §9.2). No solver library.
- Golden files `specs/golden/GOLD-001 … 010` and their conventions.

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| 01–13 | `apps/api/tests/props/test_engine_invariants.py`, `test_fleet_assignment.py`, `test_rules_props.py` | Hypothesis strategies for snapshots; `oracle.py`, `fleet_oracle.py`; golden routing provider |
| 14–18 | `apps/api/tests/unit/compliance/` | rules states built by factories |
| 19–27 | `apps/api/tests/unit/engine/` | `GOLD-CP-1` cost profile fixture; plan mutators |
| 28 | `apps/api/tests/unit/test_import_contracts.py` | import-linter |
| 29 | `bench/fleet_5x60.py` | seeded instances from the offer generator |
| 30–39 | `apps/api/tests/golden/test_gold_001.py` … `test_gold_010.py` | one fixture module per golden file; values copied from the `.md` files, with the file path in the test docstring |

Hypothesis profiles: `dev` 50, `ci` 100, `nightly` 1 000 examples. Property tests that fail keep their minimal example in the repository's Hypothesis database for regression.

## 11. Open questions

**Owner decisions (2026-11-11):** all proposed defaults in this table are accepted (OQ-003-04: option (a)), except OQ-003-05: per diems follow the Act on Drivers' Working Time (Dz.U. 2026 poz. 477, Art. 21a and 26f) — see FR-12 and golden convention G9. GOLD-001, 002, 007 and 008 were recalculated; GOLD-001 now returns five plans.

Each row is a detail that the existing documents do not fix. The proposed default is what this specification and the golden cases use. The owner confirms or changes it at approval; a change means recalculating the golden values named in "Blocks".

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-003-01 | Fallback routing formula: does `van_speed_factor` multiply the time, and how are distance and minutes rounded? | `distance_km = round_half_up(haversine × 1.25, 2)`; `drive_min = ceil(distance_km × 60 × 1.08 / 65)`; Earth radius 6 371.0088 km | all golden values |
| OQ-003-02 | Speed-curve interpolation and the speed used for a leg. | Linear between points, constant outside; `v = distance_km × 60 / drive_min` | fuel, CO₂ and profit in all golden cases |
| OQ-003-03 | Rounding points and final tie-breakers. | FR-10 … FR-13, FR-28 | exact minor units and litres |
| OQ-003-04 | PL break when daily work exceeds 9 h. `context.md` says "45 minutes when daily work > 9 h; in the MVP the break is taken whole", but at the 6-hour mark the engine cannot know the day's total. Options: (a) 30 min at 6 h + 15 min at 9 h; (b) always 45 min at 6 h; (c) after a 30-minute break cap the day at 9 h. | (a) — both parts ≥ 15 min as Art. 13 allows | GOLD-007, GOLD-008; AC-15 |
| OQ-003-05 | Per-diem counting: partial days, time abroad without route geometry, domestic per diem. | FR-12: one full rate per foreign country per local date with a service start there; domestic 0 | GOLD-001 (per diem 98.00 €) |
| OQ-003-06 | Waiting and start: is a long wait a rest; may the departure be deferred; is service atomic? | FR-4, FR-7, FR-20 | plans with waits (GOLD-004 set {G}); AC-18 |
| OQ-003-07 | Anchor of the 24-hour window: start of work (PL wording) vs end of the previous rest (561 wording). | `day_start_at` = first activity after a rest, for both profiles; from the snapshot when the day is already running | span-driven rests (GOLD-001) |
| OQ-003-08 | Week boundary for weekly counters. | Monday 00:00 in the home-base time zone | AC-17 |
| OQ-003-09 | Default `min_profit` and `min_margin_pct`. | 0 and 0 % | which low-profit plans are shown |
| OQ-003-10 | Ranking used to cut the pool to `max_pool_per_driver`. | `revenue / (deadhead_km + loaded_km)`, ties by id | results only when > 60 offers pass |
| OQ-003-11 | Order of prefilter checks and names of the rejection codes (only `MISSING_CAPACITY_DATA`, `MISSING_REVENUE`, `MISSING_COORDINATES` are named in `context.md`). | FR-15, FR-18 | GOLD-006; FEAT-005 translations of codes |
| OQ-003-12 | Attribution of toll kilometres to countries without route geometry. | The whole leg is charged at the rate of its destination country | plans through FR/IT |
| OQ-003-13 | `fastest` and `fuel` are minimised over all profitable plans, so they favour short plans (often a single short offer). Is that the intended behaviour of these variants? | Keep the definition of Core Domain Rule 13; show Δ profit next to each variant. A possible refinement (profit ≥ a share of the `profit` variant) would need a rule change. | usefulness of the variants; GOLD-001 assertion 12 |
| OQ-003-14 | Exact definition of `baseline_greedy`. | FR-36 | GOLD-009 baseline value |
| OQ-003-15 | Accommodation for a daily rest "en route" and for a van with a sleeper cab under the PL profile. | Charged for every daily rest away from base when there is no sleeper cab; 0 with a sleeper cab under both profiles | GOLD-001, 007, 008 (55.00 €) |
| OQ-003-16 | Fleet `fastest`/`fuel`: the report requires "the same or a larger number of drivers"; invariant 16 compares "the same drivers". | Every driver of the `profit` solution must keep a plan; candidates = union with the `profit` lists (FR-29) | AC-13, AC-24 |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-09 | Initial draft |
| 2 | 2026-11-11 | Owner decisions on the open questions recorded (§11); FR-12 per-diem rule replaced; warning `PER_DIEM_DEFAULTED` removed |
| 3 | 2026-11-11 | Status `draft` → `approved` by the owner |
