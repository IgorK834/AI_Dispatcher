---
id: FEAT-016
title: Agent tools for calendars, insertion, cycle comparison and amendments
status: draft
owner: project owner
requirements: [REQ-040, REQ-015, REQ-017, REQ-018, NFR-004, NFR-012]
adrs: [ADR-0006, ADR-0013, ADR-0017]
modules: [agents (tools/registry, tools/contracts, graph, service, prompts), evals]
revision: 1
---

# FEAT-016: Agent tools for calendars, insertion, cycle comparison and amendments

> **Draft, 2026-11-18. Not approved.** New tools, allowlists and prompt versions need the owner's approval, plus an agreed `ai-evals` token budget (backlog owner action O-19). After the MVP (phase 2).
> Research behind it: [`docs/research/2026-11-17-ai-dispatcher-evolution.md`](../docs/research/2026-11-17-ai-dispatcher-evolution.md) §8.
> **No new runtime agent.** The four existing agents get new read tools. The only new write tool runs from the ApprovalGate after `interrupt()`.
>
> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Goal

In chat, the dispatcher can ask:
- "when must D3 be home and what is left of their hours?";
- "where would this new offer fit?";
- "compare A, B, B+C and going home empty for D2".

The agents answer from deterministic tool facts that pass the GroundingGuard. An approved amendment of an active assignment goes through the same interrupt and approval path as `assign_plan`.

Tools return job handles instead of blocking for 60 s. A killed run no longer blocks its thread. Live runs fit a budget measured from real runs. Optionally, an evaluated experiment compares a single dispatcher agent with tools against today's supervisor.

## 2. Business context

The current tools cannot see rotations, insertions or cycle values [`agents/tools/registry.py:293-693`]:
- The optimise tools pass no horizon and wait a hard 60 s [`:467, 496-541`].
- Live runs need 300 s / 40 steps to reach approval (`evals/README.md`) and cost 50,000–76,000 tokens (development log P13).
- There is no recovery for a run that was running at a crash [`agents/service.py:32, 152-155`].

Requirements:
- REQ-040 (new);
- REQ-015, REQ-017, REQ-018;
- NFR-004 (bounded runs), NFR-012 (costs).

## 3. Scope / Out of scope

**In scope:**
- Read tools: `driver_calendar` (Fleet & Compliance), `evaluate_insertion` and `compare_cycle_options` (Route Planner).
- Write tool `amend_assignment`: no role, ApprovalGate only, after `interrupt()`, through `ApprovalService` (FEAT-015).
- Job handles for long tools.
- Run recovery at startup.
- `durability="sync"` for runs that can reach the ApprovalGate.
- New prompt versions (`fleet_compliance.v3`, `route_planner.v2`, `dispatcher.v3`) that mention the new tools.
- New eval scenarios (offline and live).
- An optional architecture experiment.

**Out of scope:**
- New agents;
- message sending;
- changes to the GroundingGuard algorithm;
- model policy changes beyond budget defaults;
- the LangGraph Platform.

## 4. Functional requirements

- **FR-1 `driver_calendar`.** A thin adapter over the FEAT-011 availability service and the FEAT-013 ledger facts. Aliases only (`D1…`); no names, phone numbers or home addresses; home and positions as city names.
- **FR-2 `evaluate_insertion`.** A thin adapter over `OfferEvaluationService.evaluate` (FEAT-015), run synchronously with `EVAL_BUDGET_S`, or as a job handle when it exceeds the tool timeout.
- **FR-3 `compare_cycle_options`.**
  - For one driver and up to 6 offers, the engine evaluates:
    - each single offer;
    - every feasible combination up to `max_offers_per_plan`, capped at 12 combinations by cycle profit;
    - `baseline_return_empty`.
  - The tool returns the research-note §5.6 table as facts: km, drive h, revenue, cost, isolated profit, cycle profit, home ETA, slack, empty km, and rejection codes.
  - Backed by a new read method `PlanService.compare_cycle_options` that calls the engine. **There is no logic in the tool.**
