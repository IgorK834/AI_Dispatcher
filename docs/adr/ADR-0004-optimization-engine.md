# ADR-0004: Optimisation engine — Branch-and-Bound per driver, exact fleet assignment, independent validators

- Status: accepted (2026-11-11)
- Date: 2026-11-09

## Context

For one driver the problem is a selective pickup-and-delivery problem with time windows and profits over a multi-day horizon: consolidated loads, chains of orders, two-dimensional capacity (pallet equivalents and kg), working-time rules and a return-home deadline. For the fleet it is an assignment (set packing): each offer with at most one driver, each driver with at most one plan. The scale is small — 5 drivers, a pool of at most 60 offers per driver, at most 6 offers in a plan — and the result must be deterministic, explainable and verifiable, because agents and the UI present its numbers as facts. Source: [`docs/report.md`](../report.md) §18, §19.

## Decision

- **Decomposition.** (1) Per driver and per objective, a custom **Branch-and-Bound** over route labels generates the top-K plans with distinct offer sets. (2) An **exact search** over combinations of plans (depth-first with conflict pruning) picks the fleet assignment. With 5 drivers and ≤ 10 plans each there are at most 11⁵ ≈ 161 thousand combinations.
- **Three objectives, lexicographic, no weights:** `profit`, `fastest`, `fuel` ([`context.md`](../../context.md) → Core Domain Rules 13).
- **Pure engine.** No IO; it receives a snapshot including the travel matrix. Working-time logic is reached only through the `DriverRules` port (ADR-0011).
- **Independent verification.** `RouteValidator` and `FleetValidator` re-check every result; they share only data models, `CostModel` and `DriverRules` with the search. A brute-force oracle proves optimality on small instances in property tests.
- **Baselines** (best single offer per driver; greedy insertion) are computed for comparison.
- **Budgets:** a node budget per driver and a wall-clock safety limit; a truncated result is flagged.

## Alternatives

Comparison from report §18.2:

| Approach | Role / reason |
|---|---|
| Greedy (cheapest insertion) | not exact; kept as a **baseline** |
| Brute force | only feasible for tiny instances; kept as the **test oracle** |
| **B&B over route labels + exact combination search** | **chosen** for the MVP |
| CP-SAT (OR-Tools) | post-MVP for more than about 10 drivers (set-packing model); adds a heavy dependency and a modelling layer that is harder to explain and to test against invariants within the deadline |
| OR-Tools Routing (multi-vehicle PDPTW) | post-MVP benchmark; working-time rules with inserted breaks and two legal profiles are awkward to express; less control over determinism and explanations |
| Metaheuristics | unnecessary at this scale; non-deterministic without care; no optimality guarantee |

## Consequences

- Full control over rules, tie-breaking and explanations; results are reproducible.
- Performance is a risk in pure Python (R4). Target: p95 ≤ 15 s for the fleet on a typical laptop, measured by a benchmark. Fallback parameters are defined (fewer offers per plan, shorter horizon, smaller K); label dominance is P1.
- The engine does not scale to large fleets; ADR to be revisited when the fleet exceeds about 10 drivers.
- The `fastest` and `fuel` objectives, as defined, tend to prefer short plans; this is recorded as an open question in FEAT-003 (OQ-003-13).
- Validators must never be weakened to make a result pass; a validation failure of an engine result is a bug.
