---
id: FEAT-007
title: Quality gates in ci-full, E2E, clean-clone run test, documentation completeness, metrics
status: approved
owner: project owner
requirements: [REQ-032, REQ-033, NFR-012, NFR-014]
adrs: [ADR-0007, ADR-0009]
modules: [.github/workflows, tests/e2e, scripts, README.md, DEVELOPMENT.md]
revision: 1
---

# FEAT-007: Quality gates in ci-full, E2E, clean-clone run test, documentation completeness, metrics

Priority: **P0**. Nothing in this specification is implemented yet.

## 1. Goal

Before the release the project is proven end to end: a second pipeline (`ci-full`) runs the integration and browser scenarios, a script proves that a clean clone starts by following the README, the README and `DEVELOPMENT.md` are complete against the delivery standards, and a metrics script produces the numbers quoted in the documentation instead of guesses.

## 2. Business context

A person who clones the repository must get a working app in a few steps (NFR-014, risk R6 in [`docs/report.md`](../docs/report.md) §36). The README is a delivery standard in itself ([`DEVELOPMENT.md`](../DEVELOPMENT.md) §1, row 8b). Product metrics must be measured by the application, not assumed (report §3.5).

## 3. Scope / Out of scope

**In scope:** `ci-full.yml`; `ai-evals.yml` (manual trigger only); the backend integration scenario; the Playwright E2E scenario; `scripts/clean_clone_check.sh`; documentation checklists and a checker script; `scripts/benchmark_report.py` (metrics); coverage threshold enforcement; audits and licence check; final README update (status table, verified commands, "How I used AI tools" examples).

**Out of scope:** deployment workflows and Docker images (post-MVP); axe automation (P1); load testing; the demo video itself (FEAT-009).

## 4. Functional requirements

- **FR-1 `ci-full`.** Runs on pushes to `main` and nightly. It contains everything in `ci-fast` plus: Gate 3 with the Hypothesis profile `nightly`; Gate 4 with the full schemathesis run; Gate 6 integration; Gate 7 E2E; Gate 8b audits (`pip-audit`, `pnpm audit`), static analysis and the licence check (no GPL/AGPL at runtime); the clean-clone check. No step calls an LLM, ORS, TIMOCOM or Cloudflare.
- **FR-2 Integration scenario** (`-m integration`, one test module): empty database → first-start seed → login as demo → create a manual offer through the API → fleet optimisation job → result with three objectives and baselines → agent run on a scripted fake model up to `approval_required` → resume `approve` → assignments exist → the driver delete endpoint now returns `409 DRIVER_HAS_ACTIVE_ASSIGNMENT`.
- **FR-3 E2E scenario** (Playwright, Chromium, against `uvicorn` on `:8000` and `pnpm start` on `:3000`, seeded data, no LLM key, Turnstile test keys):
  1. Log in as admin; switch the language to Polish and back.
  2. Fleet: add a vehicle and a driver, edit the driver, see the toast; delete the driver after confirmation.
  3. Offers: add a manual offer; check that an imported offer has no edit button; filter by country.
  4. Optimizer: run a fleet optimisation; open the `profit` plan; see three variants with kg CO₂ and the legal notice.
  5. Assign the plan after confirmation; see the assignment in the fleet view.
  6. AI Dispatcher: see the "AI is off" panel and follow its link to the optimizer.
  A second, tagged spec (`@ai-fake`) starts the API with a fake-model policy (`APP_ENV=test`) and covers: send a question → trace steps appear → approval card → Approve → assignment visible; and Reject → nothing assigned.
