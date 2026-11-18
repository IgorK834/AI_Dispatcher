---
id: FEAT-015
title: Event-driven evaluation, proposals and one approval service
status: draft
owner: project owner
requirements: [REQ-025, REQ-017, NFR-005, NFR-017]
adrs: [ADR-0006, ADR-0008, ADR-0017]
modules: [optimization.jobs (outbox, worker, job kinds, evaluation, replan, proposals, approval service), freight (outbox events), agents (ApprovalGate uses the approval service), contracts, migrations, web features/approvals]
revision: 1
---

# FEAT-015: Event-driven evaluation, proposals and one approval service

> **Draft, 2026-11-18. Not approved.** It needs the owner's approval of this spec, acceptance of ADR-0017, and the clarification of `context.md` AI rule 3 that ADR-0017 asks for (backlog owner action O-18). After the MVP (phase 2).
> Research behind it: [`docs/research/2026-11-17-ai-dispatcher-evolution.md`](../docs/research/2026-11-17-ai-dispatcher-evolution.md) §7.6, §8.2–8.5, §9.3.
> This feature covers REQ-025 (event-driven mode, post-MVP), which had no specification until now.
>
> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Goal

When an offer is created or changed, or a committed stop is delayed or cancelled, the system evaluates the effect **deterministically**, with the engine and the validators and without an LLM:
- for a new offer, the best feasible insertions after the committed stops of active drivers;
- for a delay, the affected stops, the deadline risk and recovery options.

It stores the result as a **proposal** waiting for a human decision. Every approval, from the chat graph or from the proposal inbox, goes through **one `ApprovalService`**. That service re-validates versions and writes atomically. An LLM may explain a proposal; it never creates, changes or approves one.

## 2. Business context

Today runs start only from chat [`agents/service.py:131-189`], and nothing reacts to new offers or delays. LangGraph Agent Server would need an Enterprise licence, PostgreSQL and Redis (research note §8.1), which contradicts `context.md` constraints 1a and 6. The research note recommends a transactional outbox and job kinds on the existing in-process worker [ADR-0008], with deterministic services and proposals (§8.4).

Requirements:
- REQ-025 (event-driven mode: automatic rating of new offers and an inbox of proposals);
- REQ-017 (human approval);
- NFR-005 (works without an LLM);
- NFR-017 (new: replanning stability).

## 3. Scope / Out of scope

**In scope:**
- **Outbox:** an `outbox_events` table written in the same transaction as offer create, update and import, stop events, and assignment cancel.
- **Worker:** a generalised job table with kinds (`optimize`, `evaluate_offer`, `replan`, `expire_proposals`), leases, priority, attempts and cancel.
- **Services:**
  - `OfferEvaluationService`: insertion after the committed prefix, ranked by Δcycle profit, with a threshold;
  - `ReplanService`: delay or cancellation → impact and recovery options.
- **Proposals:** a `proposals` table and an inbox.
- **`ApprovalService`:** used by the REST approval endpoint and by the graph's ApprovalGate.
- **Expiry:** eager expiry of proposals and agent approval requests.
- **UI:** an approval inbox and alerts (EN/PL).

**Out of scope:**
- Inserting between committed stops (phase 3);
- reassigning committed offers to another driver automatically (a proposal kind `reassign` may be listed but is approved like any other);
- message sending;
- LLM explanation generation beyond the existing `ExplanationService`;
- PostgreSQL / `SKIP LOCKED` (ADR-0002, later);
- new agent tools (FEAT-016).

## 4. Functional requirements

- **FR-1 Outbox.**
  - `outbox_events(id, aggregate_type, aggregate_id, type, payload JSON, created_at, processed_at, attempts)`.
  - The event types are `offer.created`, `offer.updated`, `offer.withdrawn`, `stop.event_recorded`, `assignment.cancelled` and `calendar.changed` (when FEAT-011 is present).
  - Each event is written in the same transaction as the change. The payload holds ids and versions only, never offer text.
- **FR-2 Relay.**
  - A relay step in the worker loop reads unprocessed events in `id` order and enqueues jobs with an **idempotency key** `type:aggregate_id:version`, then marks the events processed.
  - Delivery is at least once; consumers are idempotent.
