---
id: FEAT-012
title: Engine reliability and cycle-aware planning
status: draft
owner: project owner
requirements: [REQ-036, REQ-009, REQ-010, REQ-013, REQ-014, NFR-002, NFR-016]
adrs: [ADR-0004, ADR-0016]
modules: [optimization.engine (search, schedule, fleet, costs, validators, oracle, models), optimization.jobs (results read model), contracts, web features/plans, bench, specs/golden]
revision: 1
---

# FEAT-012: Engine reliability and cycle-aware planning

> **Draft, 2026-11-18. Not approved: nothing here may be implemented before the owner sets `status: approved` and accepts ADR-0016 (backlog owner action O-15).** After the MVP (phase 1, `backlog.md` §9).
> Research behind it: [`docs/research/2026-11-17-ai-dispatcher-evolution.md`](../docs/research/2026-11-17-ai-dispatcher-evolution.md) §2.3, §5.6, §7.
> This feature changes engine invariants and objectives. That needs human approval (`context.md` → Human Approval Requirements). Golden values need owner approval before their tests are written.
>
> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Goal

The engine finishes within a **job-level** time budget, and it never drops international plans because a domestic pass was cut short. It prunes more without losing exactness.

Every plan also knows its **return obligation**:
- If the driver's deadline lies inside the horizon, the plan ends at home before it (as today).
- If the deadline lies beyond the horizon, the engine checks, under the working-time rules, that the driver can still reach home in time from the plan's last stop, and it charges the cost of that return as `return_reserve`.

Plans are ranked by **cycle profit** = profit − `return_reserve`. A new baseline, "return empty", shows what the cycle is worth without any freight.

## 2. Business context

Measured on the synthetic demo (research note §2.7):
- At defaults, the 5 × 60 benchmark takes p50 158 s / p95 173 s, and 20/20 runs are truncated.
- The 30 s limit is applied per driver [`optimization/engine/search.py:57-58, 107-108`].
- The international pass is skipped after a truncated domestic pass [`search.py:145-151`].
- With a 2-day horizon, 0% of plans return home (`docs/metrics.md`), because the home leg is added only when `home_by` falls inside the horizon [`schedule.py:276-279`]. Plans that strand the van far from home look profitable.

The worked 14/7 case in research note §5.6 shows that the best isolated offer can be the worst cycle choice. Requirements: REQ-036 (new), REQ-009, REQ-010, REQ-013, REQ-014, NFR-002, NFR-016 (new).

## 3. Scope / Out of scope

**In scope:**
- A job-level wall-clock budget shared across drivers, with a `truncatedDrivers` report.
- Separate budget shares for the domestic and international passes.
- Label dominance and incumbent seeding (development log I1).
- One `home_requirement()` function replacing the four copies of the home-return rule.
- The return-leg feasibility replay and `return_reserve`.
- Objective version `profit_v2`.
- `baseline_return_empty`.
- New invariants P14 and P17.
- Golden case GOLD-012 (values approved by the owner first).
- Read-model and UI fields for plan profit, return reserve and cycle profit.

**Out of scope:**
- Rotation data (FEAT-011 supplies `HomeRequirement`; until then `home_by` from `driver_states` is used).
- Weekly rest and the rest ledger (FEAT-013).
- Fleet selection with CP-SAT and new solvers (FEAT-017).
- Insertion into committed routes (FEAT-015).
- Raising the 7-day horizon cap.

## 4. Functional requirements

- **FR-1 Job budget.**
  - `EngineParams.wall_clock_safety_s` becomes the budget of the whole `optimize()` call.
  - Each driver gets `remaining_budget / remaining_drivers`, in driver-id order. Unused time returns to the pool.
  - Baselines, rejections and validation stay outside the search budget but are reported in `timings`.
  - The engine never reads the system clock; it uses the injected elapsed-time callback (`context.md` → Architecture Principles 3).
