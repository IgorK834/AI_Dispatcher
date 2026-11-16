# Development log: problems met and how they were solved

RoutePilot AI is an MVP with a deadline of 2026-11-15, later a portfolio project. This file records the real problems of the build, what was done about each, what is still open and how it will be improved. It is the long form of the short table in [`DEVELOPMENT.md` §10.6](../DEVELOPMENT.md#106-problems-met-and-lessons). Numbers come from [`docs/metrics.md`](metrics.md) and the pull requests named in each entry.

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

The project is a first version that needs improvements, and they are planned for later (section 3); the open items below are not finished work. The demo offers have the structure of the TIMOCOM Freight Exchange API v3.0.6 payload, taken from its OpenAPI file, with generated values and separate enrichment for fields the API does not define; no real data is used.

Status words: **solved** (fixed and tested), **mitigated** (better, a limit remains), **open** (decision or work still ahead).

## 1. Summary

| # | Problem | Status | Where it is handled |
|---|---|---|---|
| P1 | Demo plans were chains of single orders at about 46% van fill | solved for the cause, **open** for the fill target | FEAT-010, PRs #123 … #131 |
| P2 | A distance-only price made small consignments unprofitable | solved | handling charge, `docs/raport.md` §3.6 |
| P3 | Half of the generated offers could not reach their own delivery window | solved | FEAT-010 FR-4a |
| P4 | The exact search is too slow for the 15 s target | mitigated, **open** | `search.py`, OQ-010-11 and NFR-002 |
| P5 | Fill stays at about 40% because of empty kilometres | **open** (owner decision) | OQ-010-11 |
| P6 | Tests depended on the time of day | solved | `evals/`, PR #130 |
| P7 | A test passed locally and failed in CI | solved | PR #130 |
| P8 | A worker forked from the web server hung the browser scenarios | solved | `AC-FEAT-004-15` |
| P9 | A validator looped at the Monday week boundary | solved | `AC-FEAT-003-25` |
| P10 | Live agents skipped required lookups; one paid campaign nearly used its whole budget | solved by process | `evals/README.md` |
| P11 | Stacked pull requests, generated files and local tooling got in the way | solved by process | section 4 |
| P12 | A specification needed a revision after approval | solved by process | FEAT-010 revisions 2 → 4 |
| P13 | Recording the live AI scenes cost much more than planned and hit three limits | mitigated, **open** | section 2, P13 |

## 2. Problems in detail

### P1 Plans were chains of single orders

- **Symptom.** In the first measurements 81% of the offers had no consolidation partner, half of the fleet plans never carried more than one order at once, and vans ran at 46% pallet fill and 40% weight fill.
- **Diagnosis.** The solver was not the cause. It already supports interleaved pickups and deliveries with a two-dimensional capacity check (`GOLD-001`). The inputs gave it no reason and no chance to consolidate: every offer was priced like a full van, lanes were drawn at random over 39 city centres, offer mass had nothing to do with the pallet count, and the pool cut ranked offers one at a time. The research is in [`docs/raport.md`](raport.md).
- **Fix.** FEAT-010: size-based prices, consignment groups along corridors, mass that follows pallets, a partner-aware pool cut, plan load metrics and a golden case (`GOLD-011`) that shows a consolidated plan beating a chain. The share of offers with a partner rose from 18.6% to 75.5%.
- **Left.** The fill itself did not reach its target (P5).
- **Lesson.** Measure before changing the engine. The measurement moved the work from the solver to the data.

### P2 A distance-only price left the fleet without profit

- **Symptom.** After the first size-based tariff no demo driver had a profitable plan, and 14 agent tests that rely on profitable plans failed.
- **Diagnosis.** The tariff was proportional to the distance. Public price examples found on 2026-11-15 (about €110 for one pallet within Poland, €169 Poland to Netherlands, €247 for two pallets over about 200 km) show that a pallet costs roughly €70–150 whatever the distance. Short lanes, which fill the demo, were three to five times too cheap.
- **Fix.** A handling charge of €35 per pallet equivalent, an assumption set below the quotes, added to the line-haul part. Every demo driver then has profitable plans. A lone 3-pallet order on a 211 km lane without a return leg still earns about €47 (checked with the engine), so the tariff makes consolidation more rewarding, not compulsory. GOLD-011 shows the other side: the consolidated plan earns €527.97 against €493.97 for the best plan without the return load.
- **Left.** The constants are assumptions, not market data. They are labelled as such in the specification and in the enrichment file.
- **Lesson.** Check a model constant against an outside source before building on it. The first tariff looked reasonable and was wrong.

### P3 Delivery windows that could not be reached

- **Symptom.** 69 of 140 timed offers (49%) could not reach their own delivery window even when picked up at the start of their pickup window.
- **Diagnosis.** The older generator reused the pickup's clock window on the delivery day, which is only valid for long lanes.
- **Fix.** FR-4a: the delivery window is derived from the pickup start plus service plus drive time, on the same day when it fits, otherwise on the next working day. A property test (`AC-FEAT-010-15`) checks it for any seed.
- **Lesson.** A generator can be internally consistent and still be infeasible. Test the generated data against the same rules the engine uses.

### P4 The exact search is slow

- **Symptom.** The 20-seed benchmark takes about 160 s per run and every run is cut by the 30 s per-driver safety limit. The target is p95 ≤ 15 s (NFR-002).
- **Diagnosis.** A profile showed 33 move attempts per search node, and 92% of them failed on a bound that is cheap to compute: arriving after the window has closed.
- **Fix.** The search now skips such moves. Results are identical (golden, oracle and property tests), and the search handles about four times more nodes per second. The 2-day report run went from 10.3 s to 5.2 s.
- **Left.** Faster nodes do not change the runtime, because the safety limit decides it. Meeting 15 s needs stronger pruning or smaller defaults (see section 3).
- **Lesson.** Profile first. The biggest cost was not where it was expected, and the correct fix was a bound, not a rewrite.

### P5 Fill stays at about 40%

- **Symptom.** Target B asks for 60% pallet fill over all kilometres. The result over 20 seeds is 40%.
- **Diagnosis.** Neither the data nor the search limits it. Changing the share of return groups from 0.5 to 1.0 changed nothing: about 41% of the kilometres stay empty, because every plan starts with a deadhead leg to the first pickup and ends with the drive home before `home_by`. On loaded kilometres the fill is 56% (pallets) and 68% (payload).
- **Fix.** None yet, on purpose. The report now shows the fill on loaded kilometres next to the all-kilometre fill, and OQ-010-11 asks the owner to measure the target differently, lower it or accept "not met".
- **Lesson.** A target written before the model existed can be unreachable. Say so, and do not tune constants to hit it.

### P6 Tests that depended on the time of day

- **Symptom.** Two offline eval scenarios failed at some hours and passed at others, on `main` as well.
- **Diagnosis.** The runner used the real clock and the offer windows are relative to "now". Under a fixed clock a second problem showed: the fixture's driver state was written at the same instant as the seeded one and lost the tie, so the driver became available at 07:45Z instead of "now".
- **Fix.** The offline campaign uses a fixed clock, and the fixture writes its states a minute later. `make eval-offline` has no failing scenario. Live runs keep the real clock.
- **Lesson.** Inject the clock everywhere; the project rule says so ([`context.md`](../context.md) core rule 2). Also check ties in anything versioned by time.

### P7 A test that passed locally and failed in CI

- **Symptom.** A contract test read `main:contracts/openapi.json` through git. CI checks out a detached merge commit and has no local `main`.
- **Fix.** The test uses `main` or `origin/main`, whichever exists, and it was checked by renaming the local branch.
- **Lesson.** Do not rely on repository state that CI does not have.

### P8 and P9 Hangs found by the quality gates

Both are described in the README ([How I used AI tools](../README.md#7-how-i-used-ai-tools), example 2). A forked optimisation worker kept dead client sockets alive and hung the browser scenarios (fix: start the worker with `spawn`, test `AC-FEAT-004-15`); the working-time validator looped when an activity ended less than a minute before the Monday week boundary (test first, then the fix, `AC-FEAT-003-25`). Both were found by reading the run logs.

### P10 Live agents and the token budget

The first live measurement of the agents showed skipped lookups, so two prompts got a second approved version and were measured again. The first paid campaign used 484 835 of 500 000 tokens, so later campaigns run under a hard ledger that reserves a call's whole token cap before the call. Details: [`docs/reports/FEAT-006-live-evals-2026-11-14.md`](reports/FEAT-006-live-evals-2026-11-14.md), [`evals/README.md`](../evals/README.md).

### P11 Process friction

| What happened | What was done |
|---|---|
| Seven pull requests depended on each other | They were stacked, each based on the previous branch, and merged with merge commits in order. A squash would have broken the stack. |
| `next dev` and `next build` change `apps/web/next-env.d.ts` and create `apps/web/AGENTS.md` | Neither is ever committed. |
| `make check` runs `prettier --check .`, which fails on an untracked local `.claude/` folder | The steps were run one by one with that folder excluded; the folder stays untracked. |
| A formatter run over a whole folder touched an unrelated file | The change was reverted before the commit. Format only the files of the task. |
| Local benchmark result files are easy to stage by accident | They are never committed (`bench/results/*.json`). |

### P12 A specification changed after approval

The tariff, the delivery windows and the town list all needed a revision after FEAT-010 was approved. The coding agent stopped with a `blocked` report instead of working around it, proposed the change, and the owner approved revision 3 and the golden values before the golden test was written. The specification now has four revisions and a changelog for each.

### P13 Recording the live AI scenes

- **Symptom.** Five takes of one chat question were needed. The first two stopped before any proposal; the third and fifth ended with the model's honest "no feasible plan"; only the fourth reached the approval card. About 256 000 of the 300 000 tokens the owner allowed were spent, so the Reject and Approve clicks could not be recorded.
- **Diagnosis, in the order it appeared.**
  1. The tool-call limit (6 per agent) was used up by "list the drivers and check five drivers". A fleet-wide question needs more.
  2. The per-run token budget (60 000) is used up by a multi-agent run: the Freight Scout's context grows with every tool result (6 000 → 10 700 input tokens), and the guard reserves the full output cap (8 192) before each call. One complete run costs about 50 000–76 000 tokens at these settings.
  3. With a free question the Freight Scout picked refrigerated offers and the planner correctly found no plan. Naming the offers made the run reach a proposal.
- **Fix for the recording.** Environment settings only: 12 tool calls, 90 000 tokens per run, dispatcher thinking level `low`, a daily cap equal to what was left of the allowance, and a question that names the driver and two offers. No code changed. Waiting parts are shown four times faster and say so on screen.
- **Left.** The Reject / Approve clicks are not in the video. Two product observations came out of it: the chat keeps its conversation only in the page's memory, so after a reload a pending approval card cannot be reached from the UI (the request stays valid on the server for 30 minutes); and the trace summary shows "0 tokens" while a run waits for approval and the real total only after it finishes.
- **Lesson.** Estimate a live run from the measured tokens of earlier runs before agreeing a budget, and stop at the allowance: the work stopped at 256 288 tokens although it was not finished.

## 3. How it will be improved

Ordered by value for the effort. "Needs approval" means a change to a default, an ADR or a specification that only the owner may make.

| # | Improvement | Why | Needs approval |
|---|---|---|---|
| I1 | **Label dominance in the search.** Drop a partial plan when another with the same offers, position and counters is earlier and cheaper. It is already on the P1 list of [`context.md`](../context.md). | The main way to reach 15 s without losing exactness. | ADR-0004 update |
| I2 | **Cheaper node work.** Cache the rule counters, avoid copying pydantic models (about 450 000 copies in a 6 000-node profile before the speed-up), compute the cost bound incrementally. | Another constant factor on top of the 4× already gained. | no |
| I3 | **Decide the runtime defaults.** Either a shorter per-driver safety limit or smaller `max_offers_per_plan` / `top_k_per_driver` for the benchmark. | The target is met only if the defaults or the target change. | yes ([`context.md`](../context.md) default parameters) |
| I4 | **Redefine target B.** Measure it on loaded kilometres, or set it near 40% over all kilometres, and show empty kilometres and their cause in the plan view. | The target as written cannot be met by the profit-optimal plans of this model. | yes (OQ-010-11) |
| I5 | **Real places for the demo towns.** Replace the 550 generated points by real towns from an open dataset, and replace the haversine matrix by one from a routing engine (owner action O-5). | More credible demo data; today's matrix is 10 MB and straight-line based. | yes (data and keys) |
| I6 | **Calibrate the tariff.** Fit the handling charge and the premium to a published tariff table per lane. | The constants are assumptions. | yes |
| I7 | **Export the load metrics to the agent tools** (OQ-010-08) so the dispatcher agent can say "the van is half empty". | The metrics exist in the API and the UI but not in the agent answers. | yes (tool change + `ai-evals`) |
| I8 | **Nightly benchmark in CI** with the numbers stored as a trend, not asserted. | Regressions in runtime and fill become visible. | yes (workflow file) |
| I9 | **Loading order and 2D pallet placement.** Today loading order is not modelled for curtain-siders. | More realistic capacity. | yes (P2 in the MVP boundaries) |
| I10 | **Larger fleets.** Add a heuristic or a general solver behind the same port. | The exact search is for about 5 vans. | ADR |
| I11 | **PostgreSQL and a VPS** with Docker Compose, as designed in ADR-0002 and ADR-0007. | The portfolio version. | outside the MVP |
| I12 | **Chat that survives a reload.** Keep the thread id in the URL or the session, restore the conversation and the pending approval card. | A pending approval is unreachable after a page refresh. | no (frontend only) |
| I13 | **Cheaper agent runs.** Trim what a tool result adds to the next model call, cap the Freight Scout's detail look-ups, and make the default tool-call and run budgets fit a fleet-wide question. | A run costs 50 000–76 000 tokens and the defaults stop it early. | yes (budget defaults, prompts, `ai-evals`) |
| I14 | **Record the approval clicks** (Reject, then Approve) on a live model once I13 makes a run cheaper, and replace the single screenshot that now serves as both 05 and 08. | AC-FEAT-009-02 asks for them. | yes (paid run, new allowance) |

A test-quality item sits next to these: add a check that no domain or test code reads the system clock outside an injected `Clock`, so that P6 cannot return.

## 4. What would be done differently

- Measure the demo data against the engine on day one, before writing the engine's performance target.
- Put the clock in every test fixture from the start.
- Run the CI gates on a branch early, to meet the "no local `main`" kind of problem before the last week.
- Write targets as "recorded, with a reason" instead of numbers that are assumed to be reachable.
