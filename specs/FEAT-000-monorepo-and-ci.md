---
id: FEAT-000
title: Monorepo, tooling and ci-fast
status: approved
owner: project owner
requirements: [REQ-021, REQ-032, REQ-033, NFR-008, NFR-009, NFR-013, NFR-014]
adrs: [ADR-0001, ADR-0007, ADR-0009, ADR-0015]
modules: [repo root, apps/api (skeleton), apps/web (skeleton), scripts, .github/workflows]
revision: 5
---

# FEAT-000: Monorepo, tooling and ci-fast

Priority: **P0**. Foundation implementation is available for review; GitHub CI and owner review are pending. Status remains `approved`.

## 1. Goal

A repository skeleton in which both applications install, start and pass a blocking pull-request pipeline (`ci-fast`) before any feature code is written: `apps/api` (FastAPI) and `apps/web` (Next.js) in separate folders, shared tooling, `.env.example` files that work unmodified, scripts for the OpenAPI contract and traceability, and agent-instruction files that stay consistent.

## 2. Business context

The project is built by AI coding agents behind quality gates ([`docs/report.md`](../docs/report.md) §24–27). Gates must exist from the first commit, otherwise later specifications cannot be verified. The local run must need no Docker, no database server and no API keys ([`context.md`](../context.md) → Project Constraints 1a).

## 3. Scope / Out of scope

**In scope**

- Workspace layout as in [`DEVELOPMENT.md`](../DEVELOPMENT.md) §3.
- API skeleton: FastAPI app factory, layered package folders, settings (pydantic-settings), structured logging with `request_id`, `/health`, `/ready`, CORS middleware, problem+json error handler.
- Web skeleton: Next.js 16 App Router, TypeScript strict, Tailwind themed from [`docs/design/tokens.json`](../docs/design/tokens.json) (CSS variables in `apps/web/src/styles/tokens.css`, Tailwind default palette off) and the three fonts of the design system through `next/font` (ADR-0015; no shadcn/ui), next-intl with `en` and `pl` and a language switch, a placeholder home page.
- `.env.example` for both apps.
- `Makefile` shortcuts, pre-commit configuration.
- `ci-fast` workflow.
- Scripts: `scripts/export_openapi.py`, `scripts/trace.py`, `scripts/check_spec_touch.py`.
- Consistency check for `AGENTS.md` / `CLAUDE.md`.

**Out of scope**

- Any domain model, table or business endpoint (FEAT-001 and later).
- `ci-full`, E2E, `ai-evals` (FEAT-007).
- Docker images and deployment (post-MVP, ADR-0007).

## 4. Functional requirements

