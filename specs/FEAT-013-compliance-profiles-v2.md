---
id: FEAT-013
title: Working-time profiles v2 — weekly rest, reductions, return obligation and rest ledger
status: draft
owner: project owner
requirements: [REQ-037, REQ-012, REQ-013]
adrs: [ADR-0011, ADR-0018]
modules: [compliance (rules, models, profiles, rule table), optimization.engine (schedule, validators, costs, home), optimization.jobs (snapshots), fleet (driver_states), contracts]
revision: 1
---

# FEAT-013: Working-time profiles v2 — weekly rest, reductions, return obligation and rest ledger

> **Draft, 2026-11-18. Not approved.** It needs the owner to approve it and accept ADR-0018 (backlog owner action O-16). The legal questions of §11 also need professional verification (owner action O-21) before the slices that depend on them start. After the MVP (phase 1 for slice 013/1, phase 2 for the rest).
> Research behind it: [`docs/research/2026-11-17-ai-dispatcher-evolution.md`](../docs/research/2026-11-17-ai-dispatcher-evolution.md) §2.4, §6. EU texts were read from legislation.gov.uk copies of the Official Journal; they must be re-checked against EUR-Lex before approval.
>
> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Goal

The working-time engine knows **when the next weekly rest is due** and never plans past it unless the plan ends at home first. It can use the rule options a van driver really has, recording each use as a fact:
- the 10 h driving extension;
- the 15 + 30 split break;
- the reduced 9 h daily rest;
- reduced weekly rests with compensation.

It inserts weekly rests away from home with their accommodation cost. It tracks the four-week driver-return obligation as a deadline. Rule constants live in a versioned rule table read by both the rules and the validator. The v1 profiles stay for replaying stored plans.

## 2. Business context

Today:
- weekly rest is only a counter reset at Monday 00:00 home time plus an informational marker [`compliance/rules.py:24-53`, `optimization/engine/schedule.py:310-316`];
- `last_weekly_rest_end` is stored but never used [`optimization/jobs/snapshots.py:156-170`];
- reductions, extensions, the split break and the four-week return are not modelled.

Since 1 July 2026, vans over 2.5 t in international transport or cabotage fall under Regulation 561/2006 (Art. 2(1)(aa), as inserted by Regulation 2020/1054). See research note §6.2.

Requirements: REQ-037 (new), REQ-012 (a plan never violates the rules of its profile), REQ-013.

## 3. Scope / Out of scope

**In scope:**
- **Slice 013/1:** the 6 × 24 h weekly-rest clock as a rejection (`WEEKLY_REST_DUE`), with `last_weekly_rest_end` in `DriverState`.
- A versioned rule table shared by the rules and the validator; v1 constants moved into it unchanged.
- Profile `eu561_van_international_v2`:
  - 10 h extension ≤ 2 per week;
  - 15 + 30 split break;
  - reduced daily rest 9 h ≤ 3 between weekly rests;
  - regular (45 h) and reduced (≥ 24 h) weekly rest insertion with the two-week rule;
  - compensation ledger and due dates;
  - the four-week return deadline as a `HomeRequirement` kind `legal_return`.
- Profile `pl_domestic_van_employee_v2`: the Polish Act with art. 22 carve-outs marked per rule, and the v1 constraints kept as named company-policy parameters.
- Profile `unsupported_v1` for cases outside the model.
- Profile selection by vehicle mass, operation type and countries.
- Rest-ledger fields in `driver_states`, and ledger facts on plans.

**Out of scope:**
- the ferry/train rule (Art. 9);
- multi-manning;
- the cabotage ledger;
- posting classification;
- the 48 h average over 4 months (a warning only, phase 3);
- night-work limits;
- planning against Art. 12 (never planned);
- vehicles > 3.5 t (they get `unsupported_v1`);
- tachograph import.

## 4. Functional requirements

- **FR-1 Weekly-rest clock (v1-compatible, slice 013/1).**
  - `DriverState` gains `last_weekly_rest_end`, mapped from `driver_states.last_weekly_rest_end`.
  - The latest weekly-rest start is `last_weekly_rest_end + 144 h` (Art. 8(6): no later than the end of six 24-hour periods).
  - A plan whose activities run past that instant is rejected with `WEEKLY_REST_DUE`, unless the plan (or its return leg, FEAT-012) reaches home before it.
  - A missing value means the conservative assumption `available_from − 0 h`, plus the flag `WEEKLY_REST_UNKNOWN`.