- **FR-4 `amend_assignment`.**
  - Kind `write`, `roles=()`.
  - Called only from the ApprovalGate after the human `approve` on a pending approval of kind `amend`.
  - Input: assignment id, assignment version, proposal id and proposal digest.
  - Calls `ApprovalService.approve`; it is idempotent on re-entry after resume (the same approval row is re-read and no second write happens).
- **FR-5 `request_approval`** gains `kind ∈ {assign, amend}` and, for `amend`, the proposal id.
- **FR-6 Job handles.**
  - `optimize_driver`, `optimize_fleet`, `evaluate_insertion` and `compare_cycle_options` accept `horizonDays (1–7)` and `driverAliases (≤ 20)`.
  - When a job exceeds `AGENT_TOOL_SYNC_WAIT_S` (default 20, *assumption*), the tool returns `{jobId, status: "running"}`. A `job_status` read tool (all planner roles) polls it.
  - The hard 60 s wait is removed.
- **FR-7 Run recovery.** At startup, agent runs in `queued` or `running` older than the run timeout become `failed` with `RUN_INTERRUPTED`, and their thread accepts new messages.
- **FR-8 Durability.** `graph.invoke` uses `durability="sync"` for every run. Today a run that reaches the ApprovalGate can't be told apart from one that doesn't in advance, so all runs use sync.
- **FR-9 Prompts.** New versions as in Scope. Content changes need owner approval and an `ai-evals` run (`context.md` AI rule 11). Offer text stays in `untrusted_text`.
- **FR-10 Evals.**
  - Add scenarios 31–38:
    - the calendar question;
    - the return deadline in PL;
    - an insertion;
    - the §5.6 comparison;
    - a stale proposal;
    - an amendment approval;
    - a job handle;
    - an injection in an offer note asking to "auto-approve".
  - Offline on fakes in CI. Live only with `--confirm-live` within the agreed budget.
- **FR-11 Budget defaults.** `AGENT_RECURSION_LIMIT`, `AGENT_MAX_TOOL_CALLS` and `AGENT_RUN_TOKEN_BUDGET` are set from the measured live runs (median + 25 %), documented in `evals/README.md`, and approved by the owner.
- **FR-12 Experiment (optional, slice 016/6).**
  - The same 38 scenarios run on a single `dispatcher` agent that holds all read tools, against the current supervisor.
  - The report records success, tool-call correctness, violations, tokens and latency.
  - The owner decides from it. No code change to production defaults in this slice.

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| NFR-004 | Bounded runs | agent tests: limits enforced; job handles keep runs under the run timeout |
| NFR-012 | Cost | tokens per complete live run ≤ the P13 range after the change (recorded in the eval report) |
| NFR-006 | Provider swap | the existing contract test still passes for ≥ 2 fake providers |

## 6. Contracts (API, data/migrations, ports, agent tools)

**API:** no new REST endpoint. Agent run states gain `failed` with the code `RUN_INTERRUPTED`; this is an additive enum value.
**Data / migrations:** none. Approval requests carry `kind` in their JSON payload.
**Configuration:** `AGENT_TOOL_SYNC_WAIT_S=20` (*assumption*); budget defaults per FR-11.

### Tool: driver_calendar
- Agent(s): fleet_compliance
- Kind: read
- Input schema: `{driverAlias: str, fromDate: date, toDate: date}` with a range ≤ 63 days; `extra="forbid"`
- Output schema: `{driverAlias, windows: [{startAt, endAt, homeFrom, source}] ≤ 10, homeRequirement: {deadline, kind, explainCode}, ledger: {weeklyRestDueBy, legalReturnDueBy, fortnightDriveRemainingMin, openCompensations ≤ 5}, warnings: [code] ≤ 10}`
- Backing service: `fleet.service.availability.AvailabilityService.for_driver` + `compliance` ledger read
- Facts exported for grounding: all timestamps, minutes, codes, the alias
- Untrusted fields: none
- Errors: `NOT_FOUND`, `RANGE_TOO_LONG` → reported as facts; the agent asks for a shorter range
- Tests: AC-FEAT-016-01