- **FR-2 Truncation report.** `OptimizationResult` gains `truncatedDrivers: list[{driverId, pass: domestic|international, reason: node_budget|time_budget}]`. The existing `truncated` flag stays: true if the list is not empty.
- **FR-3 Both passes.**
  - When a driver qualifies for both passes, the domestic pass gets at most 50% of the driver's share (*assumption*). The international pass always runs on the remainder, even if the domestic pass was truncated.
  - The node budget is split the same way.
- **FR-4 Label dominance.** A partial plan A is dropped when another partial plan B with the same set of picked offers, the same on-board set and the same position has:
  - B.t ≤ A.t;
  - B.cost ≤ A.cost;
  - B.load ≤ A.load;
  - all working-time counters of B ≤ those of A.
  Ties are broken by action sequence. The result must equal the exhaustive oracle when not truncated.
- **FR-5 Incumbent seeding.** Plans from `baseline_greedy` and `baseline_single` for the driver are inserted into the top-K lists before the search starts. This changes pruning only, never the returned set when not truncated.
- **FR-6 Single home rule.**
  - `engine/home.py::home_requirement(snapshot, driver) -> HomeRequirement | None` returns the deadline, the point and the kind.
  - `ScheduleBuilder.finish`, `build_plan`, `RouteValidator` and `oracle.py` all use it [replacing `schedule.py:276-279, 393-396`, `validators.py:105-109`, `oracle.py:50-52`].
- **FR-7 Return replay.**
  - Inside the horizon (deadline ≤ reference + horizon): unchanged. The plan ends at home; otherwise `HOME_BY_UNREACHABLE`.
  - Beyond the horizon: after the last action, replay the drive from the last point to the home point with the same `DriverRules` profile, inserting breaks and rests.
    - Arrival after the deadline → reject with `HOME_BY_AT_RISK`.
    - Otherwise, store `returnLeg = {distanceKm, driveMin, arrivalAt, restsInserted}`.
  - The plan's stops do **not** include the return leg; it is reported separately.
- **FR-8 Return reserve.**
  - `returnReserveMinor` = CostModel cost of the `returnLeg`: fuel (empty), vehicle per km, tolls per country, driver hours, accommodation for inserted daily rests away from home without a sleeper cab.
  - The same `costs.py` functions are used. Money is int minor units.
  - When the plan ends at home inside the horizon, `returnReserveMinor = 0`.
- **FR-9 Objective `profit_v2`.**
  - `cycleProfitMinor = profitMinor − returnReserveMinor`.
  - Ranking keys:
    - `profit`: (−cycleProfit, finishAt, fuelL);
    - `fastest`: (finishAt, −cycleProfit);
    - `fuel`: (fuelL, −cycleProfit).
  - Ties break on the existing plan key.
  - The minimum profit and margin thresholds apply to `cycleProfitMinor`.
  - `OptimizationResult.objectiveVersion = "v2"`. Stored v1 results are still read and shown with `objectiveVersion = "v1"`.
- **FR-10 Baseline `baseline_return_empty`.** Per driver, a plan with no offers: start → home (when a home requirement exists), with its cost. The fleet total of this baseline is reported. Invariant 15 extends to it: the `profit` solution's fleet cycle profit ≥ every baseline when not truncated.
- **FR-11 Validator.** `RouteValidator` independently replays the return leg with its own code path and checks P14 and P17:
  - **P14:** every plan is either home by the deadline or has a feasible return replay with `returnReserveMinor` charged.
  - **P17:** `cycleProfitMinor = profitMinor − returnReserveMinor` to one minor unit.
