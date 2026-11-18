# ADR-0016: Staged optimiser evolution — job-level budget, cycle-aware objective, CP-SAT fleet selection, optional OR-Tools candidates

- Status: proposed
- Date: 2026-11-18
- Amends: [ADR-0004](ADR-0004-optimization-engine.md) (it does not supersede it; B&B and the independent validators stay)
- Specifications: [FEAT-012](../../specs/FEAT-012-engine-reliability-and-cycle-aware-planning.md), [FEAT-017](../../specs/FEAT-017-larger-fleets.md)
- Research: [`docs/research/2026-11-17-ai-dispatcher-evolution.md`](../research/2026-11-17-ai-dispatcher-evolution.md) §7

## Context

ADR-0004 chose a per-driver Branch-and-Bound with top-K, an exact fleet assignment and independent validators. It expected to revisit the decision "when the fleet exceeds about 10 drivers".

Measured on the synthetic demo (research note §2.7):
- At defaults (5 drivers, pool 60, ≤ 6 offers, 5 days), p95 is 172.9 s and 20/20 runs are truncated.
- The 30 s safety limit applies per driver (`optimization/engine/search.py:57-58, 107-108`).
- A truncated domestic pass skips the international pass (`search.py:145-151`).
- The fleet assignment is an exact DFS that is exponential in the number of drivers (`fleet.py:47-91`).
- Plans whose return deadline lies beyond the horizon end anywhere at no cost (`schedule.py:276-279`). With a 2-day horizon, 0% of plans return home (`docs/metrics.md`).

No open-source solver models Regulation 561/2006 natively (research note §7.3). OR-Tools 9.15 (Apache-2.0, cp313 wheels) offers pickup-and-delivery, multiple capacity dimensions, optional visits and warm starts; its break support is only approximate.

## Decision

1. **Stage A (no new dependency).**
   - `wall_clock_safety_s` becomes the budget of the whole job, shared across drivers.
   - The domestic and international passes get separate budget shares.
   - Label dominance and incumbent seeding are added.
   - One `home_requirement()` function replaces the four copies of the home rule.
2. **Cycle-aware objective `profit_v2`.**
   - When the home deadline lies beyond the horizon, the engine replays the return leg under the working-time rules. Infeasible → `HOME_BY_AT_RISK`; feasible → `return_reserve` is charged at `CostModel` cost.
   - Plans are ranked by `cycle_profit = profit − return_reserve`, then by finish time, then by fuel. The lexicographic objectives keep their order, with no weights.
   - A new baseline, `baseline_return_empty`, is added; invariant 15 extends to it.
   - New invariants: P14 (home or a feasible charged return) and P17 (cycle-profit reconstruction).
   - Stored v1 results stay readable (`objectiveVersion`).
3. **Stage B.**
   - A `FleetSelector` port. The existing DFS stays as the default, the test oracle and the fallback.
   - A CP-SAT set-packing model (one Boolean per candidate plan; ≤ 1 per driver; ≤ 1 per offer) solves staged lexicographic objectives with one worker and a fixed seed.
   - Runtime dependency: `ortools` (Apache-2.0), imported lazily.
4. **Stage C (only if the benchmark gate of FEAT-017 passes).**
   - A `CandidateGenerator` port, with the existing per-driver B&B as the default. An OR-Tools RoutingModel PDPTW generator may propose routes for ≥ 20 vans.
   - **Every** generated route is re-scheduled by `ScheduleBuilder` with the real rules and accepted only by `RouteValidator`. Failures are repaired or discarded.
5. **Unchanged.**
   - The engine stays pure.
   - Search and validators stay separate implementations.
   - Validators are never weakened.
   - B&B remains the exact method for small fleets.

## Alternatives

| Alternative | Why not (research note §7.3, weighted matrix) |
|---|---|
| Keep everything as is | p95 172.9 s at defaults; exponential fleet step; plans that strand vans |
| Replace the engine with OR-Tools Routing | EU rules only approximate; loses exactness, golden-case control and explanations; large rewrite |
| CP-SAT for the whole problem | hard to model routing at scale; slower than RoutingModel for routing |
| Timefold | Python support removed in 1.25; would need a JVM sidecar |
| PyVRP / VROOM | EU hours-of-service breaks are an Enterprise feature (PyVRP) or fixed clock windows (VROOM); possible benchmark challengers only |
| Weights or expected future value for the return | not explainable; violates "no weights" (`context.md` Core Domain Rule 13) |

## Consequences

- `context.md` lists OR-Tools as "outside the MVP"; accepting this ADR allows it from Stage B, after a specification approval.
- `context.md` → Optimization Engine Invariants and the default-parameter notes need an update by the owner: the job-level meaning of `wall_clock_safety_s`, and the new invariants P14 and P17.
- Golden case GOLD-012 must be hand-calculated with the real `CostModel` and approved before its test is written.
- Benchmarks record runtime; they never assert it, except the unit test of the job-level budget.
- Risks: CP-SAT determinism needs a single worker; OR-Tools 9.15 has a known Python wrapper bug in `SetAllowedVehiclesForIndex` (#4982), which must not be used; wheel size increases the install.