### Tool: evaluate_insertion
- Agent(s): route_planner
- Kind: read
- Input schema: `{offerAlias: str, driverAliases: list[str] ≤ 20 | null, topN: int 1–5}`
- Output schema: `{proposals: [{driverAlias, afterStop: int, deltaCycleProfitMinor, currency, slackMin, keptCommittedStops, bindingConstraints: [code] ≤ 5}] ≤ 5, truncated: bool} | {jobId, status}`
- Backing service: `optimization.jobs.service.OfferEvaluationService.evaluate`
- Facts exported for grounding: all numbers, aliases, codes
- Untrusted fields: none (offer text is never returned)
- Errors: `OFFER_CHANGED`, `DRIVER_OFF_DUTY`, `NO_FEASIBLE_INSERTION` → facts
- Tests: AC-FEAT-016-02

### Tool: compare_cycle_options
- Agent(s): route_planner
- Kind: read
- Input schema: `{driverAlias: str, offerAliases: list[str] 1–6, horizonDays: int 1–7}`
- Output schema: `{options: [{offers: [alias], km, driveMin, revenueMinor, costMinor, isolatedProfitMinor, cycleProfitMinor, homeEta, slackMin, emptyKm, feasible: bool, rejection: code | null}] ≤ 14, baselineReturnEmptyMinor, currency} | {jobId, status}`
- Backing service: `optimization.jobs.service.PlanService.compare_cycle_options` (new read method over the engine)
- Facts exported for grounding: all fields
- Untrusted fields: none
- Errors: `OFFER_CHANGED`, `DRIVER_OFF_DUTY` → facts
- Tests: AC-FEAT-016-03

### Tool: job_status
- Agent(s): route_planner
- Kind: read
- Input schema: `{jobId: str}`
- Output schema: `{jobId, status, resultRef | null}`
- Backing service: `JobService.get`
- Facts exported for grounding: the status and reference
- Untrusted fields: none
- Errors: `NOT_FOUND`
- Tests: AC-FEAT-016-06

### Tool: amend_assignment
- Agent(s): none (ApprovalGate only)
- Kind: **write** ⇒ `interrupt()` required
- Input schema: `{assignmentId, assignmentVersion: int, proposalId, proposalDigest}`
- Output schema: `{assignmentId, newVersion, keptStops, addedStops, removedStops}`
- Backing service: `ApprovalService.approve` (FEAT-015)
- Facts exported for grounding: all fields
- Untrusted fields: none
- Errors: `PLAN_STALE`, `OFFER_CHANGED`, `CONCURRENT_ASSIGNMENT`, `PROPOSAL_NOT_OPEN` → a note, then the template answer
- Tests: AC-FEAT-016-04, 05

## 7. Acceptance criteria