- **FR-12 Read model and contract.** `RoutePlan` and `PlanSummary` gain `returnReserve` (money), `cycleProfit` (money), `returnLeg` (nullable) and `objectiveVersion`. `contracts/openapi.json` and `schema.d.ts` are regenerated. This is an additive, non-breaking change.
- **FR-13 UI.** The plan header and the variant cards show "Plan profit", "Return reserve" and "Cycle profit" (EN/PL), with a tooltip explaining that the reserve is the estimated cost of driving home empty from the last stop. The working-time notice stays.
- **FR-14 Benchmark.** `bench/fleet_5x60.py` reports `truncatedDrivers`, the nodes per pass, and the share of drivers home or with a feasible return. It gains a `--drivers N` flag. Numbers are recorded, never asserted.

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| NFR-001 | Determinism | identical snapshot → identical result (except timings), property test |
| NFR-002 | Engine performance at defaults (5 drivers, pool 60, ≤ 6 offers, 5 days) | p95 ≤ 30 s on the reference laptop (target, recorded by the benchmark, not asserted) |
| NFR-016 | Bounded job runtime | `optimize()` search time ≤ `wall_clock_safety_s × 1.2` per job (unit test with an injected elapsed callback) |

## 6. Contracts (API, data/migrations, ports, agent tools)

- **API:** no new endpoint.
  - `GET /optimization-jobs/{id}/result` gains `truncatedDrivers`, `objectiveVersion` and `baselines.returnEmpty`.
  - `GET /route-plans/{id}` gains `returnReserve`, `cycleProfit`, `returnLeg`, `objectiveVersion`.
  - The change is additive; `oasdiff` must report no breaking change.
- **Data / migrations:** no new table or column. The new fields live in the existing JSON result and plan payloads. If `route_plans` stores profit in a column, `cycle_profit_minor` is computed on read (like the FEAT-010 load metrics).
- **Ports:** no change. `DriverRules` is used for the return replay.
- **Configuration:** `EngineParams.domestic_pass_share = 0.5` (*assumption*); `wall_clock_safety_s` semantics change from per driver to per job (documented in the ADR-0016 update).
- **Agent tools:** no change in this feature. FEAT-016 adds `compare_cycle_options`. Existing tool outputs gain no fields unless FEAT-016 says so.

## 7. Acceptance criteria

- **AC-FEAT-012-01** [unit] Given 5 drivers and an injected elapsed-time callback that advances 1 s per 1,000 nodes When `optimize()` runs with `wall_clock_safety_s = 30` Then the total search time reported is ≤ 36 s, and every driver received a non-zero share.
- **AC-FEAT-012-02** [unit] Given a run where two drivers hit their share When the result is built Then `truncatedDrivers` lists exactly those drivers with the pass and reason, and `truncated = true`.
- **AC-FEAT-012-03** [unit] Given a driver in the home country with domestic and international offers and a domestic pass forced to truncate When the search runs Then feasible `eu561_van_international_v1` plans are present in the driver's top-K.
- **AC-FEAT-012-04** [property] Given random instances with N ≤ 5 offers When the search runs with label dominance and incumbent seeding and is not truncated Then the top-K plans equal the exhaustive oracle's top-K (existing P11 extended).
- **AC-FEAT-012-05** [unit] Given the 20 benchmark seeds When the search runs with and without label dominance Then the results are identical and the node count with dominance is lower or equal on every seed (the reduction factor is recorded in the bench output, not asserted).
- **AC-FEAT-012-06** [golden] Given GOLD-001 … GOLD-011 and properties P1–P13 When they run after the `home_requirement()` refactor Then every result is unchanged.
- **AC-FEAT-012-07** [unit] Given a driver whose deadline lies beyond the horizon and an offer that ends 1,500 km from home 10 h before the deadline When the plan is finished Then it is rejected with `HOME_BY_AT_RISK`. Given the deadline 30 h later Then the plan is accepted with a `returnLeg`.
- **AC-FEAT-012-08** [unit] Given an accepted plan with a `returnLeg` When costs are computed Then `returnReserveMinor` equals the CostModel cost of an empty leg of that distance and duration, including accommodation for each inserted daily rest away from home without a sleeper cab.
- **AC-FEAT-012-09** [property] Given random snapshots When plans are produced Then P14 and P17 hold for every plan, checked by the independent validator.
- **AC-FEAT-012-10** [unit] Given two plans where A has the higher profit but the lower cycle profit When the `profit` objective ranks them Then B ranks first, and the result carries `objectiveVersion = "v2"`.
- **AC-FEAT-012-11** [unit] Given any snapshot When baselines are built Then `baseline_return_empty` exists for every driver with a home requirement, and the `profit` solution's fleet cycle profit ≥ every baseline's fleet cycle profit when not truncated (invariant 15 extended).
- **AC-FEAT-012-12** [golden] Given GOLD-012 (a 14/7 driver near the end of the rotation with offers A, B and C, specified in `specs/golden/GOLD-012.md` and approved by the owner) When the engine runs Then the `profit` solution and the rejections equal the approved values to one minor unit.
- **AC-FEAT-012-13** [contract] Given the regenerated OpenAPI When `oasdiff breaking` compares it with `main` Then it reports no breaking change, and the plan schema contains `returnReserve`, `cycleProfit`, `returnLeg` and `objectiveVersion`.
- **AC-FEAT-012-14** [e2e] Given a plan with a return reserve When the plan screen opens in EN and in PL Then plan profit, return reserve and cycle profit are shown with their tooltip and the working-time notice.

