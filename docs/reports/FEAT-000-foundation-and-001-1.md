# Report: FEAT-000 / slices 1–5 and FEAT-001 / slice 1

- Status: partial — implementation and local validation are available; a GitHub PR run, owner review and branch protection are pending. Repository-wide traceability correctly fails on later, unimplemented slices.
- Authorization: the owner approved implementation of `ci-fast` and `0001_initial`, including their missing foundation prerequisites, in this chat on 2026-11-11. This does not record a review of the resulting workflow or migration commit.
- Scope: FEAT-000 revision 5 (AC-01…13), FEAT-001 revision 4 (AC-01…03). `ci-full` and `ai-evals` remain in FEAT-007/3. No live provider call was made.
- Allowed paths used: API/web foundation and tests; root package/tooling files; `.github/workflows/ci-fast.yml`; CI and contract/traceability scripts; generated OpenAPI and traceability; README/development run notes and specification changelogs. Existing task branch: `O-2,O-3`.
- The combined change exceeds 400 manual lines because the owner explicitly included the absent API/web/tooling prerequisites and the 22-table schema. The files can be reviewed by the original slice boundaries; no PR has been opened or merged.

## Changes

- `apps/api/`: pinned Python project; FastAPI health/readiness, problem responses, request IDs, CORS, settings validation and module boundaries.
- `apps/api/src/routepilot/shared/`: integer money, unit conversion, UUIDs, injected clocks, portable SQLite column types, transactional sessions and local signing-key persistence.
- `apps/api/migrations/versions/0001_initial.py`: 22 MVP tables, declared foreign keys/uniqueness/checks/indexes, future jobs/agent fields, reverse-order downgrade; checkpoint tables remain separate.
- `apps/web/`: Node 22 / Next.js 16 shell, design tokens/fonts, cookie-based EN/PL locale switch, strict types and frontend import/HTTP boundaries.
- `.github/workflows/ci-fast.yml`: named gates 1, 2, 3, 3a, 4, 5, 8a, 8c, 9, 10 and a stable `ci-fast` result job; PR trigger, read-only permissions, commit-SHA action pins, no provider secrets.
- Root tooling/scripts: lockfiles, Makefile, pre-commit, gitleaks allowlist for exact official test/local values, reproducible OpenAPI, spec coupling and strict traceability. CI tool archives are version/digest pinned.

## Acceptance criteria and evidence

| AC | Evidence |
|---|---|
| AC-FEAT-000-01 | `scripts/tests/smoke_install.sh`; locked installation in a fresh source snapshot |
| AC-FEAT-000-02 | `tests/api/test_health.py`: readiness before/after migration, request ID/error shape, 405 `Allow` regression; live API smoke |
| AC-FEAT-000-03 | `tests/security/test_cors_skeleton.py`; live credentialed preflight |
| AC-FEAT-000-04 | `src/app/page.test.tsx`, production build and server-rendered EN/PL pages |
| AC-FEAT-000-05 | `scripts/tests/test_tooling.py`: each failing tool propagates through `make check` |
| AC-FEAT-000-06 | `scripts/tests/test_tooling.py`: generated fake key rejected/redacted by gitleaks and its staged hook; malformed Python rejected by ruff |
| AC-FEAT-000-07 | `tests/contract/test_openapi_export.py`: byte stability and deliberate drift |
| AC-FEAT-000-08 | `scripts/tests/test_trace.py`: missing/unknown ACs, draft specs, malformed metadata, failing implemented JUnit AC |
| AC-FEAT-000-09 | `scripts/tests/test_check_spec_touch.py`: guarded diff with/without a spec change |
| AC-FEAT-000-10 | `scripts/tests/test_workflows.py`, actionlint and local gate commands; GitHub green/failing-run evidence remains unverified |
| AC-FEAT-000-11 | `tests/unit/test_import_contracts.py`, `src/boundaries.test.ts`; forbidden-import fixture rejected |
| AC-FEAT-000-12 | `tests/unit/test_settings.py`, `tests/db/test_local_secret.py`: safe defaults, production rejection and key persistence |
| AC-FEAT-000-13 | `scripts/tests/test_check_spec_touch.py`: real instruction files and invalid fixtures |
| AC-FEAT-001-01 | `tests/db/test_pragmas.py`: WAL, foreign keys and busy timeout on fresh connections |
| AC-FEAT-001-02 | `tests/db/test_migrations.py`: upgrade/downgrade/upgrade, complete table set, required additions/constraints and FK check |
| AC-FEAT-001-03 | `tests/db/test_types.py`: UUID/UTC/integer money round-trip, naive datetime rejection, Decimal conversions |

## Gates and remaining work

- `make check`: passed — lint, strict Python/TypeScript types, 33 backend/tooling tests, 2 Vitest tests and 30 architecture contracts.
- `make test-db`: passed — 5 migration/type/PRAGMA/key-persistence tests.
- `next build`: production build under Node 22.23.4; EN/PL HTTP responses verified.
- API smoke and Schemathesis subset: 18 generated cases passed. The probe found a missing 405 `Allow` header; a regression test preceded the fix.
- `actionlint`: workflow definition passes.
- All pre-commit hooks passed on an isolated staged source snapshot, including the real staged gitleaks hook. The only formatter correction was an extra final blank line in the new API manifest.
- Locked installs and TypeScript checking passed in a fresh source snapshot. Gitleaks scanned the complete source snapshot (about 1.5 MB) and found no leaks.
- `trace.py --check`: **fails**, reporting 168 untested approved ACs in later slices; all 16 in-scope ACs are mapped. The checker discovers 191 declared ACs in total. No spec status or assertion was weakened to make this gate pass.
- Agent collection is intentionally empty under FEAT-000 FR-16; pytest exit code 5 alone is accepted. Import errors and assertion failures remain errors.
- No GitHub run was dispatched, no PR approval/comment submitted, and branch protection was not changed. After the first green GitHub run, the owner can require the stable `ci-fast` status on `main`.
- `ci-full`, `ai-evals`, provider budgets, product feature tests and the full MVP clean-clone scenario are outside this scope.

## Dependencies and assumptions

- Registry verification used PyPI and npm on 2026-11-11; exact versions and transitive integrity values are in the two lockfiles. Runtime choices follow the approved stack: FastAPI/Pydantic/settings, SQLAlchemy/Alembic, structlog/uvicorn; Next/React/next-intl. No additional service or runtime agent was added.
- Runtime licence metadata: MIT (FastAPI, Pydantic, settings, SQLAlchemy, Alembic, Next, React, next-intl), MIT OR Apache-2.0 (structlog), BSD-3-Clause (uvicorn). These are the prescribed stack; no alternative architecture was introduced.
- `defusedxml` has PSFL licence metadata and is a development dependency for safe JUnit parsing; PyYAML (MIT) is a development dependency for workflow/spec parsing. All other additions are the specified test, lint, formatting and build tools. Native build scripts are allowed only for the pinned `@swc/core` and `@parcel/watcher` versions.
- Domain results use integer database units. Decimal fractions such as pallet equivalents and margins use text; structured snapshots use JSON. Agent/explanation cost estimates carry an explicit `currency TEXT(3)` alongside their minor units, following the common money convention. Assignment uniqueness across active rows stays in the later service, as specified.
- The foundation is not the complete application: CRUD, authentication and seed data have not been implemented. Specification statuses remain `approved` until the required completion evidence exists.
- Existing project-context phase text and the generated owner-action dependencies have not been changed. The owner's authorization in this chat permits preparing this implementation; final approval remains per resulting change.
