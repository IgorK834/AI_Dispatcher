---
id: FEAT-011
title: Driver rotations, calendar exceptions and derived availability
status: draft
owner: project owner
requirements: [REQ-035, REQ-008, REQ-013]
adrs: [ADR-0010, ADR-0011]
modules: [fleet (domain/rotation, repository, service, api), optimization.jobs (snapshots), web features/fleet, web features/calendar]
revision: 1
---

# FEAT-011: Driver rotations, calendar exceptions and derived availability

> **Draft, 2026-11-18. Not approved: nothing in this specification may be implemented before the owner sets `status: approved` (backlog owner action O-14).** After the MVP (phase 1 of the evolution backlog, `backlog.md` §9).
> Research behind it: [`docs/research/2026-11-17-ai-dispatcher-evolution.md`](../docs/research/2026-11-17-ai-dispatcher-evolution.md) §5.
> Numbers marked *assumption* are configurable modelling choices, not facts. Demo data stays synthetic (`is_synthetic = true`).
>
> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Goal

A dispatcher can give each driver a working pattern: 14 days on / 7 at home, 21/7, Monday–Friday, or any custom cycle, plus leave, unavailability, training, extra duty and vehicle service. The system derives each driver's **duty windows** and **home requirement** (where and by when the driver must be back) for up to 63 days.

The optimisation snapshot uses these windows instead of a single manually entered `available_from` / `home_by`:
- a driver who is off duty is excluded with a reason;
- a driver on duty is planned only inside the window.

The fleet calendar shows the windows. A driver without a rotation behaves exactly as today.

**A rotation is an operational availability rule, never a legal permission.** Every limit of the working-time profiles still applies inside a duty window.

## 2. Business context

Today availability is one `available_from` and one `home_by` per `driver_states` row [`optimization/jobs/snapshots.py:116, 124`]. The demo generator gives every driver "next Friday 18:00" [`fleet/generator.py:61-66`]. Long-distance van work runs on rotations; after 1 July 2026, international van drivers also fall under Regulation 561/2006, including the four-week driver-return rule (Art. 8(8a)). See the research note §3.2 and §6.2.

Without a rotation model the planner cannot:
- keep a return obligation that lies beyond the 7-day horizon;
- know that a driver is at home next week;
- warn about a pattern that cannot meet the four-week return.

Requirements: REQ-035 (new), REQ-008 (fleet view: availability), REQ-013 (return to base).

## 3. Scope / Out of scope

**In scope:**
- Rotation patterns as reusable, versioned templates made of `on` / `off` segments.
- Driver rotations: a pattern plus an anchor date and a validity period, versioned per driver.
- Calendar exceptions for drivers and vehicles.
- A pure function that derives duty windows; the `HomeRequirement` value object for the rotation and exception parts.
- CRUD and availability REST endpoints.
- Snapshot integration: availability start, deadline, off-duty exclusion, rotation versions in the snapshot digest.
- Demo rotations in the fleet generator.
- A rotation editor and a read-only fleet calendar in the web app (EN/PL).

**Out of scope:**
- Automatic rotation generation.
- Driver preferences as planning inputs (AI Act Annex III 4(b) risk, research note §6.6).
- Multi-manning.
- Vehicle handover.
- Payroll.
- The legal-return deadline from the rest ledger (FEAT-013).
- The cost of the way home beyond the horizon (FEAT-012).
- Rejecting a stale plan at approval (FEAT-014; this feature only adds the versions to the digest).

## 4. Functional requirements

- **FR-1 Pattern.**
  - Fields: `name`, `segments` (list of `{kind: on|off, days: 1…42}`), `dutyStartLocal` (default 06:00), `homeFromLocal` (default 18:00), `returnBufferMin` (0…720, default 0), `version`.
  - The cycle length is Σ days, 2…63.
  - At least one `on` and one `off` segment.
  - Changing a pattern creates a new version; drivers keep the version they reference until their rotation is updated.
