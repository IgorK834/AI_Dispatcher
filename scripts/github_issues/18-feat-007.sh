# FEAT-007 — Quality, README, ci-full. Sourced by scripts/create_github_issues.sh.
# shellcheck shell=bash disable=SC2034

s_007_1() {
  I_ID="007/1"; I_FEAT="007"; I_TITLE="Backend integration scenario end to end and the per-package coverage gate"
  I_AREA="backend infra"; I_SIZE="M"; I_DAY="2026-11-14"; I_CATCHUP="2026-11-14"
  I_ACS="02 10"; I_DEPS="004/5 006/6"
  I_GATES="make check, uv run pytest -m integration, coverage report per package"
  I_LOCK="\`apps/api/pyproject.toml\` (coverage configuration); 🔒 \`.github/workflows/ci-fast.yml\` if the coverage step changes"; I_APPROVAL="yes"
  I_BRANCH="test/FEAT-007-integration-coverage"; I_REQS="REQ-032, NFR-003"; I_ADRS="0007"; I_SCOPE_TAG="test"
  txt T_GOAL <<'EOF'
One backend test walks the whole product path without any key — seed, login, manual offer, fleet optimisation, agent run on a fake model up to approval, approve, assignments, and the resulting delete conflict — and CI fails whenever a package drops below its coverage threshold.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-007-quality-readme-ci-full.md` §4 FR-2, FR-9, §10 rows 02, 10
- `specs/FEAT-006-runtime-agents.md` §10 (the happy-path scenario doubles as this integration scenario)
- `context.md` → Testing Standards (coverage thresholds), CI Quality Gates (gate 3, gate 6)
EOF
  txt T_SCOPE <<'EOF'
- `tests/integration/test_end_to_end.py` (`-m integration`): empty database → first-start seed → login as demo → create a manual offer through the API → fleet optimisation job → result with three objectives and baselines → agent run on a scripted fake model up to `approval_required` → resume `approve` → assignments exist → `DELETE /drivers/{id}` → `409 DRIVER_HAS_ACTIVE_ASSIGNMENT`.
- Coverage thresholds in configuration equal to `context.md`: `optimization.engine`, `compliance` ≥ 90/85; `identity` ≥ 90/80; `freight`, `fleet`, `routing`, `agents` ≥ 85/75; routers ≥ 75; web `lib/` ≥ 80 — enforced per package with the numbers printed.
EOF
  txt T_OUT <<'EOF'
- E2E (007/2); the `ci-full` workflow itself (007/3).
EOF
  txt T_FILES <<'EOF'
- `apps/api/tests/integration/test_end_to_end.py` — new
- `apps/api/pyproject.toml` (coverage config), `apps/web/vitest.config.ts` (coverage for `lib/`) — changed
- `scripts/ci/check_coverage.py` (*suggested*: per-package thresholds) — new
- `.github/workflows/ci-fast.yml` — changed only to call the coverage check (🔒 O-2)
EOF
  txt T_TESTS <<'EOF'
- `test_end_to_end.py` — every step in order succeeds and the final assertions hold. → AC-02
- Coverage gate — a CI run fails when a package is below threshold and prints per-package numbers; thresholds equal `context.md`. → AC-10
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest -m integration -q
uv run pytest --cov=routepilot --cov-branch --cov-report=xml && uv run python ../scripts/ci/check_coverage.py coverage.xml
```
EOF
  txt T_TIPS <<'EOF'
- Lowering a threshold to pass is forbidden; if a package is below, add tests (or report it).
- Use temporary SQLite files for both `routepilot.db` and `agents.db` in the scenario.
EOF
}
register s_007_1