- **FR-1 Workspace.** A pnpm workspace at the root that contains `apps/web`; a uv project in `apps/api` with `uv.lock`. Lockfiles are committed.
- **FR-2 API skeleton.** `routepilot.main:app` starts with `uv run uvicorn routepilot.main:app --port 8000`. Package folders exist for every module of `context.md` → Module Boundaries, each with an `__init__.py` and a one-line docstring.
- **FR-3 Health.** `GET /health` returns `200 {"status":"ok"}` when the process is alive. `GET /ready` returns `200` when the database is reachable and the applied migration equals the head revision; otherwise `503` with problem+json `code = NOT_READY`.
- **FR-4 CORS.** `CORSMiddleware` configured from `CORS_ALLOWED_ORIGINS` exactly as in `DEVELOPMENT.md` §4.9. The app refuses to start when the list contains `*`.
- **FR-5 Errors.** One exception handler converts `DomainError(code)`, validation errors and unexpected errors to RFC 9457 problem+json with `code` and `requestId`.
- **FR-6 Logging.** `structlog` JSON logs; every request log line carries `request_id` (generated or taken from `X-Request-ID`).
- **FR-7 Web skeleton.** `pnpm dev` serves `http://localhost:3000`; the page renders a title from `messages/*.json` and a language switch that changes it between English and Polish; the API base URL comes from `NEXT_PUBLIC_API_BASE_URL`.
- **FR-8 Environment files.** `apps/api/.env.example` and `apps/web/.env.example` list every variable of `DEVELOPMENT.md` §6.1 with safe defaults. A copy without edits is enough to start both apps.
- **FR-9 Makefile.** Targets: `check` (lint + types + unit tests for both apps), `test-props`, `test-agents`, `test-db`, `openapi`, `trace`, `e2e`, `bench`, `dev-api`, `dev-web`, `seed-fleet`. Targets for later features exist and print "not available until FEAT-xxx" instead of failing silently. The README never requires `make`.
- **FR-10 pre-commit.** Hooks: ruff format and check, Prettier, ESLint on staged files, gitleaks, end-of-file and trailing-whitespace fixers.
- **FR-11 `export_openapi.py`.** Imports the app, writes `contracts/openapi.json` with sorted keys and a trailing newline. Running it twice gives byte-identical output. `--check` exits non-zero when the committed file differs.
- **FR-12 `trace.py`.** Parses `specs/FEAT-*.md` for AC IDs and status, scans tests for `@pytest.mark.ac("…")` and `[AC-…]` titles, optionally reads JUnit XML, writes `docs/traceability.md`. `--check` fails when an AC of an `approved`/`implemented` specification has no test, when a test names an unknown AC, or when an `implemented` specification has a failing test.
- **FR-13 `check_spec_touch.py`.** Given a git diff range, fails when files under `contracts/`, `apps/api/migrations/`, `apps/api/src/routepilot/agents/prompts/` or `apps/api/src/routepilot/agents/tools/` changed and no file under `specs/` changed in the same range.
- **FR-14 Agent-instruction files in sync.** A check (`check_spec_touch.py --agent-docs`) verifies: `CLAUDE.md` starts with the line `@AGENTS.md`; `AGENTS.md` has at most 150 lines and mentions `context.md`; neither file contains a path listed as a command or file in "Project quick facts" that contradicts the repository (each path marked as existing must exist).
- **FR-15 Architecture rules.** import-linter contracts encode the backend table of `context.md` → Module Boundaries and the layer order `api → service → domain / repository`. ESLint boundaries encode the frontend feature rules.
- **FR-16 `ci-fast`.** A GitHub Actions workflow on pull requests that runs gates 1, 2, 3, 3a, 4, 5, 8a, 8c, 9 and 10 of `context.md` → CI Quality Gates. In FEAT-000, gates with no tests yet (3a, 5, 8c) run and pass on an empty test set; they become meaningful as features land.

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| NFR-014 | A new contributor can install both apps | `uv sync` and `pnpm install` succeed on a clean clone with only the prerequisites of the README |
| NFR-013 | Boundaries are enforced automatically | a deliberately forbidden import fails `make check` |
| NFR-009 | The contract cannot drift | `export_openapi.py --check` fails on a stale file |
| NFR-008 | No secrets in the repository | gitleaks passes; a planted fake key is detected |
| — | Pipeline speed | `ci-fast` target ≤ 8 minutes (measured, not blocking in FEAT-000) |
| — | Reproducible tooling | Python 3.13 and Node.js 22 LTS pinned (`.python-version`, `engines` / `.nvmrc`); GitHub Actions pinned to commit SHAs |

## 6. Contracts (API, data/migrations, ports, agent tools)

**API**

| Method | Path | Auth | Success | Errors |
|---|---|---|---|---|
| GET | `/health` | none | `200 {"status":"ok"}` | — |
| GET | `/ready` | none | `200 {"status":"ready","migration":"<rev>"}` | `503` problem+json `NOT_READY` |

Both endpoints are part of `contracts/openapi.json`.

**Data / migrations:** an empty Alembic environment with `render_as_batch=True`; the first real migration belongs to FEAT-001.

**Ports:** `Clock` protocol in `shared` (`now() -> datetime`, UTC aware) with `SystemClock` and `FixedClock`.

