---
id: FEAT-014
title: Assignment integrity, lifecycle and execution events
status: draft
owner: project owner
requirements: [REQ-038, REQ-010, REQ-017]
adrs: [ADR-0002, ADR-0008, ADR-0017]
modules: [optimization.jobs (assignments, snapshots, plans), fleet (driver_states from execution), contracts, migrations, web features/plans, web features/assignments]
revision: 1
---

# FEAT-014: Assignment integrity, lifecycle and execution events

> **Draft, 2026-11-18. Not approved: it needs the owner's approval and a migration review (backlog owner action O-17).** After the MVP (phase 1 for slices 014/1–014/2, phase 2 for the rest).
> Research behind it: [`docs/research/2026-11-17-ai-dispatcher-evolution.md`](../docs/research/2026-11-17-ai-dispatcher-evolution.md) §2.3, §8.4 (questions 5–8), §8.6.
>
> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Goal

**The database guarantees** that an offer is committed to at most one open assignment, and that a driver has at most one assignment in progress. An approval is refused when anything the plan was built on has changed since the job ran:
- an offer version;
- the driver state;
- the rotation or its exceptions.

Assignments have a lifecycle (`planned → dispatched → in_progress → completed`, or `cancelled`). Dispatchers record stop events (arrived, service started, service completed, skipped) with actual times. Completing a stop writes a new driver state, so the next optimisation starts from where the driver really is, and committed stops are treated as a fixed prefix.

## 2. Business context

Verified in code (research note §2.3):
- **The uniqueness guarantee is process-local.** It rests on a `threading.Lock` and an offer compare-and-set [`optimization/jobs/service/__init__.py:880-930`]. The `assignments` table has only a non-unique index [`apps/api/migrations/versions/0001_initial.py:406-432`], so the `IntegrityError → CONCURRENT_ASSIGNMENT` path can never fire.
- **Driver-state changes after the job are not checked.**
- **Cancelling does not bump the offer version** [`:932-955`].
- **Nothing completes.** A driver with an `active` assignment can never get another one [`:828-834`].

These gaps block dynamic offers, delay recovery and continuous planning. Requirements: REQ-038 (new), REQ-010 (no duplicate offers), REQ-017 (human approval).

## 3. Scope / Out of scope

**In scope:**
- An `assignment_offers` table with partial unique indexes; writes inside `BEGIN IMMEDIATE`.
- Staleness checks at approval (offer, driver state, rotation and exceptions digest).
- `cancel()` bumps offer versions.
- The lifecycle states and their endpoints; `stop_events`.
- A driver state derived from execution.
- Committed prefixes in the snapshot builder.
- An assignments list screen with stop recording (EN/PL).

**Out of scope:**
- Driver mobile app and telematics or tachograph ingest (stop events are entered by a dispatcher in v1);
- amending an assignment (FEAT-015/016);
- documents (CMR, POD);
- invoicing;
- automatic ETA notifications to customers.

## 4. Functional requirements

- **FR-1 `assignment_offers`.**
  - One row per (assignment, offer) with a copy of the assignment status.
  - Partial unique index on `offer_id WHERE status IN ('planned','dispatched','in_progress')`.
  - Partial unique index on `assignments(driver_id) WHERE status IN ('dispatched','in_progress')`.
  - Approval inserts the rows inside the transaction that sets the offers to `assigned`. An `IntegrityError` maps to `409 CONCURRENT_ASSIGNMENT`.
- **FR-2 Transactions.** `assign_many`, `cancel` and lifecycle transitions run in `BEGIN IMMEDIATE` transactions (SQLAlchemy `connection.exec_driver_sql("BEGIN IMMEDIATE")` on SQLite; plain `BEGIN` elsewhere). The in-process lock stays as a fast path only.
- **FR-3 Staleness.** At approval, for every plan:
  - each offer version must equal the snapshot's (existing);
  - the driver's latest `driver_states.id` must equal the one in the snapshot;
  - when FEAT-011 is present, `rotationRef` and `exceptionsDigest` must equal the current ones.
  Any mismatch gives `409 PLAN_STALE` with `errors[{code, driverId|offerId, field}]`.
- **FR-4 Cancel.** Cancelling an assignment sets its offers back to `open` **and bumps their `version`**, so plans built on the old version become `OFFER_CHANGED`.
- **FR-5 Lifecycle.** `assignments.status ∈ {planned, dispatched, in_progress, completed, cancelled}`. Allowed transitions:

  | From | To | How |
  |---|---|---|
  | `planned` | `dispatched` | `POST /assignments/{id}/dispatch` |
  | `dispatched` | `in_progress` | first stop event |
  | `in_progress` | `completed` | last stop completed or skipped, or `POST /assignments/{id}/complete` |
  | `planned`, `dispatched` | `cancelled` | `DELETE` (existing cancel) |

  - Anything else gives `409 INVALID_TRANSITION`.
  - Existing `active` rows migrate to `planned`.
  - "Active" in existing code and API means `planned|dispatched|in_progress`. The API keeps accepting the filter `status=active` as that union.
  - Every transition writes an audit event and bumps `version`; `If-Match`-style `version` checks apply to dispatch and complete.