- **FR-3 Job kinds and claiming.**
  - `optimization_jobs` gains `kind`, `priority` and `lease_until` (or a new generic `jobs` table; OQ-015-01).
  - Claiming uses `BEGIN IMMEDIATE` and an `UPDATE … RETURNING` of the oldest queued job by (priority, id) whose `run_at` is due.
  - Workers extend the lease while running. A reaper requeues expired leases up to `max_attempts` (3, *assumption*), then marks them `failed`.
  - The existing heartbeat recovery becomes the lease mechanism.
- **FR-4 Cancel.**
  - `POST /optimization-jobs/{id}/cancel` sets `cancel_requested`.
  - The engine's elapsed-time callback checks it, and the job ends `cancelled` with its partial result discarded.
  - A queued job is cancelled immediately.
- **FR-5 `OfferEvaluationService.evaluate(offer_id, offer_version)`.**
  - Candidate drivers: on duty, vehicle-compatible, the pickup reachable from their committed end (existing prefilter rules), at most `EVAL_MAX_DRIVERS = 20` nearest by deadhead (*assumption*).
  - For each candidate: build the snapshot with the committed prefix (FEAT-014 FR-8), then try the offer at every feasible position **after** the prefix (pickup and delivery positions), using `build_plan()` [`optimization/engine/schedule.py:380-406`] and the validators.
  - Rank by Δcycle profit (FEAT-012) against the driver's current committed plan, then by finish time, then driver id.
  - Keep proposals with Δ ≥ `EVAL_MIN_DELTA_MINOR` (configurable, default 2,000 = €20, *assumption*), at most `EVAL_TOP_N = 3`.
  - The run is time-boxed (`EVAL_BUDGET_S = 10`). On timeout the proposals carry `truncated = true`.
- **FR-6 `ReplanService.on_stop_event(assignment_id)`.**
  - Replays the committed plan from the actual times.
  - If every remaining window and the home deadline still hold, it stores `impact = none` (no proposal).
  - Otherwise it lists the affected stops (`WINDOW_MISSED`, `HOME_BY_AT_RISK`) and computes up to 3 recovery options:
    - drop one not-yet-picked offer;
    - drop one not-yet-picked offer and give it to another driver (a `reassign` proposal pair);
    - keep the plan and accept the late arrival (shown, never applied automatically).
  - Each option carries Δcycle profit and its binding constraints.
- **FR-7 Proposals.**
  - Each row has `id, kind ∈ {insert_offer, amend_after_delay, reassign}, subject ids, payload (plan diff: kept, added and removed stops; new plan id; Δ values; binding constraint codes), versions digest, status ∈ {open, approved, rejected, expired, superseded}, expires_at, created_at`.
  - The dedup key is `(kind, subject, versions digest)`.
  - A newer event for the same subject marks the open proposal `superseded`.
- **FR-8 `ApprovalService`.**
  - `approve(proposal_or_plan, actor, comment)`:
    1. checks the role;
    2. re-validates every version (FEAT-014 FR-3; also the committed prefix);
    3. writes in one `BEGIN IMMEDIATE` transaction, either `assign_many` or `amend` (the new version of the assignment keeps the committed stops identical);
    4. records the decision and audit events.
  - `reject` records the decision.
  - **The REST endpoint and the LangGraph ApprovalGate call the same service** [`agents/graph.py:451-530`]; the audit events are the same.
- **FR-9 Commitments kept (P16).** For every approved `insert_offer` or `amend_after_delay`, the committed stops that were already executed or approved before stay identical in order, time windows and offers. Only stops after the prefix change.
- **FR-10 Expiry.** A periodic `expire_proposals` job (every 60 s, *assumption*) expires open proposals and agent approval requests past `expires_at`, instead of the lazy expiry inside chat calls [`agents/service.py:265-291`].
- **FR-11 No LLM required.** All of FR-1 … FR-10 run with no model configured. `ExplanationService` may be asked for a proposal's explanation; without a model it returns the template explanation (existing behaviour).
- **FR-12 UI.** An approval inbox (`features/approvals`) lists open proposals and agent approval requests together, with:
  - the kind;
  - a stop diff (kept, added, removed);
  - Δ cycle profit, Δ km and fill before and after;
  - the binding constraints as translated codes;
  - expiry;
  - approve and reject with a comment.
  An alerts panel shows `HOME_BY_AT_RISK`, `WINDOW_MISSED`, failed jobs and expiring proposals. EN/PL; design tokens; the working-time notice; the SYNTHETIC DATA badge.

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| NFR-005 | Works without an LLM | integration test with no model configured: event → proposal → approval |
| NFR-017 | Replanning stability | ≥ 90 % of approved stops unchanged after a 10 % offer-arrival step (benchmark, FEAT-017; recorded) |
| NFR-018 | Evaluation latency | `evaluate_offer` p95 ≤ 10 s for 5 drivers on the reference laptop (recorded) |