**Configuration:** the variables of `DEVELOPMENT.md` §6.1. Settings validation rules: `CORS_ALLOWED_ORIGINS` must not contain `*`; `APP_ENV=production` with Turnstile test keys, an empty `SECRET_KEY` or the default demo passwords is a startup error.

**Agent tools:** No change.

**Workflow file:** `.github/workflows/ci-fast.yml`. Changing workflow files needs human approval (`context.md` → Operations that need human confirmation).

## 7. Acceptance criteria

- **AC-FEAT-000-01** [integration] Given a clean clone with Python 3.13, uv, Node.js 22 and pnpm When `uv sync` runs in `apps/api` and `pnpm install` runs in the root Then both finish with exit code 0 using only the committed lockfiles.
- **AC-FEAT-000-02** [integration] Given an unmodified copy of `.env.example` and an applied (empty) migration head When the API starts and `GET /health` and `GET /ready` are called Then both return `200`; and Given a database whose revision is behind head When `GET /ready` is called Then it returns `503` with `code = NOT_READY`.
- **AC-FEAT-000-03** [contract] Given `CORS_ALLOWED_ORIGINS=http://localhost:3000` When an `OPTIONS` preflight for `GET /health` arrives with `Origin: http://localhost:3000` Then the response carries `Access-Control-Allow-Origin: http://localhost:3000` and `Access-Control-Allow-Credentials: true`; and When the origin is `http://evil.example` Then no `Access-Control-Allow-Origin` header is present.
- **AC-FEAT-000-04** [unit] Given the web skeleton When the home page renders with locale `en` and then `pl` Then the title comes from `messages/en.json` and `messages/pl.json` respectively, and `pnpm build` (`next build`) and `tsc --noEmit` succeed.
- **AC-FEAT-000-05** [integration] Given the repository When `make check` runs Then ruff, mypy `--strict`, ESLint (`--max-warnings=0`), Prettier check, `tsc --noEmit`, pytest unit tests and Vitest all run, and the target fails if any of them fails.
- **AC-FEAT-000-06** [integration] Given a staged file that contains a string shaped like an API key When `pre-commit run` executes Then the gitleaks hook fails; and Given a badly formatted Python file Then the ruff hook fails or fixes it.
- **AC-FEAT-000-07** [contract] Given the app When `scripts/export_openapi.py` runs twice Then the two outputs are byte-identical; and Given a committed `contracts/openapi.json` that differs from the app When `export_openapi.py --check` runs Then it exits non-zero.
- **AC-FEAT-000-08** [unit] Given a fixture specification with status `approved` and an AC without a test When `trace.py --check` runs Then it fails and names the AC; Given a test that references `AC-FEAT-999-01` Then it fails and names the test; Given a `draft` specification with untested ACs Then it passes.
- **AC-FEAT-000-09** [unit] Given a diff that changes `contracts/openapi.json` and no file under `specs/` When `check_spec_touch.py` runs Then it fails; Given the same diff plus a change under `specs/` Then it passes.
- **AC-FEAT-000-10** [integration] Given a pull request When `ci-fast` runs Then gates 1, 2, 3, 3a, 4, 5, 8a, 8c, 9 and 10 run as separate, named jobs or steps, any failure marks the workflow as failed, and no step uses the network for LLM, ORS or TIMOCOM calls.
- **AC-FEAT-000-11** [unit] Given the import-linter configuration When a test module adds `import routepilot.agents` inside `routepilot.optimization.engine` (fixture) Then `lint-imports` fails; and the contracts cover every row of the backend Module Boundaries table.
- **AC-FEAT-000-12** [unit] Given `apps/api/.env.example` and `apps/web/.env.example` When they are scanned Then they contain every variable of `DEVELOPMENT.md` §6.1, no LLM/ORS key value, and no key material other than the Cloudflare Turnstile test keys and local demo passwords; and Given `APP_ENV=production` with those defaults When settings load Then startup fails with a clear message.
- **AC-FEAT-000-13** [unit] Given `AGENTS.md` and `CLAUDE.md` When `check_spec_touch.py --agent-docs` runs Then it passes only if `CLAUDE.md` starts with `@AGENTS.md`, `AGENTS.md` has ≤ 150 lines, and both reference `context.md`.