- **FR-6 Stop events.**
  - `POST /assignments/{id}/stop-events` with `{routeStopId, kind ∈ {arrived, service_started, service_completed, skipped}, occurredAt, source = "dispatcher"}`.
  - Rows are append-only.
  - Validation:
    - the stop belongs to the assignment's plan;
    - per stop, kinds follow `arrived → service_started → service_completed`, or `skipped` alone;
    - `occurredAt` is not before the previous event of the assignment, and not more than 15 min in the future (*assumption*, clock skew).
  - A skipped delivery leaves its offer `assigned` and adds the flag `DELIVERY_SKIPPED` for the dispatcher.
- **FR-7 State from execution.**
  - On `service_completed` of the last stop, or on `complete`, the service writes a new `driver_states` row with `source = "execution"`:
    - position = the last completed stop;
    - `available_from` = its `occurredAt`;
    - counters = replayed with the plan's profile from the previous state over the actual timeline (planned durations between events, with actual timestamps);
    - `home_by` unchanged.
  - The replay uses the same `DriverRules` as the validator, and it must equal the validator's counters.
- **FR-8 Committed prefix.**
  - For a driver with a `planned`, `dispatched` or `in_progress` assignment, `build_snapshot` sets `available_from` and the position to the end of the last **not yet completed** committed stop of that plan, with the committed load on board.
  - The committed offers stay excluded from the pool (existing status filter).
  - The rule "no new assignment while one is open" is replaced by "no overlapping open assignments": a new plan must start after the committed end (checked at approval with `CONFLICTING_COMMITMENT`).
- **FR-9 UI.**
  - A new `features/assignments` screen lists assignments with lifecycle chips, filters and actions (dispatch, record stop event, complete, cancel), with confirmation dialogs.
  - The plan screen shows planned vs actual times per stop.
  - EN/PL; design tokens; the working-time notice.

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| NFR-003 | No duplicate commitments | db test with two connections in two processes: exactly one assignment |
| NFR-015 | CRUD conventions | api tests for every new endpoint (`200/201/204/404/409/422`) |
| NFR-008 | Security | role and CSRF tests for every state-changing endpoint |

## 6. Contracts (API, data/migrations, ports, agent tools)

**API** (roles `dispatcher|admin` for writes; `demo` read-only; CSRF + Origin):

| Method and path | Success | Errors |
|---|---|---|
| `POST /assignments` (existing) | 201 | 409 `PLAN_STALE`, `CONCURRENT_ASSIGNMENT`, `OFFER_CHANGED`, `CONFLICTING_COMMITMENT` |
| `POST /assignments/{id}/dispatch` | 200 | 404, 409 `INVALID_TRANSITION`, 409 `VERSION_CONFLICT` |
| `POST /assignments/{id}/complete` | 200 | 404, 409 `INVALID_TRANSITION` |
| `GET /assignments/{id}/stop-events` | 200 | 404 |
| `POST /assignments/{id}/stop-events` | 201 | 404, 409 `INVALID_TRANSITION`, 422 `STOP_EVENT_INVALID` |
| `DELETE /assignments/{id}` (existing cancel) | 204 | 409 `INVALID_TRANSITION` (from `in_progress`) |

`GET /assignments?status=` accepts the new states and `active`.

**Data / migrations** (one Alembic revision with downgrade, human review 🔒):
- `assignments.status` check → the five states; data migration `active → planned`.
- `assignment_offers(assignment_id FK, offer_id FK, status TEXT, PRIMARY KEY(assignment_id, offer_id))`, with a partial unique index on `offer_id WHERE status IN ('planned','dispatched','in_progress')`, backfilled from existing plans.
- A partial unique index on `assignments(driver_id) WHERE status IN ('dispatched','in_progress')`.
- `stop_events(id TEXT PK, assignment_id FK, route_stop_id FK, kind TEXT CHECK, occurred_at, source TEXT, created_by FK users, created_at)`, with an index on `(assignment_id, occurred_at)`.
- Partial indexes are supported by SQLite and PostgreSQL. The SQLAlchemy `Index(..., sqlite_where=..., postgresql_where=...)` form keeps portability.

**Ports:** no change.

**Agent tools:** `assign_plan` keeps its contract. Its error codes gain `PLAN_STALE`, `CONCURRENT_ASSIGNMENT` and `CONFLICTING_COMMITMENT`, which the ApprovalGate already turns into notes [`agents/graph.py:431-448`]. Tests cover the new codes. No new tool.

## 7. Acceptance criteria