- **FR-2 Rule table.**
  - Constants (minutes, counts, weeks) live in `compliance/profiles/<profile_id>.py` as frozen data (`RuleTable`), referenced by `profile_id`.
  - `PlDomesticRules` and `Eu561Rules` read v1 values from the table.
  - `RouteValidator` reads the same table through `rules_for_profile(...).table`. It keeps its own replay algorithm.
  - Moving the constants must not change any v1 result.
- **FR-3 v2 driving options** (international v2):
  - **Driving extension:** daily driving 9 h, extendable to 10 h at most twice per week (Art. 6(1)).
  - **Split break:** 15 + 30 min is accepted in validation and replay (Art. 7). The planner inserts a single 45 min break by default.
  - **Reduced daily rest:** ≥ 9 h, at most 3 between two weekly rests (Art. 8(4)).
  - **When options are used:** the planner uses the extension and the reduced rest **only when the plan is otherwise infeasible**, at the earliest point that makes it feasible. Each use is recorded as a ledger fact on the plan (`ledgerFacts: [{kind, at, count}]`).
- **FR-4 Weekly rest insertion** (international v2):
  - When the clock (FR-1), weekly driving 56 h, fortnightly 90 h or weekly work 60 h would be exceeded, the planner inserts a **regular weekly rest of 45 h** at the current point.
  - Accommodation is charged for each night (Art. 8(8): regular weekly rest not in the vehicle), unless the point is home.
  - A **reduced weekly rest** (≥ 24 h) is used instead only when:
    - the two-week rule allows it (Art. 8(6): in any two consecutive weeks, two regular, or one regular + one reduced);
    - a regular rest would make the plan infeasible.
  - Two consecutive reduced rests are allowed only under the Art. 8(6) international derogation conditions. These are UNVERIFIED for the planner's data, so v2 does **not** plan two consecutive reduced rests (conservative; OQ-013-03).
- **FR-5 Compensation ledger.**
  - Each reduced weekly rest creates `{week_id, deficit_min, due_by}`, where `due_by` = the end of the third week after the week of the reduction (Art. 8(6)).
  - A plan must schedule the compensation, attached to a rest ≥ 9 h (Art. 8(7)), before `due_by`, or be rejected with `COMPENSATION_DUE`.
  - The ledger is stored in `driver_states.weekly_rest_ledger` (JSON) and replayed by the validator.
- **FR-6 Four-week return.**
  - `last_home_weekly_rest_end` (the end of the last regular or compensatory weekly rest taken at home or at the operational centre) + 28 days gives `HomeRequirement(kind = "legal_return", deadline, hard = true)` (Art. 8(8a)).
  - FEAT-012's `home_requirement()` takes the earliest of all kinds.
  - It is an **employer obligation**; the plan shows it as such.
- **FR-7 Polish domestic v2.**
  - Keeps the v1 limits as named policy parameters `company_policy_break_after_6h_work` and `company_policy_weekly_work_cap_60h` (default on). They are labelled "company policy (conservative)", not "required by the Act", because art. 22 of the Act (Dz.U. 2026 poz. 477) exempts drivers of goods vehicles ≤ 3.5 t in domestic transport from art. 12 ust. 2–3, art. 13 and art. 21 (UNVERIFIED by a lawyer, OQ-013-01).
  - Daily rest 11 h and weekly rest 35 h stay (art. 14).
- **FR-8 Profile selection** (`compliance/profiles.py`), applied per plan:
  - vehicle permissible mass > 3.5 t, multi-manning or a trailer → `unsupported_v1`: the plan is not optimised, rejection `UNSUPPORTED_RULE_PROFILE`;
  - any international point or cabotage, and mass > 2.5 t → `eu561_van_international_v2`;
  - domestic only → `pl_domestic_van_employee_v2`;
  - mass unknown → the international profile plus the flag `MASS_UNKNOWN_STRICTER_PROFILE`.
  - The profile version in use is configured (`COMPLIANCE_PROFILE_VERSION=v1|v2`, default `v1` until the owner switches it).
- **FR-9 v1 replay.** Stored results keep their `profile_id`. The validator replays a v1 plan with the v1 table and a v2 plan with the v2 table.
- **FR-10 Facts for explanations.** Every plan exposes `ledgerFacts`, `weeklyRestDueBy`, `legalReturnDueBy` and `compensationsDue` in its read model, so explanations and agents can cite them (grounding).

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| NFR-003 | 0 plans violating the rules of their profile | validator + property tests (P15) |
| NFR-001 | Determinism | property test |
| NFR-013 | Coverage of `compliance` ≥ 90/85 % | coverage report |

