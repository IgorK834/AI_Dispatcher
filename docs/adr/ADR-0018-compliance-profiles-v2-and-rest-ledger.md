# ADR-0018: Versioned working-time profiles v2, a shared rule table and a rest ledger

- Status: proposed
- Date: 2026-11-18
- Amends: [ADR-0011](ADR-0011-driver-working-time.md) (the `DriverRules` port and the whole-plan profile choice stay)
- Specification: [FEAT-013](../../specs/FEAT-013-compliance-profiles-v2.md); related: [FEAT-011](../../specs/FEAT-011-driver-rotations-and-availability.md), [FEAT-012](../../specs/FEAT-012-engine-reliability-and-cycle-aware-planning.md)
- Research: [`docs/research/2026-11-17-ai-dispatcher-evolution.md`](../research/2026-11-17-ai-dispatcher-evolution.md) §2.4, §6

## Context

The two v1 profiles live in one class switched by a boolean, with hard-coded minute constants (`compliance/rules.py:56-266`):
- weekly rest is not scheduled; the Monday boundary only resets counters (`rules.py:24-53`);
- `last_weekly_rest_end` never reaches the engine (`optimization/jobs/snapshots.py:156-170`);
- reductions, the 10 h extension, the split break, compensation and the four-week driver return are not modelled;
- the validator reuses the same constants, so a wrong constant passes both.

Since 1 July 2026, vans over 2.5 t in international transport or cabotage fall under Regulation 561/2006 (Art. 2(1)(aa) as inserted by Regulation 2020/1054), including Art. 8(6) (weekly rest within six 24-hour periods), Art. 8(8) (no regular weekly rest in the vehicle) and Art. 8(8a) (driver return within four weeks). The eight-week **vehicle** return was annulled by the CJEU (C-541/20 to C-555/20, 4 October 2024); it is not modelled.

Art. 22 of the Polish Act on Drivers' Working Time (Dz.U. 2026 poz. 477) exempts drivers of goods vehicles ≤ 3.5 t in domestic transport from several provisions that v1 applies. This is UNVERIFIED by a lawyer.

## Decision

1. **Profiles are versioned data plus code.**
   - A frozen `RuleTable` per `profile_id` holds every constant; the rules and the `RouteValidator` read the same table, and the validator keeps its own replay algorithm.
   - The v1 constants move into the table unchanged; v1 results must not change.
2. **New profiles:**
   - `eu561_van_international_v2`: the weekly-rest clock, the 10 h extension, split breaks, reduced daily rest, regular and reduced weekly rest insertion, the compensation ledger, and the four-week return as a `HomeRequirement` kind.
   - `pl_domestic_van_employee_v2`: the Act with art. 22 carve-outs marked; v1's stricter limits become named company-policy parameters (default on).
   - `unsupported_v1`: vehicles > 3.5 t, multi-manning, trailers. These are never optimised.
3. **Conservative use of options.** Reductions and extensions are used only when a plan is otherwise infeasible, and every use is a recorded ledger fact. Art. 12 is never planned. Two consecutive reduced weekly rests are not planned in v2.
4. **Rest ledger in `driver_states`:** last regular and last home weekly rest, reduced-rest counts, extension count, compensation entries with due dates.
5. **Profile version switch.** `COMPLIANCE_PROFILE_VERSION=v1|v2`, default v1 until the owner switches it. Stored plans replay with their own version.
6. **The mandatory notice stays.** The product never claims compliance.

## Alternatives

| Alternative | Why not |
|---|---|
| Patch `rules.py` in place | breaks replay of stored plans and golden cases; no shared constants |
| A third-party rule engine | none found for 561 in Python; adds an unexplained dependency |
| Model every option aggressively (always reduce rests) | not conservative; harder to explain; legal risk |

## Consequences

- Golden cases for v2 (weekly rest abroad, extensions, compensation) need hand calculations and owner approval.
- `context.md` → Core Domain Rules 7–8 must be updated by the owner when v2 becomes the default.
- Legal review (backlog owner action O-21) is required for: in-vehicle rest after the 2020 change, the art. 22 carve-outs, the time base of the 561 week, and 28/7 rotations against Art. 8(8a).
- A migration adds the ledger columns, with human review.