s_007_2() {
  I_ID="007/2"; I_FEAT="007"; I_TITLE="Playwright E2E: demo scenario and the fake-model approval spec"
  I_AREA="frontend infra"; I_SIZE="M"; I_DAY="2026-11-14"; I_CATCHUP="2026-11-14"
  I_ACS="03"; I_DEPS="005/6 005/7"
  I_GATES="pnpm exec playwright test (Chromium), make check"
  I_LOCK="\`pnpm-lock.yaml\`"
  I_BRANCH="test/FEAT-007-e2e"; I_REQS="REQ-015, REQ-017, REQ-021, REQ-031"; I_ADRS="0007"; I_SCOPE_TAG="e2e"
  txt T_GOAL <<'EOF'
A real browser clicks through the demo against locally started API and web: login, language switch, CRUD with toasts and confirmation, three variants with CO₂ and the notice, assignment, the AI-off path — and, with a fake-model policy, the approval and rejection flows.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-007-quality-readme-ci-full.md` §4 FR-3 (both specs, step by step), §6 (test-only fake policy `fake:<script>` in `APP_ENV=test`), §8 (ports, Turnstile iframe), §11 OQ-007-04
- `specs/FEAT-005-frontend.md` (screens), `tests/e2e/` harness from 005/2
EOF
  txt T_SCOPE <<'EOF'
- `tests/e2e/demo.spec.ts` against `uvicorn` on `:8000` and `pnpm start` on `:3000`, seeded data, no LLM key, Turnstile test keys: (1) log in as admin, switch PL and back; (2) fleet: add a vehicle and a driver, edit with toast, delete after confirmation; (3) offers: add a manual offer, imported offer has no edit button, filter by country; (4) optimizer: fleet run, open the `profit` plan, three variants with kg CO₂ and the legal notice; (5) assign after confirmation, assignment in the fleet view; (6) AI Dispatcher: "AI is off" panel and its link to the optimizer.
- `tests/e2e/agent-fake.spec.ts` tagged `@ai-fake`: API started with a fake-model policy (`APP_ENV=test`): question → trace steps → approval card → Approve → assignment visible; and Reject → nothing assigned.
- Clear failures when ports 3000/8000 are taken.
EOF
  txt T_OUT <<'EOF'
- Other browsers (Chromium only); axe (P1); visual regression.
EOF
  txt T_FILES <<'EOF'
- `tests/e2e/{demo.spec.ts,agent-fake.spec.ts,playwright.config.ts,fixtures.ts}` — new or changed
- `scripts/e2e/start_stack.sh` (*suggested*) — new
- `Makefile` (`e2e`) — changed
EOF
  txt T_TESTS <<'EOF'
- Both specs pass in Chromium, covering every step of FR-3. → AC-03
EOF
  txt T_VERIFY <<'EOF'
```bash
make e2e   # or: pnpm exec playwright test --project=chromium
pnpm exec playwright test --grep @ai-fake
```
EOF
  txt T_TIPS <<'EOF'
- With the "always pass" site key, wait for the Turnstile token field instead of clicking the iframe.
- The fake policy is rejected outside `APP_ENV=test`; never use it in a recording.
- Start from a fresh database per run so counts are stable.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-007-04 (accepted): the fake-model policy in `APP_ENV=test` is acceptable for the E2E agent path.
EOF
}
register s_007_2

s_007_3() {
  I_ID="007/3"; I_FEAT="007"; I_TITLE="ci-full and ai-evals workflows; audits, SAST and licence check"
  I_AREA="infra"; I_SIZE="M"; I_DAY="2026-11-14"; I_CATCHUP="2026-11-14"
  I_ACS="01 08 09"; I_DEPS="007/1 007/2 O-2"
  I_GATES="workflow runs green on main; static workflow checks"
  I_LOCK="🔒 \`.github/workflows/ci-full.yml\`, 🔒 \`.github/workflows/ai-evals.yml\`"; I_APPROVAL="yes"
  I_BRANCH="chore/FEAT-007-ci-full"; I_REQS="NFR-008, NFR-012"; I_ADRS="0007 0009"; I_SCOPE_TAG="ci"
  txt T_GOAL <<'EOF'
`main` and a nightly run prove everything `ci-fast` does plus integration, E2E, the full contract run, audits, static analysis, licences and the clean-clone check — while live LLM evaluations run only by hand, with secrets and a hard budget.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-007-quality-readme-ci-full.md` §4 FR-1, FR-10, §6 (workflow files), §10 rows 01, 08, 09, §11 OQ-007-03
- `context.md` → CI Quality Gates (all gates), Security Requirements 10, Dependency rules (no GPL/AGPL at runtime)
EOF
  txt T_SCOPE <<'EOF'
- `ci-full.yml` on push to `main` and nightly: everything in `ci-fast` plus Hypothesis `nightly` profile (gate 3), full schemathesis (4), integration (6), E2E (7), `pip-audit` + `pnpm audit` + licence check (8b), the clean-clone check (007/4); no call to an LLM, ORS, TIMOCOM or Cloudflare.
- CodeQL through GitHub's default setup (OQ-007-03) — configured in the repository settings by the owner, referenced here.
- `ai-evals.yml`: `workflow_dispatch` only, provider keys from GitHub Secrets, hard token budget, exits early without secrets (forks), uploads the report artefact with the metrics of FEAT-006 AC-40.
- `scripts/tests/test_workflows.py`: static checks of the YAML (triggers, pinned action SHAs, no secrets in `ci-fast`/`ci-full`).
EOF
  txt T_OUT <<'EOF'
- Deployment workflows and Docker images (post-MVP).
EOF
  txt T_FILES <<'EOF'
- `.github/workflows/ci-full.yml`, `.github/workflows/ai-evals.yml` — new (🔒 O-2)
- `scripts/tests/test_workflows.py`, `scripts/tests/fixtures/lockfiles/*` — new
- `scripts/ci/license_check.sh` (*suggested*) — new
EOF
  txt T_TESTS <<'EOF'
- A push to `main` runs gates 1–10 incl. 6, 7, 8b; any failure fails the workflow; logs show no outbound call to LLM, ORS, TIMOCOM or Cloudflare hosts. → AC-01
- Gate 8b fails on a fixture lockfile with a known high-severity advisory or a GPL/AGPL runtime licence and passes on the real lockfiles. → AC-08
- `ai-evals` has only a manual trigger, requires the secrets, stops at the budget and uploads a report. → AC-09
EOF
  txt T_VERIFY <<'EOF'
```bash
uv run pytest scripts/tests/test_workflows.py -q
gh run list --workflow ci-full --limit 3
gh workflow view ai-evals
```
EOF
  txt T_TIPS <<'EOF'
- Verify the licence-checker tool's name and version in its registry before using it.
- Pin every action to a SHA; give `ai-evals` only the permissions it needs.
- A nightly failure must be visible (status badge or notification) — otherwise nobody sees it.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-007-03 (owner): the repository is public, so CodeQL default setup is used.
EOF
}
register s_007_3