## 6. Contracts (API, data/migrations, ports, agent tools)

**API:**

| Method and path | Role | Success | Errors |
|---|---|---|---|
| `GET /proposals?status&kind&cursor` | dispatcher, admin, demo (read) | 200 | — |
| `GET /proposals/{id}` | same | 200 | 404 |
| `POST /proposals/{id}/approve` `{comment?}` | dispatcher, admin | 200 (assignment or amendment) | 409 `PLAN_STALE`, `OFFER_CHANGED`, `CONCURRENT_ASSIGNMENT`, `PROPOSAL_NOT_OPEN`; 403 |
| `POST /proposals/{id}/reject` `{comment?}` | dispatcher, admin | 200 | 409 `PROPOSAL_NOT_OPEN` |
| `POST /optimization-jobs/{id}/cancel` | owner of the job, admin | 202 | 404, 409 `JOB_FINISHED` |
| `GET /alerts?cursor` | dispatcher, admin, demo | 200 | — |

The SSE event `proposal.created` is added to the existing agent event stream or a new `/events` stream (OQ-015-03).

**Data / migrations** (🔒 review):
- `outbox_events`;
- `proposals`;
- `optimization_jobs` + `kind`, `priority`, `lease_until`, `cancel_requested`, `attempts`, `run_at` (or the generic `jobs` table);
- `assignments` + `amended_from_id` (the version chain).

**Ports:** no change.

**Configuration:**
- `EVAL_MAX_DRIVERS=20`, `EVAL_MIN_DELTA_MINOR=2000`, `EVAL_TOP_N=3`, `EVAL_BUDGET_S=10`;
- `PROPOSAL_TTL_MIN=60`, `JOB_LEASE_S=60`, `JOB_MAX_ATTEMPTS=3`.
All are *assumptions*.

**Agent tools:** no new tool (FEAT-016). `assign_plan` keeps its contract but delegates to `ApprovalService.approve`.

## 7. Acceptance criteria

- **AC-FEAT-015-01** [db] Given an offer created through the API, an import that updates an offer, and a cancelled assignment When their transactions commit Then exactly one outbox event per change exists with ids and versions only. When a transaction rolls back Then no event exists.
- **AC-FEAT-015-02** [integration] Given the same outbox event relayed twice (simulated crash before `processed_at`) When the worker runs Then exactly one job and one proposal set exist (idempotency key).
- **AC-FEAT-015-03** [db] Given two worker loops on one SQLite file When they claim jobs concurrently Then no job is claimed twice, and a job whose lease expires is requeued and runs again at most `JOB_MAX_ATTEMPTS` times.
- **AC-FEAT-015-04** [contract] Given a queued job When `cancel` is called Then the job is `cancelled` and never runs. Given a running engine job When `cancel` is called Then it ends `cancelled` within one elapsed-time check, and no result is stored.
- **AC-FEAT-015-05** [integration] Given a driver with an in-progress assignment and a new compatible offer near the last committed stop When `offer.created` is processed Then an `insert_offer` proposal exists for that driver with the offer inserted after the committed prefix, a positive Δ cycle profit ≥ the threshold, and its binding constraints.
- **AC-FEAT-015-06** [property] Given random committed plans and offers When insertion proposals are computed Then every proposal's committed prefix is identical to the current plan's (P16), and every proposed plan passes `RouteValidator`.
- **AC-FEAT-015-07** [integration] Given an offer that fits no driver When it is evaluated Then no proposal is created, and the job result records `NO_FEASIBLE_INSERTION` with the per-driver rejection codes.
- **AC-FEAT-015-08** [integration] Given a dispatched assignment and a stop event `arrived` 4 h after the planned arrival (fixed clock) When `ReplanService` runs Then it reports the affected stops with `WINDOW_MISSED` or `HOME_BY_AT_RISK`, and stores up to 3 `amend_after_delay` options ranked by Δ cycle profit. Given a delay with no effect Then `impact = none` and no proposal.
- **AC-FEAT-015-09** [integration] Given an offer of an assignment that is withdrawn by its source (version bump) When the event is processed Then an `amend_after_delay` proposal without that offer exists, and the old open proposals of that assignment are `superseded`.
- **AC-FEAT-015-10** [agent] Given the chat graph reaching the ApprovalGate and the REST inbox approving a proposal When both approvals succeed Then both call `ApprovalService.approve`, and the audit events have the same types and fields (fake models).
- **AC-FEAT-015-11** [contract] Given an open proposal whose driver state changed after it was created When it is approved Then the answer is `409 PLAN_STALE`, and nothing is written. Given an approved or expired proposal Then `409 PROPOSAL_NOT_OPEN`. Given `demo` Then `403`.
- **AC-FEAT-015-12** [integration] Given an open proposal and an agent approval request past `expires_at` When the `expire_proposals` job runs Then both are `expired` without any chat call.
- **AC-FEAT-015-13** [integration] Given no LLM provider configured When an offer is created, evaluated, proposed and approved through the REST API Then all steps succeed, and the proposal explanation is the template explanation.
- **AC-FEAT-015-14** [e2e] Given an open insertion proposal When the dispatcher opens the inbox in EN and in PL, sees the stop diff and the Δ values, and approves it Then the assignment shows the new stop after the committed stops, and the alert list no longer shows the proposal.