## 6. Contracts (API, data/migrations, ports, agent tools)

**API** (additive):
- `GET /drivers/{id}/state` and `POST /drivers/{id}/state` gain:
  - `lastRegularWeeklyRestEnd`
  - `lastHomeWeeklyRestEnd`
  - `reducedDailyRestsSinceWeekly`
  - `extendedDrivingDaysThisWeek`
  - `weeklyRestLedger: [{weekId, deficitMin, dueBy}]`
  All are optional.
- Plan read models gain `profileVersion`, `ledgerFacts`, `weeklyRestDueBy`, `legalReturnDueBy` and `compensationsDue`.
- New rejection codes: `WEEKLY_REST_DUE`, `COMPENSATION_DUE`, `UNSUPPORTED_RULE_PROFILE`; new flags `WEEKLY_REST_UNKNOWN`, `MASS_UNKNOWN_STRICTER_PROFILE`.

**Data / migrations** (one Alembic revision with downgrade). Columns added to `driver_states`:
- `last_regular_weekly_rest_end`
- `last_home_weekly_rest_end`
- `reduced_daily_rests_since_weekly INTEGER`
- `extended_driving_days_this_week INTEGER`
- `weekly_rest_ledger JSON`

`last_weekly_rest_end` exists already. Vehicles: `permissible_mass_kg INTEGER NULL` if not present (check FEAT-001 §6.1 first; OQ-013-05).

**Ports:** `DriverRules` gains a read-only property `table: RuleTable`. The `advance_*` and `remaining` signatures are unchanged.

**Configuration:** `COMPLIANCE_PROFILE_VERSION` (`v1` default).

**Agent tools:** no change. `check_plan_rules` returns the new facts automatically through the plan read model (FEAT-016 verifies grounding).

## 7. Acceptance criteria

- **AC-FEAT-013-01** [golden] Given a driver whose `last_weekly_rest_end` was 5 days 20 h before `available_from` and an offer that needs 10 h of work When the engine runs Then the offer is rejected with `WEEKLY_REST_DUE`. Given a plan that reaches home 2 h before the latest weekly-rest start Then it is accepted.
- **AC-FEAT-013-02** [unit] Given a `driver_states` row with `last_weekly_rest_end` When the snapshot is built Then `DriverState.last_weekly_rest_end` equals it. Given a null value Then the flag `WEEKLY_REST_UNKNOWN` is on the driver and the conservative assumption of FR-1 is used.
- **AC-FEAT-013-03** [property] Given random snapshots When plans are produced Then no plan has an activity after `last_weekly_rest_end + 144 h` unless a weekly rest is scheduled before it or the plan is at home before it (P15).
- **AC-FEAT-013-04** [unit] Given a hand-crafted plan that runs past the weekly-rest clock When `RouteValidator` checks it Then it reports `WEEKLY_REST_DUE`.
- **AC-FEAT-013-05** [golden] Given GOLD-001 … GOLD-011 and P1–P13 When the v1 constants are read from the rule table Then every result is identical.
- **AC-FEAT-013-06** [unit] Given a test rule table with a changed daily driving limit When both the rules and the validator use it Then both apply the changed limit (one source of constants).
- **AC-FEAT-013-07** [golden] Given an international plan that is infeasible with 9 h of daily driving and feasible with 10 h When the v2 profile plans it Then exactly one extension is used and recorded in `ledgerFacts`. Given a third extension needed in the same week Then the plan is rejected.
- **AC-FEAT-013-08** [unit] Given a plan with a 15 min break followed by a 30 min break after 4 h 30 min of driving When the v2 validator checks it Then it is valid. The planner, given the same input, inserts one 45 min break.
- **AC-FEAT-013-09** [unit] Given three reduced daily rests since the last weekly rest When a fourth would be needed Then the v2 planner uses a regular 11 h rest or rejects the plan.
- **AC-FEAT-013-10** [golden] Given a 4-day international tour that reaches the weekly-rest clock abroad When the v2 profile plans it Then a regular 45 h weekly rest is inserted at that point, with accommodation cost for each night, and the validator accepts the plan (a new golden case approved by the owner).
- **AC-FEAT-013-11** [unit] Given a reduced weekly rest of 24 h in week W When the ledger is updated Then an entry `{week W, deficit 21 h, dueBy end of week W+3}` exists.
- **AC-FEAT-013-12** [unit] Given an open compensation due in 2 days and a plan that schedules no rest ≥ 9 h + deficit before it When the plan is finished Then it is rejected with `COMPENSATION_DUE`.
- **AC-FEAT-013-13** [unit] Given `last_home_weekly_rest_end` 25 days ago and a rotation deadline in 10 days When `home_requirement()` runs Then the deadline is 3 days from now, with `kind = "legal_return"`.
- **AC-FEAT-013-14** [unit] Given the table of cases mass ∈ {2,400; 3,200; 3,500; 7,500; unknown} kg × {domestic, international, cabotage} × {hire-or-reward} When the profile is selected Then the result matches FR-8, including `unsupported_v1` for 7,500 kg and the flag for unknown mass.
- **AC-FEAT-013-15** [golden] Given a stored v1 result When it is read and validated after v2 is introduced Then it is replayed with the v1 table and stays valid, with `profileVersion = "v1"`.
- **AC-FEAT-013-16** [db] Given the migration When it is applied, downgraded and applied again Then the new `driver_states` columns exist after each upgrade, and existing rows keep their values.
- **AC-FEAT-013-17** [unit] Given the PL domestic v2 profile with `company_policy_break_after_6h_work = false` When a 7 h domestic work block is planned Then no break is forced by the profile, and the plan carries the policy label in its facts.