- **AC-FEAT-014-01** [db] Given two plans that share one offer, approved at the same moment from two separate processes on one SQLite file When both approvals run Then exactly one assignment exists, and the other request answers `409` with `CONCURRENT_ASSIGNMENT` or `OFFER_CHANGED`.
- **AC-FEAT-014-02** [db] Given an existing open commitment for an offer When a row for the same offer with an open status is inserted directly Then the database raises an integrity error, and the service maps it to `CONCURRENT_ASSIGNMENT`.
- **AC-FEAT-014-03** [db] Given a database with `active` assignments from revision `0001` When the new migration is applied, downgraded and applied again Then the assignments become `planned`, `assignment_offers` is backfilled with one row per committed offer, and the downgrade restores `active`.
- **AC-FEAT-014-04** [contract] Given a plan built from driver state S1 When a new state S2 is posted for that driver and the plan is approved Then the answer is `409 PLAN_STALE` with `field = "driverState"`.
- **AC-FEAT-014-05** [contract] Given FEAT-011 is present and a plan built before an exception was added for its driver When the plan is approved Then the answer is `409 PLAN_STALE` with `field = "rotation"`.
- **AC-FEAT-014-06** [contract] Given an assignment that is cancelled When the old plan for one of its offers, or a plan from an earlier job containing that offer, is approved Then the answer is `409 OFFER_CHANGED`, because the offer version was bumped.
- **AC-FEAT-014-07** [unit] Given every pair of states When a transition is requested Then only the FR-5 transitions succeed, and all others raise `INVALID_TRANSITION`.
- **AC-FEAT-014-08** [contract] Given a `planned` assignment When `dispatch` and then `complete` are called by a dispatcher with CSRF Then the answers are `200` with the new states and version + 1 each time. Without CSRF Then `403`. By `demo` Then `403`.
- **AC-FEAT-014-09** [contract] Given a dispatched assignment When stop events are posted in an invalid order, for a stop of another plan, or 20 min in the future Then the answer is `422 STOP_EVENT_INVALID`. The first valid event moves the assignment to `in_progress`.
- **AC-FEAT-014-10** [integration] Given a driver with an `in_progress` assignment whose first two stops are completed When an optimisation job runs Then the driver's snapshot starts at the end of the last uncompleted committed stop with the committed load on board, and no new plan of that driver overlaps the committed stops.
- **AC-FEAT-014-11** [integration] Given a completed assignment When the last stop is completed Then a new `driver_states` row with `source = "execution"` exists, its counters equal the `RouteValidator` replay of the actual timeline, and the driver can receive a new assignment.
- **AC-FEAT-014-12** [e2e] Given a dispatcher When they dispatch an assignment, record arrival and completion of each stop, and complete it on the assignments screen in EN and in PL Then the lifecycle chips and the planned vs actual times are shown, together with the working-time notice.

## 8. Edge cases

- **A stop event for a cancelled assignment:** `409 INVALID_TRANSITION`.
- **Two dispatchers record the same event:** the second is accepted only if it is valid in order. Duplicates of `kind` for one stop give `422`.
- **Completing with skipped deliveries:** allowed; the skipped offers stay `assigned` with the flag `DELIVERY_SKIPPED`. Reopening them is a dispatcher action (cancel or manual), not automatic.
- **Clock skew** beyond 15 min: rejected (*assumption*).
- **Migration on a large demo database:** the backfill runs in batches of 500.

## 9. Dependencies

- FEAT-004 (jobs, plans, assignments), FEAT-001 (states), FEAT-011 (rotation digest, optional for AC-05), FEAT-012 (none).
- ADR-0002, ADR-0008, ADR-0017 (proposed; lifecycle and events).
- Libraries: none new.
- Shared files: `apps/api/migrations/**` (🔒), `contracts/openapi.json`, `apps/web/messages/*.json`.

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| 01, 02 | `apps/api/tests/db/test_assignment_uniqueness.py` | temp SQLite file, `multiprocessing` with `spawn` |
| 03 | `apps/api/tests/db/test_migrations.py` | a revision-0001 database with active assignments |
| 04–06, 08, 09 | `apps/api/tests/api/test_assignments_lifecycle.py` | factories |
| 07 | `apps/api/tests/unit/jobs/test_assignment_states.py` | — |
| 10, 11 | `apps/api/tests/integration/test_execution_flow.py` | fixed clock |
| 12 | `tests/e2e/assignments.spec.ts` | demo data |

## 11. Open questions

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-014-01 | Keep `status=active` as an alias in the API? | yes, as a union | AC-08 |
| OQ-014-02 | Clock-skew tolerance for stop events | 15 min (*assumption*) | AC-09 |
| OQ-014-03 | May a `planned` assignment be completed without being dispatched? | no | AC-07 |
| OQ-014-04 | What happens to the offers of a skipped delivery? | stay `assigned` + flag; the dispatcher decides | nothing |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-18 | Initial draft from the research note §8.6 and §12 (E4) |
