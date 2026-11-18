---
id: FEAT-017
title: Larger fleets — benchmark grid, CP-SAT fleet selection and an optional candidate generator
status: draft
owner: project owner
requirements: [REQ-039, REQ-010, NFR-001, NFR-002, NFR-017]
adrs: [ADR-0004, ADR-0016]
modules: [bench, freight (generator: market simulation), fleet (generator: fleet size), optimization.engine (fleet selection, candidate generator port)]
revision: 1
---

# FEAT-017: Larger fleets — benchmark grid, CP-SAT fleet selection and an optional candidate generator

> **Draft, 2026-11-18. Not approved.** It needs the owner's approval and acceptance of ADR-0016, including the new runtime dependency `ortools` (backlog owner action O-20). After the MVP: slice 017/1 in phase 1, 017/2 in phase 2, 017/3 in phase 3, and 017/3 only if the 017/2 benchmark gate says so.
> Research behind it: [`docs/research/2026-11-17-ai-dispatcher-evolution.md`](../docs/research/2026-11-17-ai-dispatcher-evolution.md) §7.3–7.7, §13.
> All benchmark data is synthetic (`is_synthetic = true`). Benchmark numbers are recorded, never asserted, except where an AC says so.
>
> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Goal

**A reproducible benchmark** measures the engine on synthetic fleets of 5, 20, 50 and 100 vans, with:
- 1-, 7- and 21-day horizons (21 days as rolling 7-day steps);
- three offer densities and two consolidation levels;
- mixed rotations;
- static and dynamic offer arrival.

**Fleet selection** (choosing at most one plan per driver and each offer at most once) scales to 50+ drivers with an exact CP-SAT set-packing model. The current exact DFS stays as the oracle and the fallback.

**Optionally**, a `CandidateGenerator` port lets an OR-Tools PDPTW model propose routes for large fleets. **Every** route it proposes is re-scheduled by the existing `ScheduleBuilder` and checked by the existing validators. It is adopted only if the benchmark shows it beats the B&B at equal feasibility.

## 2. Business context

The fleet DFS is exact and exponential in the number of drivers [`optimization/engine/fleet.py:47-91`]; the research note calls it fine at 5 drivers and not viable at 50. The B&B is per driver and exact. No public benchmark combines PDPTW with profits, 2-D capacity, EU driver rules and rotations (research note §13), so RoutePilot needs its own.

OR-Tools 9.15 is Apache-2.0 with cp313 wheels (research note §15.4). `context.md` lists OR-Tools as "outside the MVP", so it needs ADR-0016 and a spec.

Requirements: REQ-039 (new), REQ-010, NFR-001, NFR-002, NFR-017.

## 3. Scope / Out of scope

**In scope:**
- `bench/grid.py` with the factor grid and a fractional design.
- Generator flags: fleet size, density, dynamism, rotations.
- A JSON report with metrics and machine information.
- `FleetSelector` port: implementations `DfsFleetSelector` (existing code, moved behind the port) and `CpSatFleetSelector`.
- `CandidateGenerator` port: implementations `BranchAndBoundGenerator` (existing per-driver search) and `OrToolsPdptwGenerator`, with repair and validation.
- The adoption-gate report.

**Out of scope:**
- Changing the default solver without an owner decision;
- PyVRP and VROOM adapters (benchmark challengers only if the owner asks);
- distributed or parallel processes beyond the existing worker;
- routing-engine changes.

## 4. Functional requirements

- **FR-1 Grid.** Factors:
  - fleet {5, 20, 50, 100};
  - horizon {1, 7, 21} days;
  - density {4, 12, 30} offers per vehicle-day;
  - consolidation share {0.2, 0.75};
  - rotations {all Mon–Fri, mixed 14/7 + 21/7 + Mon–Fri with two anchor offsets};
  - dynamism {0 %, 30 % released during the horizon}.
  The full grid has 288 cells × 5 seeds. A fractional design of 36 cells (documented list) runs in ≤ 60 min on the reference laptop (recorded).
- **FR-2 Generators.**
  - `generate_fleet(n_drivers=…)` scales the existing fleet generator: bases cycle over the 5 demo bases plus generated towns, and vans keep 8/9/10 EP.
  - `generate_offers(density, consolidation, dynamism, horizon)` extends `offers-generator v3` with release times and cancellation events.
  - Same seed → same output; every record is synthetic.