## 8. Edge cases

- `CORS_ALLOWED_ORIGINS` with a trailing slash or spaces → normalised; an empty list → startup error in non-test environments.
- `SECRET_KEY` empty with `APP_ENV=local` → a random key is generated on first start and stored (in `app_meta` once FEAT-001 exists; until then in memory with a warning).
- A specification with malformed front matter → `trace.py` fails with the file name.
- Windows line endings in `contracts/openapi.json` → `.gitattributes` forces LF.
- Port already in use → documented in `DEVELOPMENT.md` §6.2, not handled by code.

## 9. Dependencies

- ADR-0001 (stack), ADR-0007 (local run), ADR-0009 (contracts).
- Tool and library versions: [`docs/report.md`](../docs/report.md) §9.2. Verify each package and version in its registry before adding it; do not add a package that is not listed there without a justification in the completion report.
- Shared files created here: lockfiles, `Makefile`, `.env.example`, `.github/workflows/ci-fast.yml`, `contracts/openapi.json`.

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| 01, 05, 06, 10 | verified in CI job logs and a `scripts/tests/` smoke script | clean runner |
| 02, 03 | `apps/api/tests/api/test_health.py`, `apps/api/tests/security/test_cors_skeleton.py` | in-memory app |
| 04 | `apps/web/src/app/page.test.tsx` | `messages/*.json` |
| 07 | `apps/api/tests/contract/test_openapi_export.py` | temporary output path |
| 08, 09, 13 | `scripts/tests/test_trace.py`, `test_check_spec_touch.py` | fixture specs and fixture diffs under `scripts/tests/fixtures/` |
| 11 | `apps/api/tests/unit/test_import_contracts.py` | fixture module |
| 12 | `apps/api/tests/unit/test_env_example.py`, `test_settings.py` | the `.env.example` files |

## 11. Open questions

**Owner decisions (2026-11-11):** all proposed defaults in this table are accepted. OQ-000-04 is settled by a registry check made on this date: pin TypeScript 6.0.x (6.0.3 on this date), because `typescript-eslint` 8.72.2 declares `typescript >=4.8.4 <6.1.0`; check again on implementation day.

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-000-01 | `context.md` Gate 9 says "API image + `/health`, `/ready`"; the MVP has no Docker image (ADR-0007). `docs/report.md` §26 says "start `uvicorn` with an empty DB file". Which wording is binding? | Follow the report: start `uvicorn`, call `/health`, `/ready` and one CORS preflight. Update the Gate 9 text in `context.md` on approval. | AC-FEAT-000-10 wording |
| OQ-000-02 | `context.md` lists `psycopg 3` in the backend stack although the MVP uses only SQLite. Install it now? | Do not install in the MVP; add it with the PostgreSQL work (ADR-0002). | nothing |
| OQ-000-03 | Exact minimum versions of uv and pnpm to state in the README. | Record the versions used on the day FEAT-000 is implemented and pin pnpm through `packageManager`. | README prerequisites table |
| OQ-000-04 | TypeScript version: the registry shows 7.0.2, and `context.md` asks for "a version supported by Next.js/ESLint". | Pin the newest version that Next.js 16 and typescript-eslint both support on implementation day; record it in the completion report (risk R12). | nothing |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-09 | Initial draft |
| 2 | 2026-11-11 | Owner decisions on the open questions recorded (§11); TypeScript 6.0.x |
| 3 | 2026-11-11 | Status `draft` → `approved` by the owner |
| 4 | 2026-11-11 | Owner decision ADR-0015: the web skeleton sets up the design tokens and fonts of `docs/design/` instead of shadcn/ui (§3). No AC changed. Front-matter `revision` aligned with this changelog |
| 5 | 2026-11-11 | Foundation implementation, tests and `ci-fast` definition added for review. No AC changed; strict repository-wide traceability remains blocking. Validation: `docs/reports/FEAT-000-foundation-and-001-1.md`. |