s_007_4() {
  I_ID="007/4"; I_FEAT="007"; I_TITLE="Clean-clone check, check_docs.py and the final README"
  I_AREA="infra docs"; I_SIZE="M"; I_DAY="2026-11-14"; I_CATCHUP="2026-11-15"
  I_ACS="04 05 06"; I_DEPS="007/3 O-8 O-10"
  I_GATES="scripts/clean_clone_check.sh (≤ 10 min, no keys), check_docs.py --readme --development"
  I_LOCK="\`README.md\`, \`scripts/docs_denylist.txt\` (owner content)"
  I_BRANCH="docs/FEAT-007-readme-clean-clone"; I_REQS="REQ-032, REQ-033, NFR-014"; I_ADRS="0007"; I_SCOPE_TAG="docs"
  txt T_GOAL <<'EOF'
Anyone can clone the repository and have the app running in at most ten minutes by following the README exactly — and a script proves it, along with the completeness and honesty of the README and the development guide.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-007-quality-readme-ci-full.md` §4 FR-4 … FR-7, FR-11, §8, §11 OQ-007-01, OQ-007-02
- `README.md` (current structure), `DEVELOPMENT.md` §1 (standards matrix)
- `context.md` → Project Constraints 1a, 7, 10
EOF
  txt T_SCOPE <<'EOF'
- `scripts/clean_clone_check.sh` (FR-4): fresh clone (or CI checkout), exactly the README §6 commands for API and web (`pnpm build && pnpm start` instead of `pnpm dev`), wait for `/ready`, call `/health`, log in with the demo account from `.env.example`, list drivers (expect 5), request `http://localhost:3000/login` (expect `200`), print the elapsed time; fail on any error; no API key in the environment.
- `scripts/check_docs.py` (FR-5 … FR-7): `--readme` (twelve sections in order, Polish summary ≤ 25 lines, relative links resolve, §6 commands identical to the clean-clone script, purpose statement via `scripts/docs_denylist.txt`), `--development` (14 sections; a standards-matrix row with existing proof references for standards 1–6, 7a–7e, 8a–8e), wording checks (status claims vs FEAT statuses; working-time notice where schedules are defined).
- Final README update (FR-11): status table matching what `ci-full` proves, verified commands, at least three concrete examples in "How I used AI tools" (a brief with its completion report, a defect caught by a gate, a manual correction).
EOF
  txt T_OUT <<'EOF'
- Media and the demo section's images (FEAT-009); macOS/Windows CI runners (OQ-007-01: Linux in CI + one manual run).
EOF
  txt T_FILES <<'EOF'
- `scripts/clean_clone_check.sh`, `scripts/check_docs.py`, `scripts/docs_denylist.txt` (content from O-8) — new
- `scripts/tests/test_check_docs.py`, `scripts/tests/fixtures/docs/*` — new
- `README.md`, `DEVELOPMENT.md` (only to satisfy the checks) — changed
EOF
  txt T_TESTS <<'EOF'
- `clean_clone_check.sh` in `ci-full` — README commands unchanged, API ready, demo login works, 5 drivers, web login `200`, time printed and ≤ 10 min. → AC-04
- `test_check_docs.py` — README with the sections in order and ≤ 25-line Polish summary passes; a fixture with a missing or reordered section fails → AC-05; `DEVELOPMENT.md` with 14 sections and a complete standards matrix passes, a fixture with a missing row fails → AC-06.
EOF
  txt T_VERIFY <<'EOF'
```bash
bash scripts/clean_clone_check.sh
uv run python scripts/check_docs.py --readme --development
uv run pytest scripts/tests/test_check_docs.py -q
```
EOF
  txt T_TIPS <<'EOF'
- The README is the single source of the commands; the script reads or mirrors them so that a README change without a script change fails.
- Never describe planned features as implemented; ✅ only for what `ci-full` proves.
- Purpose statement: only "an MVP with a deadline (2026-11-15), later a portfolio project".
EOF
  txt T_DECISIONS <<'EOF'
- OQ-007-01 (accepted): Linux in CI plus one manual run on the owner's machine (O-10).
- OQ-007-02 (accepted): the owner maintains `scripts/docs_denylist.txt` (O-8).
EOF
}
register s_007_4