- **FR-4 Clean-clone check.** `scripts/clean_clone_check.sh` clones the repository into a temporary directory (or uses a fresh CI checkout), executes exactly the commands of README §6 for the API and the web (with `pnpm build && pnpm start` instead of `pnpm dev`), waits for `/ready`, calls `/health`, logs in with the demo account from `.env.example`, lists drivers (expects 5) and requests `http://localhost:3000/login` (expects `200`). It measures the elapsed time and fails if any step fails. No API key is present in the environment.
- **FR-5 README completeness.** The README contains, in this order, the sections: What it is · Features · Creative twist · Technical overview · Architecture (with a Mermaid diagram) · Run locally — step by step (prerequisites with versions, API then web, optional keys, demo login, tests) · How I used AI tools · Demo · Project structure · Limitations · Roadmap · Documentation map — followed by a Polish summary of at most 25 lines. `scripts/check_docs.py` verifies the headings and their order, the 25-line limit, that every relative link resolves, that every fenced command in §6 also appears in `clean_clone_check.sh`, and that the fixed purpose statement rule holds (see FR-7).
- **FR-6 DEVELOPMENT.md completeness.** `check_docs.py` verifies that the 14 sections exist and that the standards matrix (§1) has a row for every delivery standard 1–6, 7a–7e, 8a–8e, each with a non-empty "Proof" cell whose referenced files and AC IDs exist.
- **FR-7 Wording checks.** `check_docs.py` scans all Markdown files and fails on: a planned feature described with "is implemented" style markers while its specification is not `implemented` (it compares the README status table with the FEAT statuses); the working-time notice missing from a file that defines schedules (plan and golden specifications, README limitations); any term from a configurable deny-list file `scripts/docs_denylist.txt` (kept by the owner; used to enforce the fixed purpose statement of `context.md` → Project Constraints 10).
- **FR-8 Metrics.** `scripts/benchmark_report.py` runs on the seeded demo data (fixed seed and reference date) and writes `docs/metrics.md` with: fleet profit of the `profit` solution vs `baseline_single` and `baseline_greedy` (absolute and %), share of empty km, capacity utilisation (EP·km and kg·km over available), share of drivers home before `home_by`, engine runtime p50/p95 over 20 runs, node counts, and — when run with `--agents-fake` — time from question to `approval_required` on the fake model. Every number in the README that describes results must come from this file.
- **FR-9 Coverage gate.** `ci-fast` and `ci-full` fail when a package is below its threshold (`context.md` → Testing Standards).
- **FR-10 `ai-evals`.** A manually triggered workflow with provider keys from GitHub Secrets and a hard token budget; it runs the scenarios of FEAT-006 AC-40/41 and uploads the report as an artefact. It never runs on pull requests.
- **FR-11 Final README update.** Status table updated to reality (✅ only for what `ci-full` proves), commands verified by the clean-clone check, and at least three concrete examples added to "How I used AI tools" (a task brief with its completion report, a defect caught by a gate, a manual correction), replacing the placeholder.

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| NFR-014 | Clean clone → working app | `clean_clone_check.sh` passes; elapsed time ≤ 10 min on the CI runner (recorded) |
| NFR-012 | No cost to run or test | `ci-fast` and `ci-full` use no paid service and no secret |
| — | `ci-full` duration | target ≤ 25 min (recorded) |
| — | E2E stability | the scenario passes 3 times in a row locally before release; retries in CI limited to 1 |

## 6. Contracts (API, data/migrations, ports, agent tools)

- **API / data / ports / agent tools:** No change.
- **Workflow files:** `.github/workflows/ci-full.yml`, `.github/workflows/ai-evals.yml` (changes need human approval).
- **Scripts:** `scripts/clean_clone_check.sh`, `scripts/check_docs.py`, `scripts/benchmark_report.py`, `scripts/docs_denylist.txt`.
- **Generated documents:** `docs/metrics.md`, `docs/traceability.md`.
- **Test-only configuration:** `APP_ENV=test` allows a fake-model policy entry `fake:<script-name>` in `AGENT_MODEL_POLICY`; it is rejected in any other environment.

## 7. Acceptance criteria