## 8. Edge cases

- **An event storm** (an import of 150 offers): the relay batches up to 50 events per loop. Evaluation jobs get a lower priority than user-started optimisations.
- **An offer that changes again during evaluation:** the proposal's versions digest no longer matches, so it is `superseded` by the next event.
- **SQLite busy:** retry `BEGIN IMMEDIATE` with backoff up to `busy_timeout`; report a `JOB_RETRY` metric.
- **A driver without a committed plan:** insertion falls back to a fresh plan for that driver, with kind `insert_offer` and an empty prefix.
- **A proposal for a driver who goes off duty** (FEAT-011): approval answers `PLAN_STALE`.

## 9. Dependencies

- FEAT-012 (cycle profit), FEAT-014 (lifecycle, committed prefix, staleness), FEAT-011 (optional: `calendar.changed`, `DRIVER_OFF_DUTY`).
- ADR-0006, ADR-0008, ADR-0017 (proposed).
- `context.md` AI rule 3 clarification (owner, O-18).
- Libraries: none new.
- Shared files: `apps/api/migrations/**` (🔒), `contracts/openapi.json`, `apps/web/messages/*.json`.

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| 01, 03 | `apps/api/tests/db/test_outbox.py`, `test_job_claim.py` | temp SQLite file, two processes |
| 02, 05, 07–09, 12, 13 | `apps/api/tests/integration/test_event_pipeline.py` | fixed clock, demo data |
| 04, 11 | `apps/api/tests/api/test_jobs_cancel.py`, `test_proposals.py` | factories |
| 06 | `apps/api/tests/props/test_insertion.py` | Hypothesis |
| 10 | `apps/api/tests/agents/test_approval_service.py` | fake models |
| 14 | `tests/e2e/approvals.spec.ts` | demo data |

## 11. Open questions

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-015-01 | Extend `optimization_jobs` or create a generic `jobs` table? | extend with `kind` (smaller migration) | AC-03 |
| OQ-015-02 | Thresholds and limits (`EVAL_*`, TTL) | values in §6 (*assumptions*) | AC-05 |
| OQ-015-03 | One new SSE stream `/events` or reuse the agent stream? | new `/events` stream, DB-polled like today | AC-14 |
| OQ-015-04 | `context.md` AI rule 3 says writes run only after `interrupt()` in the graph. Does a REST approval of a deterministic proposal through `ApprovalService` satisfy the human-approval rule? | yes; ADR-0017 proposes the wording | all |
| OQ-015-05 | Should `reassign` proposals be in v1? | listed as options but approved one by one; no automatic pairing | AC-08 |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-18 | Initial draft from the research note §8 and §12 (E5) |