- **FR-2 Driver rotation.**
  - Fields: `driverId`, `patternId`, `patternVersion`, `anchorDate` (local date in the driver's home time zone, first `on` day of cycle 0), `validFrom`, `validTo|null`, `version`.
  - The validity periods of one driver never overlap.
  - A new rotation version closes the previous one at its `validFrom`.
- **FR-3 Calendar exception.**
  - Fields: `subjectType ∈ {driver, vehicle}`, `subjectId`, `kind ∈ {leave, unavailable, training, extra_duty, vehicle_service, home_by_override}`, `startAt < endAt` (≤ 90 days), `noteCode` (optional enum-like code; **no free text and no health reason**), `version`.
  - Exceptions of the same subject and kind do not overlap.
- **FR-4 Windows** (pure, `fleet/domain/rotation.py`).
  - For each cycle *k*: day = `anchorDate + k × L`. For every `on` segment, a window starts at `dutyStartLocal` on its first day, and `homeFrom` = `homeFromLocal` on its last day.
  - `endAt = homeFrom − returnBufferMin`.
  - Local times are converted to UTC with `zoneinfo` in the driver's home zone. In a DST gap or fold, `fold=0` is used.
- **FR-5 Exceptions on windows**, applied in a fixed order:
  1. `extra_duty` adds a window, or extends one that touches it;
  2. `leave`, `unavailable` and `training` subtract their interval, splitting a window if needed;
  3. `home_by_override` caps `endAt`.
  - Windows shorter than `MIN_WINDOW_MIN = 120` (*assumption*) are dropped.
  - Output is sorted by `startAt`, then window id.
- **FR-6 Vehicle exceptions.** A `vehicle_service` exception that overlaps a window makes the driver of that vehicle unavailable for the overlap.
- **FR-7 Legacy fallback.** A driver without a valid rotation at the requested time gets one window `[state.available_from, state.home_by]` with `source = "legacy_state"`. If `home_by` is null, the window ends at `reference_time + horizon_days`, as today.
- **FR-8 HomeRequirement** (rotation part).
  - `deadline` = the earliest of:
    - the current window `endAt`;
    - the start of the next blocking exception;
    - the latest `driver_states.home_by`, when set (it stays a manual override).
  - `point` = driver home.
  - `kind ∈ {rotation_end, exception, manual_override}`; `hard = true`.
  - `explainCode` ∈ {`HOME_PERIOD_STARTS`, `EXCEPTION_STARTS`, `MANUAL_HOME_BY`}.
  - FEAT-012 owns the single engine function that consumes it; FEAT-013 adds `legal_return`.
- **FR-9 Return-period warning.** If a pattern's longest run of `on` days plus the gap to the next home period exceeds 28 days, the API returns the warning `ROTATION_EXCEEDS_RETURN_PERIOD`. A rotation using that pattern can be saved only with `acknowledgeWarnings: true`; the acknowledgement is audited.
- **FR-10 Commitment conflict.** Creating or changing a rotation or exception that makes an `active` assignment's plan end after the new `endAt`, or start inside a removed interval, returns `409 COMMITMENT_CONFLICT` listing the assignment ids. An `admin` may pass `force: true`; the change is then saved and an audit event `rotation.conflict_forced` is written.
- **FR-11 Snapshot integration** (`optimization/jobs/snapshots.py::build_snapshot`):
  - `available_from = max(state.available_from, window.startAt)`;
  - `home_by = HomeRequirement.deadline`;
  - a driver with no window intersecting `[reference_time, reference_time + horizon_days]` is not optimised and gets the rejection `DRIVER_OFF_DUTY` in the job result (instead of being skipped silently);
  - the snapshot stores `rotationRef` (`rotationId@version`, `patternId@version`) and an `exceptionsDigest` per driver, so they are part of the snapshot SHA-256.
- **FR-12 Availability read model.**
  - `GET /drivers/{id}/availability?from&to` returns windows, the home requirement and warnings for ≤ 63 days.
  - `GET /fleet/availability?from&to&cursor` returns the same per driver (≤ 100 drivers per page) plus active assignments as intervals, for the calendar.
- **FR-13 Generator.** `fleet-generator` assigns demo rotations deterministically per seed: drivers 1–2 Mon–Fri `[on 5, off 2]`, drivers 3–4 `[on 14, off 7]`, driver 5 `[on 21, off 7]`, anchors derived from the reference date. Every row is marked synthetic (`source = 'generated_mock'`).
- **FR-14 UI.**
  - A rotation editor in the driver form: choose or create a pattern, set the anchor, see a 63-day preview, and the FR-9 warning with an acknowledgement checkbox.
  - A fleet calendar page (`features/calendar`): drivers × 21/42/63 days with bands for duty, home period, exception and assignment, plus a deadline marker. Keyboard navigable, Radix primitives, design tokens only, EN/PL, the working-time notice and the SYNTHETIC DATA badge.

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| NFR-001 | Determinism of window derivation | property test: identical inputs → identical output |
| NFR-011 | Data minimisation: exceptions carry no health data | schema has no free-text field; security test |
| NFR-020 | Window derivation is cheap | 100 drivers × 63 days computed in ≤ 200 ms on the reference laptop (recorded, not asserted) |

## 6. Contracts (API, data/migrations, ports, agent tools)

**API** (camelCase JSON; problem+json errors; roles: read `dispatcher|admin|demo`, write `dispatcher|admin`; CSRF + Origin on writes):

| Method and path | Success | Errors |
|---|---|---|
| `GET /rotation-patterns`, `POST /rotation-patterns` | 200 list, 201 + `Location` | 422 `ROTATION_PATTERN_INVALID` |
| `GET/PATCH/DELETE /rotation-patterns/{id}` | 200, 200 (new version), 204 | 404, 409 `PATTERN_IN_USE` (delete), 409 `VERSION_CONFLICT` |
| `GET /drivers/{id}/rotations`, `POST /drivers/{id}/rotations` | 200, 201 | 409 `ROTATION_OVERLAP`, 409 `COMMITMENT_CONFLICT`, 422 `ROTATION_WARNING_NOT_ACKNOWLEDGED` |
| `GET/POST /calendar-exceptions`, `GET/PATCH/DELETE /calendar-exceptions/{id}` | 200, 201, 200, 204 | 422 `EXCEPTION_INVALID`, 409 `EXCEPTION_OVERLAP`, 409 `COMMITMENT_CONFLICT` |
| `GET /drivers/{id}/availability?from&to` | 200 | 422 `RANGE_TOO_LONG` (> 63 days) |
| `GET /fleet/availability?from&to&cursor` | 200 | 422 `RANGE_TOO_LONG` |

Response example: research note §5.12. `force` and `acknowledgeWarnings` are body fields; `force` needs the `admin` role.

**Data / migrations** (one new Alembic revision with downgrade; SQLite-portable; `context.md` → Data Model):
- `rotation_patterns(id TEXT PK, name TEXT, segments JSON, duty_start_local TEXT, home_from_local TEXT, return_buffer_min INTEGER, version INTEGER, is_synthetic BOOLEAN, created_at, updated_at, deleted_at)`.
- `driver_rotations(id TEXT PK, driver_id FK drivers, pattern_id FK rotation_patterns, pattern_version INTEGER, anchor_date TEXT, valid_from, valid_to, version INTEGER, warnings_acknowledged JSON, created_at)`, unique `(driver_id, valid_from)`.
- `calendar_exceptions(id TEXT PK, subject_type TEXT CHECK IN ('driver','vehicle'), subject_id TEXT, kind TEXT CHECK, start_at, end_at, note_code TEXT, version INTEGER, created_at, updated_at, deleted_at)`, index `(subject_type, subject_id, start_at)`.
- `optimization_jobs.request` snapshot JSON gains per-driver `rotationRef` and `exceptionsDigest`. This is not a new column.

**Ports:** no change.

**Configuration:** `AVAILABILITY_MAX_RANGE_DAYS=63`, `MIN_WINDOW_MIN=120` (*assumption*).

**Agent tools:** no change in this feature. `driver_calendar` is specified in FEAT-016.

## 7. Acceptance criteria

- **AC-FEAT-011-01** [unit] Given pattern `[on 14, off 7]` with defaults, anchored on 2026-11-02 for a driver in `Europe/Warsaw` When windows are computed from 2026-11-02 to 2027-01-03 Then exactly three windows exist, with `homeFrom` at 18:00 local on 2026-11-15, 2026-12-06 and 2026-12-27, and starts at 06:00 local on 2026-11-02, 2026-11-23 and 2026-12-14.
- **AC-FEAT-011-02** [property] Given any valid pattern, anchor, exceptions and range When windows are computed Then they are sorted, pairwise disjoint and inside the range, every `endAt ≤ homeFrom`, and repeating the computation gives an identical result.
- **AC-FEAT-011-03** [unit] Given a window that spans the DST change of 2027-03-28 in `Europe/Warsaw` When it is computed Then `startAt` and `homeFrom` keep their local times, and their UTC offsets differ by one hour.
- **AC-FEAT-011-04** [unit] Given a 14-day window and an `unavailable` exception on days 5–6 When windows are computed Then two windows remain around the exception. Given an `extra_duty` exception on an off day Then one additional window is returned. Given a `home_by_override` Then the window `endAt` equals the override.
- **AC-FEAT-011-05** [unit] Given a `vehicle_service` exception on the driver's vehicle overlapping a window When availability is computed Then the overlap is removed from that driver's window.
- **AC-FEAT-011-06** [unit] Given a driver without a rotation When windows are computed Then one window `[available_from, home_by]` with `source = "legacy_state"` is returned, and `HomeRequirement.kind = "manual_override"` when `home_by` is set.
- **AC-FEAT-011-07** [unit] Given pattern `[on 28, off 7]` When it is validated Then the warning `ROTATION_EXCEEDS_RETURN_PERIOD` is returned. Given `[on 21, off 7]` or `[on 5, off 2]` Then there is no warning.
- **AC-FEAT-011-08** [contract] Given the pattern endpoints When a pattern is created, read, patched and deleted Then the answers are `201` + `Location`, `200`, `200` with `version + 1`, and `204`; deleting a pattern used by a rotation answers `409 PATTERN_IN_USE`; an invalid segment list answers `422 ROTATION_PATTERN_INVALID`.
- **AC-FEAT-011-09** [contract] Given a driver with a rotation valid from 2026-11-02 When a second rotation with an overlapping validity is posted Then the answer is `409 ROTATION_OVERLAP`. When a rotation with a warned pattern is posted without `acknowledgeWarnings` Then the answer is `422 ROTATION_WARNING_NOT_ACKNOWLEDGED`.
- **AC-FEAT-011-10** [contract] Given an `active` assignment whose plan ends on Friday When an exception `unavailable` from Thursday is posted Then the answer is `409 COMMITMENT_CONFLICT` with the assignment id. With `force: true` by an `admin` Then `201` and an audit event `rotation.conflict_forced`. With `force: true` by a `dispatcher` Then `403`.
- **AC-FEAT-011-11** [db] Given the new migration When it is applied, downgraded and applied again on a fresh SQLite file Then all three tables, the unique key and the index exist after each upgrade and are gone after the downgrade.
- **AC-FEAT-011-12** [contract] Given the exception schema When a request contains an unknown field such as a free-text reason Then it is rejected with `422`, and no column of `calendar_exceptions` can hold free text other than `note_code` from a fixed list.
- **AC-FEAT-011-13** [contract] Given a driver with a 14/7 rotation When `GET /drivers/{id}/availability` is called for 63 days Then the windows, `homeRequirement` and `warnings` match the pure function. For 64 days Then the answer is `422 RANGE_TOO_LONG`.
- **AC-FEAT-011-14** [contract] Given 5 drivers When `GET /fleet/availability` is called for 21 days Then every driver appears once with windows, exceptions and active assignment intervals, and the cursor pagination returns no duplicates.
- **AC-FEAT-011-15** [integration] Given a driver whose next window starts after `reference_time + horizon_days` When an optimisation job runs Then that driver has no plan, and the job result lists the rejection `DRIVER_OFF_DUTY` for the driver.
- **AC-FEAT-011-16** [integration] Given a driver on duty with a window ending inside the horizon When an optimisation job runs Then the snapshot's `home_by` equals the window `endAt`, `available_from` equals `max(state.available_from, window.startAt)`, and the snapshot holds `rotationRef` and `exceptionsDigest`. Changing an exception changes the snapshot digest.
- **AC-FEAT-011-17** [golden] Given drivers without rotations When GOLD-001 … GOLD-011 and the engine property tests run Then every result is unchanged.
- **AC-FEAT-011-18** [property] Given any seed When the fleet generator runs Then drivers 1–2 have Mon–Fri, 3–4 have 14/7 and driver 5 has 21/7 rotations, all rows are synthetic, and the output is identical for the same seed and reference date.
- **AC-FEAT-011-19** [e2e] Given a logged-in dispatcher When they create a 14/7 rotation in the driver form and open the fleet calendar Then the duty and home bands appear for that driver in EN and in PL, together with the working-time notice.
- **AC-FEAT-011-20** [unit] Given the calendar component When it is rendered with windows, exceptions and assignments Then every band has an accessible label, the arrow keys move between days, and no text is hard-coded (all keys exist in `en.json` and `pl.json`).

## 8. Edge cases

- **The anchor date lies in the future.** There are no windows before it. The legacy fallback does not apply while a rotation is valid.
- **`validTo` cuts a cycle.** Windows end at `validTo`; the next rotation starts its own cycle.
- **An exception straddles two windows.** Both windows are clipped.
- **A DST gap at `dutyStartLocal`** (e.g. 02:30). `fold=0` gives the time after the gap; this is covered by a test.
- **A driver without a home time zone.** It is derived from the home country as today (`timezone_for_country`). If unknown, use `UTC` and add the flag `TIMEZONE_DEFAULTED`.
- **The driver is mid-trip when the window ends.** The plan must end by `endAt` anyway (hard). The dispatcher can add `extra_duty`.
- **A vehicle shared by two drivers.** This is not supported in v1 (vehicles are 1:1). The second assignment of a vehicle is rejected as today.

## 9. Dependencies

- Specifications: FEAT-001 (drivers, states), FEAT-003 (snapshot model, unchanged engine), FEAT-005 (design system and i18n).
- FEAT-012 RP-104 provides the single `home_requirement()` used by the engine. Slice 011/4 depends on it.
- Libraries: none new (`zoneinfo` from the standard library).
- Shared files: `contracts/openapi.json`, `apps/api/migrations/**` (🔒), `apps/web/messages/*.json`.

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| 01–07 | `apps/api/tests/unit/fleet/test_rotation_windows.py` | hand-written patterns and anchors |
| 02 | `apps/api/tests/props/test_rotation_windows.py` | Hypothesis strategies for patterns, anchors and exceptions |
| 08–10, 13, 14 | `apps/api/tests/api/test_rotations.py`, `test_calendar_exceptions.py`, `test_availability.py` | factories |
| 11 | `apps/api/tests/db/test_migrations.py` (extend) | fresh SQLite file |
| 12 | `apps/api/tests/security/test_calendar_exceptions_schema.py` | — |
| 15, 16 | `apps/api/tests/integration/test_snapshot_rotations.py` | seeded demo data with a fixed clock |
| 17 | existing golden and props suites | unchanged |
| 18 | `apps/api/tests/props/test_fleet_generator.py` (extend) | seeds |
| 19 | `tests/e2e/rotations.spec.ts` | demo account |
| 20 | `apps/web/src/features/calendar/*.test.tsx` | MSW handlers from the OpenAPI schema |

## 11. Open questions

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-011-01 | Defaults for `dutyStartLocal` / `homeFromLocal` | 06:00 / 18:00 local | AC-01 |
| OQ-011-02 | Is the FR-9 threshold 28 days right, or should it depend on the rest ledger (FEAT-013)? | 28 days as a static warning; FEAT-013 adds the dynamic deadline | AC-07 |
| OQ-011-03 | May a `dispatcher` force a commitment conflict, or only an `admin`? | only `admin` | AC-10 |
| OQ-011-04 | Should home bases be stored at city precision only (data minimisation)? | keep today's coordinates; review with O-21 | nothing |
| OQ-011-05 | Should `home_by` stay editable on `driver_states` once rotations exist? | yes, as a manual override (`kind = manual_override`) | AC-06 |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-18 | Initial draft from the research note §5 |