- **AC-FEAT-016-01** [agent] Given fake models When the Fleet & Compliance agent calls `driver_calendar` Then the call succeeds, any other role calling it is rejected with `TOOL_NOT_ALLOWED`, and an answer that cites the returned deadline passes the GroundingGuard, while an answer with a changed deadline is replaced by the template.
- **AC-FEAT-016-02** [agent] Given fake models and an offer with a feasible insertion When the Route Planner calls `evaluate_insertion` Then the output is schema-valid with at most `topN` proposals and contains no offer text, and the numbers are grounded facts.
- **AC-FEAT-016-03** [agent] Given the GOLD-012 snapshot When `compare_cycle_options` runs for its driver and offers A, B and C Then the options equal the engine's values for each combination, the `baselineReturnEmptyMinor` equals the baseline, and the infeasible option carries its rejection code.
- **AC-FEAT-016-04** [agent] Given a pending approval of kind `amend` When the run is resumed with `reject`, or with no decision until expiry Then `amend_assignment` is never executed. When it is resumed with `approve` by a `dispatcher` Then it is executed exactly once through `ApprovalService.approve`. No agent role can call it directly.
- **AC-FEAT-016-05** [agent] Given an approved amendment whose node is re-entered after a simulated crash between the write and the checkpoint When the run resumes Then no second amendment is written, and the answer reports the existing result.
- **AC-FEAT-016-06** [agent] Given an optimisation job that takes longer than `AGENT_TOOL_SYNC_WAIT_S` (fake engine) When the tool runs Then it returns a job handle within the wait time, `job_status` later returns the result reference, and the run ends within its timeout.
- **AC-FEAT-016-07** [integration] Given an agent run left `running` in the database and a restart of the application When startup completes Then the run is `failed` with `RUN_INTERRUPTED`, and a new message on its thread starts a new run.
- **AC-FEAT-016-08** [agent] Given a run paused at the ApprovalGate When the process is killed and the graph is rebuilt with the same checkpointer Then the pending interrupt is found and can be resumed (durability `sync`).
- **AC-FEAT-016-09** [eval] Given scenarios 31–38 When the offline eval campaign runs on scripted fakes Then every scenario passes, with 0 write-policy violations and 0 followed injections.
- **AC-FEAT-016-10** [eval] Given an owner-agreed budget When the live campaign runs all 38 scenarios with the new prompt versions Then task success is ≥ 27/30 on the old scenarios and ≥ 6/8 on the new ones, with 0 write-policy violations, and the tokens per run are recorded.
- **AC-FEAT-016-11** [eval] Given the experiment configuration When the single-agent variant and the supervisor run the same scenarios on the same model Then a report with success, tool-call correctness, violations, tokens and latency per variant is written to `evals/reports/`, and no production default changes.

## 8. Edge cases

- **An alias from an older run in the same thread** that refers to a deleted driver: `NOT_FOUND` fact.
- **A job handle that finishes after the run ended:** the next message can call `job_status`.
- **A proposal superseded between the request and the approval:** `PROPOSAL_NOT_OPEN` → note.
- **A budget exhausted mid-run:** the template answer (existing).

## 9. Dependencies

- FEAT-006 (graph, tools, guards), FEAT-011 (availability), FEAT-012 (cycle profit), FEAT-013 (ledger facts), FEAT-015 (evaluation service, `ApprovalService`).
- ADR-0006, ADR-0013, ADR-0017.
- Owner: prompt and allowlist approval, `ai-evals` budget (O-19).
- Libraries: none new (LangGraph `durability` exists in the pinned 1.2.20; verify in the changelog before use).
- Shared files: `apps/api/src/routepilot/agents/prompts/**` (🔒).

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| 01–06, 08 | `apps/api/tests/agents/test_planning_tools.py`, `test_amend_assignment.py`, `test_job_handles.py`, `test_durability.py` | fake models, temp checkpointer |
| 07 | `apps/api/tests/integration/test_agent_run_recovery.py` | temp databases |
| 09 | `evals/agents/31-38*.yaml` + `tests/agents/test_eval_runner.py` | offline fakes |
| 10, 11 | `evals/` live campaign | the owner's budget and keys (never in CI) |

## 11. Open questions

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-016-01 | `AGENT_TOOL_SYNC_WAIT_S` | 20 s (*assumption*) | AC-06 |
| OQ-016-02 | Live budget for AC-10 and AC-11 | owner decides (O-19) | AC-10, 11 |
| OQ-016-03 | Should `job_status` be available to every role? | Route Planner only | AC-06 |
| OQ-016-04 | Is the 12-combination cap for `compare_cycle_options` enough? | yes for ≤ 6 offers by cycle profit | AC-03 |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-18 | Initial draft from the research note §8 and §12 (E6) |