- **AC-FEAT-007-01** [integration] Given a push to `main` When `ci-full` runs Then gates 1–10 including 6, 7 and 8b run, the workflow fails if any gate fails, and the logs show no outbound call to LLM, ORS, TIMOCOM or Cloudflare hosts.
- **AC-FEAT-007-02** [integration] Given an empty database and no API keys When the integration scenario of FR-2 runs Then every step succeeds in order and the final assertions hold (assignments exist; the driver delete returns `409 DRIVER_HAS_ACTIVE_ASSIGNMENT`).
- **AC-FEAT-007-03** [e2e] Given locally started API and web with seeded data When the Playwright scenario of FR-3 runs (both specs) Then all steps pass in Chromium, including the language switch, CRUD with toasts and confirmation, three variants with CO₂ and the legal notice, assignment, the "AI is off" path, and the fake-model approval and rejection paths.
- **AC-FEAT-007-04** [integration] Given a fresh checkout and an environment without any API key When `scripts/clean_clone_check.sh` runs Then it executes the README commands unchanged, the API becomes ready, the demo login works, 5 drivers are listed, the web login page answers `200`, and the measured time is printed and is ≤ 10 minutes.
- **AC-FEAT-007-05** [unit] Given the repository When `scripts/check_docs.py --readme` runs Then it passes only if the README has the twelve sections in order, a Polish summary of ≤ 25 lines at the end, resolvable relative links, and §6 commands identical to those in the clean-clone script; a fixture README with a missing or reordered section fails.
- **AC-FEAT-007-06** [unit] Given the repository When `scripts/check_docs.py --development` runs Then it passes only if `DEVELOPMENT.md` has its 14 sections and a standards-matrix row with existing proof references for each of the delivery standards 1–6, 7a–7e and 8a–8e; a fixture with a missing row fails.
- **AC-FEAT-007-07** [integration] Given seeded demo data When `scripts/benchmark_report.py` runs twice Then `docs/metrics.md` contains all metrics of FR-8, the non-timing values are identical between the runs, and the fleet profit is ≥ both baselines.
- **AC-FEAT-007-08** [integration] Given the dependency set When Gate 8b runs Then a known high-severity advisory or a GPL/AGPL runtime licence in a fixture lockfile makes the gate fail, and the real lockfiles pass.
- **AC-FEAT-007-09** [integration] Given the `ai-evals` workflow When its definition and a run are inspected Then it has only a manual trigger, requires the provider secrets, stops at the configured token budget and uploads a report with the metrics of FEAT-006 AC-40.
- **AC-FEAT-007-10** [integration] Given the coverage report of a CI run When the coverage gate evaluates it Then the job fails when any package is below its threshold and prints the per-package numbers; the thresholds in the configuration equal those of `context.md` → Testing Standards.

## 8. Edge cases

- The CI runner has ports 3000/8000 occupied → the scripts fail with a clear message naming the port.
- Playwright cannot interact with the Turnstile iframe → with Cloudflare's "always pass" test site key the widget issues a token without interaction; the test waits for the token field instead of clicking.
- The README changes a command but the script does not → `check_docs.py` fails (single source: the README).
- Timing metrics vary between machines → only non-timing metrics are compared between runs; timings are reported, not asserted (except the documented targets).
- `ai-evals` without secrets (fork) → the workflow exits early with a message.

## 9. Dependencies

- All earlier features (FEAT-000 … FEAT-006) merged.
- ADR-0007 (local run), ADR-0009 (contracts).
- Tools: Playwright, schemathesis, pip-audit, gitleaks, a licence checker (name and version verified in the registry at implementation).
- Human approval for the workflow files and for any live `ai-evals` run.

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| 01, 08, 09, 10 | workflow runs; `scripts/tests/test_workflows.py` (static checks of the YAML: triggers, pinned action SHAs, no secrets in `ci-fast`/`ci-full`) | fixture lockfiles |
| 02 | `apps/api/tests/integration/test_end_to_end.py` | scripted fake model; temporary SQLite files |
| 03 | `tests/e2e/demo.spec.ts`, `tests/e2e/agent-fake.spec.ts` | seeded data; `APP_ENV=test` fake policy |
| 04 | `scripts/clean_clone_check.sh` in `ci-full` | fresh checkout |
| 05, 06 | `scripts/tests/test_check_docs.py` | fixture documents |
| 07 | `scripts/tests/test_benchmark_report.py` | seeded database |

## 11. Open questions

**Owner decisions (2026-11-11):** all proposed defaults in this table are accepted. OQ-007-03: the repository will be public on GitHub, so CodeQL default setup is used.

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-007-01 | Should the clean-clone check also run on macOS and Windows runners? | Linux in CI; one manual run on the owner's machine on 2026-11-14. | AC-FEAT-007-04 scope |
| OQ-007-02 | Content of `scripts/docs_denylist.txt` (terms that must not appear in the repository). | The owner maintains the file; the checker only enforces it. | FR-7 |
| OQ-007-03 | Which static-analysis tool for Gate 8b (`context.md` names CodeQL/Semgrep). | CodeQL through GitHub's default setup for a public repository. | AC-FEAT-007-08 |
| OQ-007-04 | Is the fake-model policy in `APP_ENV=test` acceptable for the E2E agent path? | Yes; it is rejected outside `test`. | AC-FEAT-007-03 (second spec) |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-09 | Initial draft |
| 2 | 2026-11-11 | Owner decisions on the open questions recorded (§11) |
| 3 | 2026-11-11 | Status `draft` → `approved` by the owner |