## 8. Edge cases

- **The week boundary inside an activity:** as in v1 (AC-FEAT-003-25).
- **The time base of the 561 week:** the code uses the home time zone; tachographs record UTC (UNVERIFIED, OQ-013-02). v2 makes the time base a table parameter.
- **A weekly rest that spans two weeks** counts in one week only (Art. 8(9)). The ledger assigns it to the week where it started.
- **An Art. 12 exceedance:** never planned; a stored state that reports one is accepted as history only.
- **A home point equal to the operational centre:** one point in v2. A separate operational centre is phase 3.

## 9. Dependencies

- FEAT-003 (rules, validators), FEAT-012 (`home_requirement()`, return replay), FEAT-011 (rotation deadlines; the deadline kinds are combined in FEAT-012).
- ADR-0011 and ADR-0018 (proposed).
- Owner action O-21 (legal review) for FR-4 (in-vehicle reduced rest), FR-6 and FR-7 before their slices start.
- Libraries: none new.
- Shared files: `apps/api/migrations/**` (🔒), `contracts/openapi.json`, `specs/golden/**` (🔒).

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| 01, 07, 10, 15 | `apps/api/tests/golden/test_gold_compliance_v2.py` | new GOLD-013 … 015 (owner-approved) |
| 02, 04, 06, 08, 09, 11–14, 17 | `apps/api/tests/unit/compliance/test_rules_v2.py`, `test_rule_table.py`, `test_profile_selection.py` | factories |
| 03 | `apps/api/tests/props/test_engine_invariants.py` (P15) | Hypothesis |
| 05 | existing golden and props suites | unchanged |
| 16 | `apps/api/tests/db/test_migrations.py` | fresh SQLite file |

## 11. Open questions

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-013-01 | Are the 6 h break and the 60 h weekly cap legally required for domestic vans ≤ 3.5 t, or only conservative (art. 22 of the Act)? | keep them as default-on company policy | AC-17 |
| OQ-013-02 | Time base of the 561 week and the 6 × 24 h clock (UTC or local) | home time zone as today; parameter in the table | AC-03 |
| OQ-013-03 | May the planner use two consecutive reduced weekly rests abroad (Art. 8(6) derogation)? | no (conservative) | AC-10, 11 |
| OQ-013-04 | May a reduced weekly rest or a daily rest be taken in a van with a sleeper cab after the 2020 change to Art. 8(8)? | no; accommodation is charged unless at home | AC-10 |
| OQ-013-05 | Where does vehicle permissible mass come from (field exists or not)? | add a nullable `permissible_mass_kg`; demo vans 3,500 | AC-14 |
| OQ-013-06 | Should `COMPLIANCE_PROFILE_VERSION` default to v2 once all slices are merged? | owner decision after the golden cases pass | nothing |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-18 | Initial draft from the research note §6 and §12 (E3) |