- **FR-3 Metrics per run:**
  - fleet cycle profit and profit;
  - the gap to `baseline_greedy` and `baseline_return_empty`;
  - empty-km share;
  - EP·km and kg·km fill (all and loaded km);
  - offers served / offered;
  - validator feasibility before and after repair;
  - repair iterations;
  - runtime p50/p95 wall and CPU;
  - peak RSS;
  - home-return reliability (FEAT-012 P14 share);
  - plan stability after an arrival step (share of committed stops kept, in order).
  Also recorded: generator version, seeds, CPU model, core count, Python and dependency versions.
- **FR-4 `FleetSelector` port.**
  - `select(objective, candidates) -> FleetSolution`.
  - `DfsFleetSelector` is the current `assign_fleet` [`fleet.py:47-91`], unchanged in behaviour.
  - `CpSatFleetSelector`:
    - one Boolean per candidate plan;
    - ≤ 1 per driver; ≤ 1 per offer;
    - lexicographic objectives as staged solves (maximise cycle profit; then fix it and minimise finish; then fuel — matching FEAT-012 `profit_v2` order);
    - `num_workers = 1`, a fixed `random_seed`, and a time limit `FLEET_SELECT_BUDGET_S` (default 10, *assumption*).
  - On a timeout without proof of optimality, the result carries `selectionTruncated = true` with the best solution found.