s_007_5() {
  I_ID="007/5"; I_FEAT="007"; I_TITLE="benchmark_report.py and docs/metrics.md"
  I_AREA="engine infra"; I_SIZE="S"; I_DAY="2026-11-14"; I_CATCHUP="2026-11-14"
  I_ACS="07"; I_DEPS="003/8 004/3"
  I_GATES="scripts/benchmark_report.py run twice; make check"
  I_LOCK="\`docs/metrics.md\` (generated)"
  I_BRANCH="test/FEAT-007-metrics"; I_REQS="NFR-002"; I_ADRS="0004"; I_SCOPE_TAG="metrics"
  txt T_GOAL <<'EOF'
Every result number the README may quote comes from one reproducible report: fleet profit against both baselines, empty kilometres, capacity use, drivers home on time, and engine runtime.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-007-quality-readme-ci-full.md` §4 FR-8, §8 (timings vary), §10 row 07
- `specs/FEAT-003-optimizer-and-working-time.md` AC-29 (benchmark), invariant 15
EOF
  txt T_SCOPE <<'EOF'
- `scripts/benchmark_report.py` on the seeded demo data (fixed seed and reference date) writing `docs/metrics.md`: fleet profit of `profit` vs `baseline_single` and `baseline_greedy` (absolute and %), share of empty km, capacity utilisation (EP·km and kg·km over available), share of drivers home before `home_by`, engine runtime p50/p95 over 20 runs, node counts; with `--agents-fake` also the time from question to `approval_required` on the fake model.
- Non-timing values identical between runs; timings reported, not asserted.
EOF
  txt T_OUT <<'EOF'
- README text using the numbers (007/4).
EOF
  txt T_FILES <<'EOF'
- `scripts/benchmark_report.py`, `scripts/tests/test_benchmark_report.py` — new
- `docs/metrics.md` — generated
EOF
  txt T_TESTS <<'EOF'
- `test_benchmark_report.py` — two runs: all FR-8 metrics present, non-timing values identical, fleet profit ≥ both baselines. → AC-07
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run python ../scripts/benchmark_report.py && uv run python ../scripts/benchmark_report.py --agents-fake
uv run pytest ../scripts/tests/test_benchmark_report.py -q
```
EOF
  txt T_TIPS <<'EOF'
- Record the machine (CPU, OS) in the report header; timings are only comparable on the same machine.
EOF
}
register s_007_5