## 8. Edge cases

- **No home requirement** (no `home_by`, no rotation): no return leg, `returnReserveMinor = 0`, and `baseline_return_empty` is absent for that driver.
- **The plan ends at the home point:** the reserve is 0.
- **The return replay needs a weekly rest:** FEAT-013 decides; until then a replay that would exceed weekly limits fails with `HOME_BY_AT_RISK` (conservative).
- **Routing fallback** (haversine) for the return leg: the plan keeps the `ROUTING_FALLBACK` warning.
- **Truncated run:** invariant 15 is not asserted (as today).
- **Stored v1 results:** they are not recomputed.

## 9. Dependencies

- FEAT-003 (engine), FEAT-004 (jobs and read model), FEAT-005 (plan UI), FEAT-010 (pool and metrics).
- ADR-0004 (engine) and ADR-0016 (proposed; changes the time-budget semantics and the objectives).
- FEAT-011 provides rotation-based home requirements; this feature works with `home_by` alone.
- Libraries: none new.
- Shared files: `contracts/openapi.json`, `apps/web/messages/*.json`, `specs/golden/**` (🔒 golden values).

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| 01–03 | `apps/api/tests/unit/engine/test_search_budget.py` | small snapshots, fake elapsed callback |
| 04 | `apps/api/tests/props/test_engine_invariants.py` (extend P11) | Hypothesis `ci` profile |
| 05 | `apps/api/tests/unit/engine/test_dominance.py` + `bench/fleet_5x60.py` | bench seeds 20261116 … 35 |
| 06 | existing golden and props suites | unchanged |
| 07, 08, 10, 11 | `apps/api/tests/unit/engine/test_return_reserve.py` | hand-built matrices |
| 09 | `apps/api/tests/props/test_engine_invariants.py` (new P14, P17) | — |
| 12 | `apps/api/tests/golden/test_gold_012.py` | `specs/golden/GOLD-012.md` (owner-approved) |
| 13 | `apps/api/tests/contract/test_openapi_drift.py` | — |
| 14 | `tests/e2e/plan-cycle-profit.spec.ts`, `apps/web/src/features/plans/*.test.tsx` | MSW |

## 11. Open questions

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-012-01 | Domestic pass share of the budget | 0.5 (*assumption*) | AC-03 |
| OQ-012-02 | Should the reserve be discounted for a likely backhaul? | no; conservative and shown, never hidden | AC-08 |
| OQ-012-03 | GOLD-012 values: hand calculation with the engine's real `CostModel` and matrix (the research note's figures are illustrative) | Architect agent proposes, owner approves | AC-12 |
| OQ-012-04 | Should `wall_clock_safety_s` keep its name with the new per-job meaning? | yes, documented in ADR-0016 | AC-01 |
| OQ-012-05 | Should the reserve include the drive to the next duty-window start instead of home when the driver stays abroad on purpose? | no, phase 3 (handover) | nothing |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-18 | Initial draft from the research note §7 and §12 (E1) |
