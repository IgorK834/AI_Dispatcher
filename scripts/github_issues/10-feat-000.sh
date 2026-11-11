# FEAT-000 — Monorepo and ci-fast. Sourced by scripts/create_github_issues.sh.
# shellcheck shell=bash disable=SC2034

s_000_1() {
  I_ID="000/1"; I_FEAT="000"; I_TITLE="API skeleton: app factory, settings, logging, /health, /ready, CORS, problem+json"
  I_AREA="infra backend"; I_SIZE="M"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-11"
  I_ACS="02 03 12"; I_DEPS="O-1"
  I_GATES="ruff check + format, mypy --strict, pytest (make check arrives in 000/3)"
  I_LOCK="\`apps/api/uv.lock\`, \`apps/api/.env.example\`, \`apps/web/.env.example\`"
  I_BRANCH="feat/FEAT-000-api-skeleton"; I_REQS="REQ-032, NFR-008, NFR-014"; I_ADRS="0001 0007 0009"; I_SCOPE_TAG="api"
  txt T_GOAL <<'EOF'
A FastAPI application that starts with one command on a clean machine, answers `/health` and `/ready`, speaks problem+json, logs JSON with a `request_id`, enforces the CORS allowlist and refuses unsafe production settings. Every later backend slice builds on this skeleton.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-000-monorepo-and-ci.md` §3 (scope), §4 FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-8, §6 (API table, ports, configuration rules), §8 (edge cases), §11 (OQ-000-02, OQ-000-04)
- `DEVELOPMENT.md` §2 (layers), §3 (repository layout), §4.5 (problem+json shape), §4.9 (CORS and CSRF), §6.1 (environment variables)
- `context.md` → Selected Technology Stack, Module Boundaries (backend table), External Integration Contracts (CORS)
- `docs/report.md` §9.2 (tool and library versions to verify)
EOF
  txt T_SCOPE <<'EOF'
- uv project in `apps/api` (`pyproject.toml`, committed `uv.lock`, `.python-version` = 3.13) with the package `routepilot` under `src/`.
- One package folder per backend module of `context.md` → Module Boundaries: `shared`, `identity`, `fleet`, `freight`, `routing`, `compliance`, `optimization/engine`, `optimization/jobs`, `agents`, `integrations` — each with an `__init__.py` and a one-line docstring (FR-2).
- `routepilot.main:app` built by an app factory; settings through pydantic-settings covering every variable of `DEVELOPMENT.md` §6.1.
- Settings validation: `CORS_ALLOWED_ORIGINS` normalised (trailing slash, spaces), `*` → startup error, empty list → error outside `test`; `APP_ENV=production` with the Turnstile test keys, an empty `SECRET_KEY` or the default demo passwords → startup error with a clear message.
- `SECRET_KEY` empty with `APP_ENV=local` → a random key in memory with a warning (it is persisted in `app_meta` once FEAT-001 exists).
- structlog JSON logging; a middleware that takes `X-Request-ID` or generates one, binds it to every log line and returns it.
- One exception handler: `DomainError(code)`, validation errors and unexpected errors → RFC 9457 problem+json with `code` and `requestId` (no stack trace unless `APP_ENV=local`).
- `GET /health` and `GET /ready` (database reachable and applied revision = Alembic head, otherwise `503 NOT_READY`); an empty Alembic environment with `render_as_batch=True`.
- `CORSMiddleware` from `CORS_ALLOWED_ORIGINS` with `allow_credentials=True`, as in `DEVELOPMENT.md` §4.9.
- `Clock` protocol with `SystemClock` and `FixedClock` in `shared`.
- `apps/api/.env.example` and `apps/web/.env.example` with every variable of `DEVELOPMENT.md` §6.1 and safe defaults (the web skeleton of 000/2 only reads its file).
- `.gitignore` entries for `.env`, `apps/api/data/`, `*.db`, `*.db-wal`, `*.db-shm`; `.gitattributes` forcing LF.
EOF
  txt T_OUT <<'EOF'
- Any domain table, model or business endpoint (FEAT-001 and later); the first real migration (001/1).
- The web app (000/2), the Makefile, pre-commit and import-linter (000/3), the OpenAPI export and other scripts (000/4), the workflow (000/5).
- `psycopg` and anything PostgreSQL (OQ-000-02: not in the MVP); Docker (ADR-0007).
EOF
  txt T_FILES <<'EOF'
- `apps/api/pyproject.toml`, `apps/api/uv.lock`, `apps/api/.python-version`, `apps/api/alembic.ini`, `apps/api/migrations/env.py`, `apps/api/migrations/script.py.mako` — new
- `apps/api/src/routepilot/main.py`, `apps/api/src/routepilot/*/__init__.py` (all modules) — new
- `apps/api/src/routepilot/shared/{config.py,clock.py,errors.py,logging.py,problem.py}` — new (*suggested* file names)
- `apps/api/src/routepilot/shared/api/health.py` (*suggested*) — new
- `apps/api/.env.example`, `apps/web/.env.example` — new
- `apps/api/tests/api/test_health.py`, `apps/api/tests/security/test_cors_skeleton.py`, `apps/api/tests/unit/test_env_example.py`, `apps/api/tests/unit/test_settings.py`, `apps/api/tests/conftest.py` — new
- `.gitignore`, `.gitattributes` — new
EOF
  txt T_IFACE <<'EOF'
```text
GET /health -> 200 {"status": "ok"}
GET /ready  -> 200 {"status": "ready", "migration": "<rev>"}
            -> 503 application/problem+json {type, title, status, code: "NOT_READY", requestId}
```

```python
class Clock(Protocol):                 # shared/clock.py
    def now(self) -> datetime: ...     # always UTC-aware
class SystemClock: ...                 # implements Clock
class FixedClock:                      # implements Clock; for tests
    def __init__(self, at: datetime) -> None: ...

class DomainError(Exception):          # shared/errors.py — mapped to problem+json by the shared handler
    code: str                          # stable machine-readable code, e.g. "NOT_READY"

def create_app(settings: Settings | None = None) -> FastAPI: ...   # suggested name; main.py exposes `app`
```

Problem body (`DEVELOPMENT.md` §4.5): `{type, title, status, detail?, instance?, code, requestId, errors?[{field, code, message}]}`, content type `application/problem+json`.
EOF
  txt T_TESTS <<'EOF'
- `tests/api/test_health.py` — `/health` 200; `/ready` 200 with an applied (empty) head; `/ready` 503 `NOT_READY` when the database revision is behind head (use a temporary Alembic script directory with one fixture revision). → AC-02
- `tests/security/test_cors_skeleton.py` — preflight from `http://localhost:3000` gets `Access-Control-Allow-Origin` + `Allow-Credentials: true`; from `http://evil.example` gets no `Access-Control-Allow-Origin`. → AC-03
- `tests/unit/test_env_example.py` — both `.env.example` files contain every variable of `DEVELOPMENT.md` §6.1, no LLM/ORS key value, no key material other than the Turnstile test keys and local demo passwords. → AC-12
- `tests/unit/test_settings.py` — `APP_ENV=production` with the defaults fails with a clear message; `*` in the allowlist fails; trailing slash and spaces are normalised. → AC-12
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv sync && uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src
cp .env.example .env && uv run uvicorn routepilot.main:app --port 8000
curl -i http://localhost:8000/health
curl -i -X OPTIONS http://localhost:8000/health -H 'Origin: http://localhost:3000' -H 'Access-Control-Request-Method: GET'
```
EOF
  txt T_TIPS <<'EOF'
- With zero Alembic revisions the head is `None`; make "applied == head" handle that case explicitly, and test the "behind head" case with a fixture revision rather than with production migrations.
- Verify every package and version in its registry before adding it (`docs/report.md` §9.2 lists them); record the versions in the completion report. TypeScript is not part of this slice.
- `X-Request-ID` from the client is accepted only if it looks like an id (length limit); otherwise generate one — it ends up in logs.
- `.env.example` may contain the public Turnstile test keys and local demo passwords (OQ-001-04); the production guard must reject exactly those values.
- Keep handlers thin: health and readiness live in `shared` (or `main.py` wiring) — no business module exists yet.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-000-02 (accepted): do not install `psycopg` in the MVP.
- OQ-000-03 (accepted): record the uv and pnpm versions used on implementation day for the README prerequisites.
- OQ-001-04 (accepted): fixed local demo passwords in `.env.example` are allowed; they are rejected when `APP_ENV` is not `local`/`test`.
EOF
}
register s_000_1

s_000_2() {
  I_ID="000/2"; I_FEAT="000"; I_TITLE="Web skeleton: Next.js 16, TypeScript strict, Tailwind with design tokens, next-intl EN/PL"
  I_AREA="infra frontend"; I_SIZE="M"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-11"
  I_ACS="04"; I_DEPS="O-1"
  I_GATES="pnpm lint, tsc --noEmit, vitest, next build"
  I_LOCK="\`pnpm-lock.yaml\`, \`apps/web/messages/*.json\`, root \`package.json\` / \`pnpm-workspace.yaml\`"
  I_BRANCH="feat/FEAT-000-web-skeleton"; I_REQS="REQ-021, REQ-032, NFR-014"; I_ADRS="0001 0007 0015"; I_SCOPE_TAG="web"
  txt T_GOAL <<'EOF'
A Next.js web app that installs from the committed lockfile, renders a home page whose title comes from `messages/en.json` / `messages/pl.json`, switches language, builds with `next build` and passes strict type checks. Every frontend slice builds on it.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-000-monorepo-and-ci.md` §4 FR-1, FR-7, §5 (pinned runtimes), §11 OQ-000-04 (TypeScript pin)
- `specs/FEAT-005-frontend.md` §6 (message namespaces, configuration) — read only, to name things consistently
- `DEVELOPMENT.md` §2.3 (frontend structure), §3 (layout), §9 (UX guidelines and design system in short), §6.1 (web variables)
- `docs/design/README.md` §2 (colour), §3 (type), §4 (space, shape, elevation), §11 (implementation notes); values in `docs/design/tokens.json`
- `docs/adr/ADR-0015-frontend-ui-components-and-design-system.md` (no shadcn/ui)
- `context.md` → Selected Technology Stack (web row), Module Boundaries → Frontend, Coding Standards → TypeScript
EOF
  txt T_SCOPE <<'EOF'
- pnpm workspace at the root (`package.json` with `packageManager`, `pnpm-workspace.yaml` containing `apps/web`), committed `pnpm-lock.yaml`; Node.js 22 LTS pinned (`.nvmrc` and `engines`).
- `apps/web`: Next.js 16 App Router, React 19, TypeScript strict with `noUncheckedIndexedAccess`, TypeScript pinned to 6.0.x (OQ-000-04 — re-check the typescript-eslint peer range on the day).
- Tailwind themed from `docs/design/tokens.json`: CSS variables in `apps/web/src/styles/tokens.css`, colours, fonts, radii and shadows in the Tailwind theme, Tailwind's default palette switched off (ADR-0015; no shadcn/ui, no component kit).
- The three design-system fonts (Inter, Inter Tight, JetBrains Mono) through `next/font/google`; page background, text colours and the red focus ring applied in `globals.css` from the tokens.
- next-intl with locales `en` and `pl`, the locale stored in a cookie and applied on the server render; a language switch on the home page.
- `messages/en.json` and `messages/pl.json` with the namespaces of FEAT-005 §6 (`common`, `auth`, `fleet`, `offers`, `plans`, `optimizer`, `chat`, `admin`, `errors`, `rejections`, `warnings`, `legal`) — only the keys the placeholder page needs.
- ESLint (next, @typescript-eslint, jsx-a11y) with `--max-warnings=0`, Prettier, Vitest + Testing Library set up.
- The API base URL read from `NEXT_PUBLIC_API_BASE_URL` (file `apps/web/.env.example` comes from 000/1).
EOF
  txt T_OUT <<'EOF'
- Any screen of FEAT-005, the typed API client, SSE helper and `lib/format` (005/1), the Turnstile widget (005/2), MapLibre.
- The "no hard-coded strings" lint rule and the key-parity check (005/1), ESLint feature boundaries (000/3).
- Base components (`components/ui/`), `VanSide`, Radix UI primitives and the token lint rule (005/1).
- Dark theme, mobile-first layout (out of the MVP).
EOF
  txt T_FILES <<'EOF'
- `package.json`, `pnpm-workspace.yaml`, `pnpm-lock.yaml`, `.nvmrc`, `.prettierrc`, `.prettierignore` — new
- `apps/web/package.json`, `apps/web/next.config.ts`, `apps/web/tsconfig.json`, `apps/web/eslint.config.mjs`, `apps/web/vitest.config.ts`, `apps/web/postcss.config.mjs`, `apps/web/tailwind.config.ts` (if the installed Tailwind major still uses one; otherwise the theme lives in `globals.css`) — new
- `apps/web/src/styles/tokens.css` (generated from or hand-copied from `docs/design/tokens.json`) — new
- `apps/web/src/app/{layout.tsx,page.tsx,globals.css}`, `apps/web/src/i18n/*` (next-intl request config), `apps/web/src/components/language-switch.tsx` — new
- `apps/web/messages/en.json`, `apps/web/messages/pl.json` — new
- `apps/web/src/app/page.test.tsx` — new
EOF
  txt T_IFACE <<'EOF'
- Scripts in `apps/web/package.json`: `dev` (port 3000), `build`, `start`, `lint`, `typecheck` (`tsc --noEmit`), `test` (`vitest run`), `format:check`.
- Message key for the title (*suggested*): `common.appTitle`; the switch labels `common.language.en` / `common.language.pl`.
EOF
  txt T_TESTS <<'EOF'
- `src/app/page.test.tsx` — `[AC-FEAT-000-04]` renders the home page with locale `en` and then `pl` and asserts the title text comes from the respective messages file.
- CI-like checks in the same PR: `pnpm --filter web build` and `pnpm --filter web typecheck` succeed (also part of AC-04).
EOF
  txt T_VERIFY <<'EOF'
```bash
corepack enable && pnpm install --frozen-lockfile
pnpm --filter web lint && pnpm --filter web typecheck && pnpm --filter web test
pnpm --filter web build
pnpm --filter web dev   # open http://localhost:3000 and switch EN ↔ PL
```
EOF
  txt T_TIPS <<'EOF'
- Check the next-intl App Router setup against the documentation of the installed version (the API changed between majors) — do not write it from memory.
- TypeScript 7 exists in the registry but typescript-eslint 8.72.2 accepts `<6.1.0`; pin 6.0.x unless a re-check on the day shows a newer supported pair (record it).
- Keep every visible string in the messages files from the first commit; 005/1 adds a lint rule that will fail on literals.
- Polish needs ICU plural rules later (1 / 2–4 / 5+); keep next-intl's ICU message format.
- Check how the installed Tailwind major defines a theme (config file vs. CSS `@theme`) before wiring the tokens; keep the token names of `tokens.json` so later slices can grep them.
- The language switch is the design system's segmented control: selected segment white with red text (`docs/design/README.md` §6).
EOF
  txt T_DECISIONS <<'EOF'
- OQ-000-04 (settled 2026-11-11): pin TypeScript 6.0.x (6.0.3 on that date); check again on implementation day.
- ADR-0015 (owner, 2026-11-11): own design system "Clear Route v3" on Tailwind + Radix UI primitives; shadcn/ui is not used.
EOF
}
register s_000_2

s_000_3() {
  I_ID="000/3"; I_FEAT="000"; I_TITLE="Tooling: Makefile, pre-commit with gitleaks, import-linter and ESLint boundaries"
  I_AREA="infra"; I_SIZE="M"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-11"
  I_ACS="01 05 06 11"; I_DEPS="000/1 000/2"
  I_GATES="make check, pre-commit run --all-files, lint-imports"
  I_LOCK="\`Makefile\`, \`.pre-commit-config.yaml\`, lockfiles (dev dependencies)"
  I_BRANCH="chore/FEAT-000-tooling"; I_REQS="NFR-008, NFR-013, NFR-014"; I_ADRS="0001 0009"; I_SCOPE_TAG="tooling"
  txt T_GOAL <<'EOF'
One command (`make check`) runs every fast check of both apps, pre-commit stops secrets and badly formatted code before they are committed, and the architecture boundaries of `context.md` are enforced by tools instead of by convention.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-000-monorepo-and-ci.md` §4 FR-9, FR-10, FR-15, §5 (NFR-013, NFR-008), §10 (test plan rows 01, 05, 06, 11)
- `context.md` → Module Boundaries (both tables), CI Quality Gates (gates 1, 2, 3, 8a, 10), Security Requirements 6
- `DEVELOPMENT.md` §2.2 (module boundaries), §7 (commands), §8 (gates), §13 (secrets)
EOF
  txt T_SCOPE <<'EOF'
- `Makefile` targets: `check` (ruff format --check, ruff check, mypy --strict, pytest unit, Prettier check, ESLint, `tsc --noEmit`, Vitest — fails if any fails), `test-props`, `test-agents`, `test-db`, `openapi`, `trace`, `e2e`, `bench`, `dev-api`, `dev-web`, `seed-fleet`. Targets for later features exist and print "not available until FEAT-xxx" with a non-zero exit (FR-9).
- `.pre-commit-config.yaml`: ruff format and check, Prettier, ESLint on staged files, gitleaks, end-of-file and trailing-whitespace fixers (FR-10).
- `.gitleaks.toml` with an allowlist for exactly the Cloudflare Turnstile test keys and the local demo passwords (OQ-001-04).
- import-linter contracts in `apps/api/pyproject.toml` (or `.importlinter`) encoding every row of the backend Module Boundaries table and the layer order `api → service → domain / repository` (FR-15).
- ESLint boundaries for the frontend: `features/x` imports `features/y` only through `index.ts`; `fetch` only under `lib/api/` (FR-15).
- A smoke script for the clean install (AC-01) under `scripts/tests/`.
EOF
  txt T_OUT <<'EOF'
- The CI workflow (000/5); the OpenAPI, trace and spec-touch scripts (000/4) — `make openapi` / `make trace` print "not available until 000/4" until then.
- Any real test of later features; coverage thresholds enforcement in CI (007/1).
EOF
  txt T_FILES <<'EOF'
- `Makefile`, `.pre-commit-config.yaml`, `.gitleaks.toml` — new
- `apps/api/pyproject.toml` (import-linter contracts, dev dependencies), `apps/api/uv.lock` — changed
- `apps/web/eslint.config.mjs`, `apps/web/package.json`, `pnpm-lock.yaml` — changed (boundaries plugin)
- `apps/api/tests/unit/test_import_contracts.py`, `apps/api/tests/fixtures/import_violation/` — new
- `scripts/tests/smoke_install.sh`, `scripts/tests/smoke_check.sh` (*suggested*) — new
EOF
  txt T_IFACE <<'EOF'
```text
make check | test-props | test-agents | test-db | openapi | trace | e2e | bench | dev-api | dev-web | seed-fleet
```
Each target is a thin wrapper around the direct command that the README documents; the README never requires `make`.
EOF
  txt T_TESTS <<'EOF'
- `tests/unit/test_import_contracts.py` — a fixture module that does `import routepilot.agents` from inside `routepilot.optimization.engine` makes `lint-imports` fail; a check that every row of the backend Module Boundaries table has a contract. → AC-11
- `scripts/tests/smoke_install.sh` — clean clone + `uv sync` + `pnpm install --frozen-lockfile` exit 0. → AC-01
- `scripts/tests/smoke_check.sh` — `make check` runs every listed tool and fails when one tool fails (inject a failing fixture). → AC-05
- A pre-commit test: a staged file with a fake key-shaped string makes the gitleaks hook fail; a badly formatted Python file is fixed or rejected by ruff. → AC-06
EOF
  txt T_VERIFY <<'EOF'
```bash
make check
pre-commit install && pre-commit run --all-files
cd apps/api && uv run lint-imports
bash scripts/tests/smoke_install.sh && bash scripts/tests/smoke_check.sh
```
EOF
  txt T_TIPS <<'EOF'
- Use an obviously fake key in the gitleaks test (generated at test time, never committed as a literal that a scanner would flag in the repo).
- import-linter "forbidden" contracts per row are easier to read than one huge layers contract; keep the table order so a reviewer can compare row by row.
- The ESLint boundaries plugin is a new dev dependency: verify its name and version in the registry and justify it in the report (FR-15 requires the rule, not a specific package).
- `make check` must not need the network beyond the package installs; no LLM, ORS or TIMOCOM calls anywhere.
EOF
}
register s_000_3

s_000_4() {
  I_ID="000/4"; I_FEAT="000"; I_TITLE="Scripts: export_openapi.py, trace.py, check_spec_touch.py"
  I_AREA="infra"; I_SIZE="L"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-11"
  I_ACS="07 08 09 13"; I_DEPS="000/1"
  I_GATES="pytest scripts/tests, export_openapi.py --check, trace.py --check"
  I_LOCK="\`contracts/openapi.json\` (first version), \`docs/traceability.md\` (generated)"
  I_BRANCH="chore/FEAT-000-scripts"; I_REQS="NFR-009, REQ-033"; I_ADRS="0009"; I_SCOPE_TAG="scripts"
  txt T_GOAL <<'EOF'
The three guard scripts of the spec-driven workflow: the API contract is exported deterministically and cannot drift, every AC of an approved spec is traced to a test, and contract/migration/prompt/tool changes cannot land without a spec change. The agent-instruction files are checked for consistency.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-000-monorepo-and-ci.md` §4 FR-11, FR-12, FR-13, FR-14, §8 (malformed front matter, LF line endings), §10 (rows 07, 08, 09, 13)
- `specs/README.md` → Traceability rules (what `trace.py --check` fails on), ID scheme
- `context.md` → Specification-Driven Workflow, CI Quality Gates (gates 4 and 10), Pull Request Acceptance Rules 5
- `DEVELOPMENT.md` §4.8 (OpenAPI workflow), §10.4 (agent-instruction files)
EOF
  txt T_SCOPE <<'EOF'
- `scripts/export_openapi.py`: imports the app, writes `contracts/openapi.json` with sorted keys and a trailing newline; byte-identical on repeated runs; `--check` exits non-zero when the committed file differs (FR-11). Commit the first `contracts/openapi.json` (health endpoints only).
- `scripts/trace.py`: parses `specs/FEAT-*.md` front matter (status) and AC IDs, scans `apps/api/tests` for `@pytest.mark.ac("…")` and `apps/web`/`tests/e2e` for `[AC-…]` titles, optionally reads JUnit XML, writes `docs/traceability.md`; `--check` fails on an untested AC of an `approved`/`implemented` spec, on a test naming an unknown AC, and on a failing test of an `implemented` spec; a malformed front matter fails with the file name (FR-12).
- `scripts/check_spec_touch.py`: given a git diff range, fails when files under `contracts/`, `apps/api/migrations/`, `apps/api/src/routepilot/agents/prompts/` or `apps/api/src/routepilot/agents/tools/` changed without any change under `specs/` (FR-13); `--agent-docs` checks `CLAUDE.md` starts with `@AGENTS.md`, `AGENTS.md` has ≤ 150 lines and both mention `context.md`, and every path marked as existing in "Project quick facts" exists (FR-14).
- Register the `ac` pytest marker in `apps/api/pyproject.toml` so unknown markers fail.
- Wire `make openapi` and `make trace` to the scripts.
EOF
  txt T_OUT <<'EOF'
- TypeScript type generation from the contract (005/1) and `oasdiff` in CI (000/5).
- Changing any specification to make the trace pass — untested ACs of approved specs are expected to fail `--check` until their slices land; CI runs `--check` only once tests exist (see tips).
EOF
  txt T_FILES <<'EOF'
- `scripts/export_openapi.py`, `scripts/trace.py`, `scripts/check_spec_touch.py` — new
- `scripts/tests/test_trace.py`, `scripts/tests/test_check_spec_touch.py`, `scripts/tests/fixtures/**` — new
- `apps/api/tests/contract/test_openapi_export.py` — new
- `contracts/openapi.json`, `docs/traceability.md` — generated
- `Makefile` (targets `openapi`, `trace`), `apps/api/pyproject.toml` (marker) — changed
EOF
  txt T_IFACE <<'EOF'
```text
uv run python scripts/export_openapi.py [--out contracts/openapi.json] [--check]
uv run python scripts/trace.py [--check] [--junit PATH ...] [--out docs/traceability.md]
uv run python scripts/check_spec_touch.py [--base REF] [--head REF]
uv run python scripts/check_spec_touch.py --agent-docs
```
Exit code 0 = pass, 1 = check failed (message names the AC, test, file or path), 2 = usage error.
EOF
  txt T_TESTS <<'EOF'
- `tests/contract/test_openapi_export.py` — two runs into a temporary path are byte-identical; `--check` against a modified copy exits non-zero. → AC-07
- `scripts/tests/test_trace.py` — fixture spec `approved` with an untested AC fails and names it; a test naming `AC-FEAT-999-01` fails and names the test; a `draft` spec with untested ACs passes; malformed front matter fails with the file name. → AC-08
- `scripts/tests/test_check_spec_touch.py` — fixture diff touching `contracts/openapi.json` without `specs/` fails; with a `specs/` change passes; `--agent-docs` passes on the real files and fails on fixtures that break each rule. → AC-09, AC-13
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run python ../scripts/export_openapi.py && uv run python ../scripts/export_openapi.py --check
uv run python ../scripts/trace.py && git diff --stat docs/traceability.md
uv run python ../scripts/check_spec_touch.py --agent-docs
uv run pytest ../scripts/tests tests/contract/test_openapi_export.py -q
```
EOF
  txt T_TIPS <<'EOF'
- Today `AGENTS.md` has 138 lines — close to the 150 limit of FR-14; the check must count lines exactly as `wc -l` does.
- `trace.py --check` on the real repository fails while approved specs have untested ACs. In CI (000/5) run it so that it reports but does not block until the owner decides otherwise, **or** ask the owner — do not change the rule silently and do not mark specs `draft` to pass.
- Sorted keys alone do not make FastAPI output stable — also fix the `servers`/version fields and avoid timestamps.
- `.gitattributes` forces LF so the byte-identical check holds on Windows.
EOF
}
register s_000_4

s_000_5() {
  I_ID="000/5"; I_FEAT="000"; I_TITLE="ci-fast workflow with gates 1, 2, 3, 3a, 4, 5, 8a, 8c, 9, 10"
  I_AREA="infra"; I_SIZE="M"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-11"
  I_ACS="10"; I_DEPS="000/3 000/4 O-2"
  I_GATES="the workflow itself green on a PR; actionlint (if available)"
  I_LOCK="🔒 \`.github/workflows/ci-fast.yml\`"; I_APPROVAL="yes"
  I_BRANCH="chore/FEAT-000-ci-fast"; I_REQS="NFR-009, NFR-013"; I_ADRS="0007 0009"; I_SCOPE_TAG="ci"
  txt T_GOAL <<'EOF'
Every pull request runs the blocking fast pipeline (target ≤ 8 minutes) with each gate as a separate, named job or step, so that "No passing CI → No merge" can be enforced from the first feature on.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-000-monorepo-and-ci.md` §4 FR-16, §5 (pipeline speed, pinned actions), §11 OQ-000-01 (Gate 9 wording)
- `context.md` → CI Quality Gates (table and policy), Operations that need human confirmation (workflows)
- `DEVELOPMENT.md` §8 (gate table, merge policy, Gate 9 note)
EOF
  txt T_SCOPE <<'EOF'
- `.github/workflows/ci-fast.yml` on `pull_request`, with named jobs/steps:
  - Gate 1: `ruff format --check`, `ruff check`, Prettier check, ESLint `--max-warnings=0`
  - Gate 2: `mypy --strict`, `tsc --noEmit`
  - Gate 3: pytest (Hypothesis profile `ci`) with coverage report, Vitest
  - Gate 3a: agent tests on fake models (`tests/agents`)
  - Gate 4: OpenAPI drift (`export_openapi.py --check`), TS types drift (once 005/1 adds generation), `oasdiff breaking` against the base branch, schemathesis subset
  - Gate 5: Alembic up/down/up on a fresh SQLite file; repository tests
  - Gate 8a: gitleaks
  - Gate 8c: auth, CSRF and CORS security tests (`tests/security`)
  - Gate 9: `next build`; start `uvicorn` on an empty database, `GET /health`, `GET /ready`, one CORS preflight
  - Gate 10: import-linter, ESLint boundaries, `trace.py --check` (see 000/4 tips), `check_spec_touch.py` on the PR range, `--agent-docs`
- Caching for uv and pnpm; Python 3.13 and Node 22 pinned; every action pinned to a commit SHA; least-privilege `permissions`.
- No secrets and no network calls to LLM, ORS, TIMOCOM or Cloudflare.
EOF
  txt T_OUT <<'EOF'
- `ci-full`, E2E, integration, audits/SAST/licences, `ai-evals` (007/3).
- Branch protection settings on GitHub (owner, in the repository settings).
EOF
  txt T_FILES <<'EOF'
- `.github/workflows/ci-fast.yml` — new (🔒 owner approval)
- `scripts/ci/*.sh` (*suggested*: small helpers such as the Gate 9 smoke) — new
EOF
  txt T_TESTS <<'EOF'
- The workflow runs on this PR; each gate appears as a named job/step; a deliberately failing commit on a scratch branch (for example a formatting error) marks the workflow failed — record the run links in the completion report. → AC-10
- Static check that no step references a secret or an LLM/ORS/TIMOCOM host (a grep in a helper script is enough).
EOF
  txt T_VERIFY <<'EOF'
```bash
gh workflow view ci-fast --repo <owner>/<repo>
gh run list --workflow ci-fast --limit 3
```
Plus the timing of the first green run (target ≤ 8 min — measured, not blocking in FEAT-000).
EOF
  txt T_TIPS <<'EOF'
- Gates whose subject does not exist yet (3a, 5, 8c, TS types drift) must run and pass on empty input (FR-16). Implement that explicitly — for example treat pytest exit code 5 ("no tests collected") as success with a comment naming FR-16 — never by skipping the job.
- `oasdiff` needs the base version of `contracts/openapi.json`: read it with `git show origin/${{ github.base_ref }}:contracts/openapi.json`.
- Pin actions by SHA with the version in a trailing comment so updates stay reviewable.
- The workflow file needs the owner's approval before merge (O-2). Open the PR early so the review can happen in parallel.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-000-01 (accepted): Gate 9 starts `uvicorn` on an empty database file (no Docker image in the MVP).
EOF
}
register s_000_5