- **FR-5 Selection config.** `ENGINE_FLEET_SELECTOR = dfs | cpsat`, default `dfs` until the owner switches it. If `ortools` is not importable, `cpsat` falls back to `dfs` with the flag `SELECTOR_FALLBACK`.
- **FR-6 `CandidateGenerator` port.**
  - `generate(snapshot, budget) -> dict[driver_id, list[RoutePlan candidates]]`.
  - The default `BranchAndBoundGenerator` wraps the existing per-driver search.
  - `OrToolsPdptwGenerator`:
    - one vehicle per driver, start = position at `available_from`, end = home with the deadline as the end time window;
    - pickup and delivery pairs with the same-vehicle and precedence constraints;
    - two capacity dimensions (EP × 10, kg);
    - time windows;
    - optional offers via one disjunction per pair, with penalty = revenue;
    - a conservative daily-driving surrogate dimension;
    - transit costs registered as matrices (no Python callbacks in the inner loop);
    - `GUIDED_LOCAL_SEARCH`, a time limit and a fixed seed.
    - It must not use `SetAllowedVehiclesForIndex` (known 9.15 Python issue #4982).
- **FR-7 Repair and validation.**
  - Every generated route is re-scheduled with `build_plan()` under the real `DriverRules` profile and checked by `RouteValidator`.
  - On failure, the offer with the lowest marginal cycle profit is dropped and the route is re-scheduled, up to `REPAIR_MAX = 3` (*assumption*); then the route is discarded.
  - Only validator-accepted plans enter fleet selection.
- **FR-8 Adoption gate.**
  - `bench/gate_report.py` compares B&B and OR-Tools generator candidates at 20 and 50 vans × 7 days, at equal budgets.
  - The gate passes when OR-Tools gives ≥ the B&B fleet cycle profit with 100 % post-repair feasibility in ≥ 80 % of cells, within the time budget.
  - The report is stored; the owner decides on `ENGINE_CANDIDATE_GENERATOR = bnb | ortools | auto` (default `bnb`).

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| NFR-001 | Determinism | same snapshot + seed + selector → identical result (property test on CP-SAT with 1 worker) |
| NFR-002 | Performance targets | 5×60: p95 ≤ 30 s; 20 × 7 d: ≤ 120 s; 50 × 7 d: ≤ 300 s (recorded) |
| NFR-017 | Stability | ≥ 90 % committed stops kept after a 10 % arrival step (recorded) |
| NFR-019 | Selection scalability | CP-SAT selection of 50 drivers × 10 candidates ≤ 5 s (bench, recorded) |

## 6. Contracts (API, data/migrations, ports, agent tools)

- **API:** none. `OptimizationResult` gains the additive fields `selector`, `generator`, `selectionTruncated` and `repairStats`.
- **Data / migrations:** none.
- **Ports** (pure, in `optimization/engine`):

  ```python
  class FleetSelector(Protocol):
      selector_id: str
      def select(self, objective: Objective, candidates: list[RoutePlan]) -> FleetSolution: ...

  class CandidateGenerator(Protocol):
      generator_id: str
      def generate(self, snapshot: EngineSnapshot, budget: Budget) -> dict[str, list[RoutePlan]]: ...
  ```

- **Configuration:** `ENGINE_FLEET_SELECTOR=dfs`, `ENGINE_CANDIDATE_GENERATOR=bnb`, `FLEET_SELECT_BUDGET_S=10`, `REPAIR_MAX=3`.
- **Dependency:** `ortools==9.15.6755` (Apache-2.0; verify on PyPI at implementation time; cp313 wheels for macOS arm64 and manylinux). An optional extra is not possible with the "local run" rule, so it is a regular dependency, imported lazily.
- **Agent tools:** no change.

## 7. Acceptance criteria

- **AC-FEAT-017-01** [unit] Given the grid definition When the fractional design is listed Then it has 36 cells covering every level of every factor at least once, and the same seed list gives identical generated instances (byte-identical JSON).
- **AC-FEAT-017-02** [property] Given any seed and grid cell When fleet and offers are generated Then every record is synthetic, the fleet has the requested size, offer counts match density × vehicle-days ± 5 %, and released offers have a release time inside the horizon.
- **AC-FEAT-017-03** [unit] Given a benchmark run When the report is written Then it contains every metric of FR-3 plus the machine information, and the runtime figures are not asserted.
- **AC-FEAT-017-04** [property] Given random candidate sets with ≤ 5 drivers and ≤ 4 candidates each When `CpSatFleetSelector` and `DfsFleetSelector` select for each objective Then both return solutions with equal objective values, and the CP-SAT solution passes `FleetValidator`.
- **AC-FEAT-017-05** [property] Given the same candidates When `CpSatFleetSelector` runs twice with the same seed Then the selected plan ids are identical.
- **AC-FEAT-017-06** [unit] Given `ENGINE_FLEET_SELECTOR=cpsat` and `ortools` made unimportable in the test When the engine runs Then `DfsFleetSelector` is used, and the result carries `SELECTOR_FALLBACK`.
- **AC-FEAT-017-07** [unit] Given 50 drivers × 10 synthetic candidates When `CpSatFleetSelector` runs with a 10 s budget Then it returns a `FleetValidator`-valid solution, and its runtime is recorded in the bench report (the ≤ 5 s target is recorded, not asserted).
- **AC-FEAT-017-08** [golden] Given GOLD-001 … GOLD-012 When the engine runs with the `BranchAndBoundGenerator` behind the new port Then all results are unchanged.
- **AC-FEAT-017-09** [property] Given random snapshots When `OrToolsPdptwGenerator` produces candidates Then every plan that reaches fleet selection passes `RouteValidator` under its real profile, and the repair statistics are reported.
- **AC-FEAT-017-10** [unit] Given gate-report inputs for 20 and 50 vans When the gate is evaluated Then the report states pass or fail per cell and overall by the FR-8 rule, and no default changes automatically.

## 8. Edge cases

- **No candidate for a driver:** the driver stays without a plan (as today).
- **CP-SAT reports infeasibility:** impossible by construction (the empty selection is feasible). If it happens, it is a bug: fall back to DFS with `SELECTOR_FALLBACK` and log an error.
- **OR-Tools returns no solution within the budget:** the generator returns no candidates, and the B&B candidates are used when `auto`.
- **Very large matrices:** 100 vans × 3,000 offers exceed sensible memory. The grid's 100-van cells use density 4 only (documented).

## 9. Dependencies

- FEAT-011 (rotations in the grid), FEAT-012 (`profit_v2`, GOLD-012, `baseline_return_empty`), FEAT-014 (committed prefix for stability).
- ADR-0016; owner approval of the dependency (O-20).
- Library: `ortools` (Apache-2.0).
- Shared files: `apps/api/pyproject.toml` and `uv.lock` (🔒, new dependency).

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| 01–03 | `bench/tests/test_grid.py`, `apps/api/tests/props/test_scaled_generators.py` | seeds |
| 04–07 | `apps/api/tests/props/test_fleet_selector.py`, `apps/api/tests/unit/engine/test_fleet_selector.py` | synthetic candidates |
| 08 | existing golden suite + GOLD-012 | — |
| 09 | `apps/api/tests/props/test_ortools_generator.py` (marked `slow`, not in `ci-fast`) | small snapshots |
| 10 | `bench/tests/test_gate_report.py` | fixture report |

## 11. Open questions

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-017-01 | Add `ortools` as a dependency (size about 25 MB per wheel; UNVERIFIED) | yes, after ADR-0016 | 017/2 |
| OQ-017-02 | Thresholds of the adoption gate | ≥ B&B profit, 100 % feasibility after repair, ≥ 80 % of cells | AC-10 |
| OQ-017-03 | Should the fractional grid run nightly in CI? | manual only until the owner approves a workflow change (development log I8) | nothing |
| OQ-017-04 | Add PyVRP as a challenger | no, unless requested | nothing |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-18 | Initial draft from the research note §7 and §13 (E7) |
