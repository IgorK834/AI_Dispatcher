# FEAT-001 — Domain, SQLite, CRUD, auth. Sourced by scripts/create_github_issues.sh.
# shellcheck shell=bash disable=SC2034

s_001_1() {
  I_ID="001/1"; I_FEAT="001"; I_TITLE="Shared kernel, SQLite engine, type conventions and migration 0001_initial"
  I_AREA="backend"; I_SIZE="L"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-11"
  I_ACS="01 02 03"; I_DEPS="000/1 O-3"
  I_GATES="make check, make test-db"
  I_LOCK="🔒 \`apps/api/migrations/**\` (human review), \`apps/api/uv.lock\`"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-001-db-foundation"; I_REQS="REQ-001, NFR-015"; I_ADRS="0002 0010"; I_SCOPE_TAG="db"
  txt T_GOAL <<'EOF'
The database foundation every module uses: value objects for money, units and ids in `shared`, one SQLite engine with the required PRAGMAs, shared column types that make the unit and time rules impossible to break, and the single reviewed initial migration that creates every MVP table.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-001-domain-sqlite-crud-auth.md` §4 FR-1, FR-2, FR-3, §6.1 (all tables and columns), §11 OQ-001-05 (one initial migration)
- `specs/FEAT-004-routing-and-jobs.md` §6.3 and `specs/FEAT-006-runtime-agents.md` §6.4 — columns of the jobs, plans, assignments, routing-cache and agent tables (they are created here)
- `docs/report.md` §14 (column lists of every table)
- `DEVELOPMENT.md` §5.1 (SQLite settings), §5.2 (type conventions), §5.3 (migrations)
- `context.md` → Data Model, Core Domain Rules 1–2
EOF
  txt T_SCOPE <<'EOF'
- `shared`: `Money` (int minor units + ISO-4217 currency, no float), distance/mass/length helpers (m Decimal 2, km Decimal 2, mm/kg int), id generation (UUID4 as text), `round_half_up` helper for Decimal.
- One SQLAlchemy 2 engine from `DATABASE_URL`; a connect listener sets `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000` on every connection; a short-lived session per request / unit of work (FR-1).
- Shared types and mixins (FR-2): `UuidText`, `UtcDateTime` (rejects naive datetimes with `ValueError`, returns aware UTC), money as integer + currency columns, `JSON` for structures and lists, `version` (starts at 1), `created_at`, `updated_at`.
- Alembic configured with `render_as_batch=True`; migration `0001_initial` creating every table of report §14 plus `app_meta(key TEXT PRIMARY KEY, value JSON, updated_at)`, with the constraints and indexes of FEAT-001 §6.1 and the tables of FEAT-004 §6.3 / FEAT-006 §6.4; `downgrade` drops everything (FR-3).
- `/ready` now compares against the real head (000/1 logic, no change needed if written generically).
- Persist the generated local `SECRET_KEY` in `app_meta` (FEAT-000 §8 edge case).
EOF
  txt T_OUT <<'EOF'
- Repositories, services and endpoints of any resource (001/2 … 001/6). SQLAlchemy models may be added by the slices that use them, but must match `0001_initial` exactly.
- LangGraph checkpoint tables — they live in `agents.db` and are created by `SqliteSaver.setup()` (006/3).
- PostgreSQL (post-MVP, ADR-0002).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/shared/{money.py,units.py,ids.py,rounding.py}` — new (*suggested* names)
- `apps/api/src/routepilot/shared/db/{engine.py,types.py,base.py}` — new (*suggested*)
- `apps/api/migrations/versions/0001_initial.py` — new (🔒 owner review, O-3)
- `apps/api/migrations/env.py`, `apps/api/alembic.ini` — changed
- `apps/api/tests/db/{conftest.py,test_pragmas.py,test_migrations.py,test_types.py}` — new
- `Makefile` target `test-db` — changed
EOF
  txt T_IFACE <<'EOF'
```python
@dataclass(frozen=True)
class Money:                       # shared/money.py
    amount_minor: int              # never float
    currency: str                  # ISO-4217, 3 letters

class UtcDateTime(TypeDecorator[datetime]):   # rejects naive datetimes (ValueError); returns aware UTC
    ...
class UuidText(TypeDecorator[UUID]): ...      # UUID stored as TEXT

def make_engine(database_url: str) -> Engine: ...   # suggested; installs the PRAGMA listener
```
Table and column names: exactly as FEAT-001 §6.1, FEAT-004 §6.3, FEAT-006 §6.4 and report §14 (snake_case). `driver_states` has no `version` (rows are immutable); `freight_stops` has `CHECK (window_start <= window_end)`; `UNIQUE(source, source_offer_id)` on `freight_offers`.
EOF
  txt T_TESTS <<'EOF'
- `tests/db/test_pragmas.py` — a new connection reports `journal_mode = wal`, `foreign_keys = 1`, `busy_timeout = 5000`. → AC-01
- `tests/db/test_migrations.py` — on a fresh temporary SQLite file `upgrade head` → `downgrade base` → `upgrade head` succeed; the final schema contains every table of report §14 plus `app_meta`. → AC-02
- `tests/db/test_types.py` — UUID, aware UTC datetime and 12 345 minor units round-trip unchanged; binding a naive datetime raises `ValueError`. → AC-03
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run alembic upgrade head && uv run alembic downgrade base && uv run alembic upgrade head
uv run pytest tests/db -q
make check && make test-db
```
EOF
  txt T_TIPS <<'EOF'
- SQLite returns naive datetimes; `UtcDateTime` must attach UTC on the way out and reject naive values on the way in.
- Do not use `server_default=func.now()` or other dialect-specific SQL; set timestamps from the injected `Clock` in services.
- Partial uniqueness "one active assignment per driver" is enforced in the service (FEAT-004 §6.3), not by a SQLite-only partial index.
- Write the migration by hand (or autogenerate and then review every line); the owner must be able to compare it table by table (O-3). A PR above ~400 lines is acceptable here with that justification.
- Store `fuel_l` as millilitres and `co2_kg` as grams (`INTEGER`) in plan tables (FEAT-004 §6.3).
EOF
  txt T_DECISIONS <<'EOF'
- OQ-001-05 (accepted): one initial migration with all MVP tables; later features need no schema migration to start.
EOF
}
register s_001_1

s_001_2() {
  I_ID="001/2"; I_FEAT="001"; I_TITLE="identity: Argon2id, sessions, Turnstile, login/logout/me, rate limit, first-start accounts"
  I_AREA="backend"; I_SIZE="L"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-12"
  I_ACS="20 21 22 25 26 28 29 31 33"; I_DEPS="001/1"
  I_GATES="make check, uv run pytest tests/security"
  I_LOCK="\`apps/api/.env.example\`, \`contracts/openapi.json\`, \`apps/api/uv.lock\`"
  I_BRANCH="feat/FEAT-001-identity"; I_REQS="REQ-005, NFR-008"; I_ADRS="0012"; I_SCOPE_TAG="identity"
  txt T_GOAL <<'EOF'
Users can log in with email, password and the Turnstile captcha, get a secure server-side session, log out, and are rate-limited. The `admin` and `demo` accounts exist after the first start, and unsafe production settings stop the startup.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-001-domain-sqlite-crud-auth.md` §4 FR-13, FR-14, FR-15, FR-16, FR-17, §6.2 (Authentication table), §6.3 (`CaptchaVerifier`), §6.6 (configuration), §8 (email normalisation, cookies on HTTP), §10 (test plan rows 20–22, 25–29, 31, 33), §11 OQ-001-02, OQ-001-04
- `context.md` → Security Requirements 1–3, External Integration Contracts (Turnstile keys)
- `DEVELOPMENT.md` §13 (security notes), §4.5 (problem codes)
EOF
  txt T_SCOPE <<'EOF'
- Passwords with Argon2id (argon2-cffi); a password policy (`PASSWORD_MIN_LENGTH`, default 12).
- `CaptchaVerifier` port; `TurnstileVerifier` (httpx POST of secret, token and IP to Cloudflare's verification endpoint); `FakeCaptchaVerifier` for tests.
- Endpoints: `GET /auth/captcha-config`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` (FEAT-001 §6.2).
- Login order (FR-13): rate limit → (`Origin` check added in 001/3) → body validation → Turnstile verification → user lookup + Argon2id verify (a dummy hash when the email is unknown) → session creation → audit row. Wrong password and unknown email give identical responses.
- Sessions (FR-14): 32-byte CSPRNG token in cookie `rp_session` (`HttpOnly; SameSite=Lax; Path=/`, `Secure` on HTTPS); only `SHA-256(token)` stored; expiry after `SESSION_TTL_HOURS` (12); logout deletes the row and clears both cookies; a password change deletes all sessions of the user.
- CSRF token generation at login and in `/auth/me`: `HMAC-SHA256(SECRET_KEY, session_id)` hex, returned as `csrfToken` and cookie `rp_csrf` (verification of state-changing requests comes in 001/3).
- slowapi on login: per IP (`10/minute`) and per normalised email (`5/minute`) → `429 RATE_LIMITED` with `Retry-After` (FR-16).
- First-start accounts in the lifespan (FR-17): create `admin` and `demo` if no user exists; idempotent; outside `local`/`test` the default passwords, the Turnstile test keys or an empty `SECRET_KEY` stop the startup.
- A minimal audit write for login attempts and logout (`audit_events` rows); full audit coverage is verified in 001/7.
- No registration route of any kind (AC-33).
EOF
  txt T_OUT <<'EOF'
- CSRF verification, `Origin` checks, role dependencies, security headers (001/3).
- Account lockout after failed logins (P1 — `failed_logins` and `locked_until` columns exist but stay unused), password reset, `/admin/users` (P1), self-registration (never in the MVP).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/identity/{api,service,domain,repository}/**`, `apps/api/src/routepilot/identity/ports.py` — new
- `apps/api/src/routepilot/shared/audit.py` (*suggested* audit port used by every module) — new
- `apps/api/src/routepilot/main.py` (router, lifespan step, DI of the verifier) — changed
- `apps/api/.env.example` (auth variables, if not complete yet) — changed
- `apps/api/tests/security/{test_auth.py,test_first_start.py}`, `apps/api/tests/unit/identity/{test_sessions.py,test_passwords.py}` — new
- `contracts/openapi.json` — regenerated
EOF
  txt T_IFACE <<'EOF'
```text
GET  /api/v1/auth/captcha-config -> 200 {provider: "turnstile", siteKey}
POST /api/v1/auth/login  {email, password, captchaToken}
     -> 200 {user: {id, email, role, locale}, csrfToken} + Set-Cookie rp_session, rp_csrf
     -> 400 CAPTCHA_FAILED | 401 INVALID_CREDENTIALS | 403 ORIGIN_NOT_ALLOWED (001/3) | 429 RATE_LIMITED
POST /api/v1/auth/logout -> 204, both cookies cleared
GET  /api/v1/auth/me     -> 200 {user, csrfToken} | 401 UNAUTHENTICATED
```

```python
class CaptchaVerifier(Protocol):                 # identity/ports.py
    def verify(self, token: str, remote_ip: str | None) -> CaptchaResult: ...
@dataclass(frozen=True)
class CaptchaResult:
    ok: bool
    error_codes: list[str]
```
Configuration: `SECRET_KEY`, `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `DEMO_EMAIL`, `DEMO_PASSWORD`, `SESSION_TTL_HOURS` (12), `LOGIN_RATE_LIMIT_PER_IP` (`10/minute`), `LOGIN_RATE_LIMIT_PER_ACCOUNT` (`5/minute`), `PASSWORD_MIN_LENGTH` (12).
EOF
  txt T_TESTS <<'EOF'
- `tests/security/test_auth.py` — login with the "always pass" keys (stubbed HTTP transport) returns user + `csrfToken`, cookies with the right flags, `/auth/me` 200 → AC-20; wrong password and unknown email give identical `401` bodies apart from `requestId`, no cookie → AC-21; the "always fail" `2x…` secret gives `400 CAPTCHA_FAILED` and the verifier ran before the user lookup (spy) → AC-22; logout clears cookies and the session row, the old cookie gets `401` → AC-25; six attempts in a minute → `429` with `Retry-After` → AC-28; routes and OpenAPI contain no registration path, `POST /auth/register` → `404` → AC-33.
- `tests/unit/identity/test_sessions.py` — `FixedClock` at T + 12 h + 1 s rejects and deletes the session. → AC-26
- `tests/unit/identity/test_passwords.py` — `password_hash` starts with `$argon2id$`; `token_hash` is SHA-256 of the cookie value; the raw token is stored nowhere. → AC-31
- `tests/security/test_first_start.py` — two starts on an empty DB leave exactly one `admin` and one `demo`; `APP_ENV=production` with defaults or test keys fails. → AC-29
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/security tests/unit/identity -q
make check && make openapi
cp .env.example .env && uv run uvicorn routepilot.main:app --port 8000
# open http://localhost:8000/docs and log in with the demo account (Turnstile test key passes automatically)
```
EOF
  txt T_TIPS <<'EOF'
- No test calls Cloudflare: stub the verifier's HTTP transport to return the documented answers for the `1x…` and `2x…` test keys.
- Normalise the email (trim, lower-case) before the lookup **and** before building the per-account rate-limit key.
- Verify a dummy Argon2id hash for unknown emails so timing does not reveal account existence.
- Never put the password, token, hash or captcha token into a log line or an audit `diff`.
- `Secure` is set only when the request scheme is HTTPS; on plain `http://localhost` the cookie must still work.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-001-02 (accepted): session 12 h; 10/min per IP and 5/min per account; 12 characters minimum — all configurable.
- OQ-001-04 (accepted): fixed local demo passwords in `.env.example`, rejected outside `local`/`test`.
EOF
}
register s_001_2

s_001_3() {
  I_ID="001/3"; I_FEAT="001"; I_TITLE="CSRF token, Origin check, role dependencies and security headers"
  I_AREA="backend"; I_SIZE="M"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-12"
  I_ACS="23 24 34"; I_DEPS="001/2"
  I_GATES="make check, uv run pytest tests/security"
  I_LOCK="—"
  I_BRANCH="feat/FEAT-001-csrf-roles"; I_REQS="REQ-005, NFR-008"; I_ADRS="0009 0012"; I_SCOPE_TAG="identity"
  txt T_GOAL <<'EOF'
Every state-changing request is protected by the `Origin` allowlist and a per-session CSRF token, every endpoint can declare its minimum role through FastAPI dependencies, and every response carries the security headers.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-001-domain-sqlite-crud-auth.md` §4 FR-12, FR-15, FR-19, §6.5 (permission matrix and how to read the "Auth" columns)
- `DEVELOPMENT.md` §4.9 (CORS and CSRF explained), §13
- `context.md` → Security Requirements 4, 5, 7
EOF
  txt T_SCOPE <<'EOF'
- For `POST`, `PATCH`, `PUT`, `DELETE`: the `Origin` header must be in `CORS_ALLOWED_ORIGINS` (missing or other → `403 ORIGIN_NOT_ALLOWED`), and `X-CSRF-Token` must equal the `rp_csrf` cookie and be valid for the session, i.e. `HMAC-SHA256(SECRET_KEY, session_id)` (otherwise `403 CSRF_FAILED`). `POST /auth/login` gets only the `Origin` check (plus the captcha), inserted at its place in the FR-13 order.
- Dependencies `require_user` and `require_role(*roles)` and the role reading of §6.5: "demo" = any logged-in role, "dispatcher" = dispatcher + demo + admin, "admin" = admin only.
- Security-headers middleware (FR-19): `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` (relaxed only for `/docs`).
EOF
  txt T_OUT <<'EOF'
- The permission-matrix test over every CRUD endpoint (AC-27) — it lands in 001/7, once all endpoints exist.
- CORS preflight details (AC-17, 18, 19 in 001/7).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/identity/api/dependencies.py` (*suggested*), `apps/api/src/routepilot/identity/service/csrf.py` (*suggested*) — new
- `apps/api/src/routepilot/shared/middleware/{csrf.py,security_headers.py}` (*suggested*) — new
- `apps/api/src/routepilot/main.py` — changed (middleware order)
- `apps/api/tests/security/{test_csrf.py,test_headers.py}` — new
EOF
  txt T_IFACE <<'EOF'
```python
def require_user() -> CurrentUser: ...                       # 401 UNAUTHENTICATED without a valid session
def require_role(*roles: Role) -> Callable[..., CurrentUser]: ...   # 403 FORBIDDEN otherwise
```
Problem codes: `CSRF_FAILED` (403), `ORIGIN_NOT_ALLOWED` (403), `FORBIDDEN` (403), `UNAUTHENTICATED` (401).
EOF
  txt T_TESTS <<'EOF'
- `tests/security/test_csrf.py` — with a valid session, `POST`/`PATCH`/`DELETE` without the header, with a wrong token or with another session's token → `403 CSRF_FAILED` and nothing changes; the right token succeeds → AC-23. A state-changing request with an `Origin` outside the allowlist or without `Origin` → `403 ORIGIN_NOT_ALLOWED` → AC-24. Use `POST /auth/logout` plus a small router registered only in the test app for `PATCH`/`DELETE`.
- `tests/security/test_headers.py` — every JSON response carries the three headers. → AC-34
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/security -q && make check
curl -i -X POST http://localhost:8000/api/v1/auth/logout -H 'Origin: http://evil.example'   # expect 403 ORIGIN_NOT_ALLOWED
```
EOF
  txt T_TIPS <<'EOF'
- Compare tokens with `hmac.compare_digest`.
- Middleware order matters: CORS must still answer preflights (`OPTIONS`) without CSRF checks; the `Origin` check applies to state-changing methods only.
- The test-only router lives under `tests/` and is mounted only by the test app factory — never in `main.py`.
EOF
}
register s_001_3

s_001_4() {
  I_ID="001/4"; I_FEAT="001"; I_TITLE="Drivers CRUD and driver state"
  I_AREA="backend"; I_SIZE="L"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-12"
  I_ACS="04 05 06 07 08 09 15"; I_DEPS="001/3"
  I_GATES="make check, uv run pytest tests/api, make openapi"
  I_LOCK="\`contracts/openapi.json\`"
  I_BRANCH="feat/FEAT-001-drivers-crud"; I_REQS="REQ-006, REQ-008, NFR-015"; I_ADRS="0009 0010"; I_SCOPE_TAG="fleet"
  txt T_GOAL <<'EOF'
Full REST CRUD for drivers with cursor pagination, filters, optimistic concurrency and the delete rules, plus the append-only driver-state history whose newest row is embedded in the driver.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-001-domain-sqlite-crud-auth.md` §4 FR-4, FR-5, FR-6 (driver rules), FR-9, §6.1 (`drivers`, `driver_states`, value ranges), §6.2 (Drivers table and schemas), §6.3 (`DriverUsageChecker`), §8 (edge cases)
- `DEVELOPMENT.md` §4.1–4.4 (naming, methods, CRUD conventions, pagination and filtering), §4.5 (problem codes), §14 (how to add a CRUD resource — the same steps)
- `context.md` → Core Domain Rules 1–3, External Integration Contracts (REST)
EOF
  txt T_SCOPE <<'EOF'
- `GET/POST /drivers`, `GET/PATCH/DELETE /drivers/{id}`, `GET/POST /drivers/{id}/state` with the schemas `DriverCreate`, `DriverUpdate`, `Driver`, `DriverStateCreate`, `DriverState` of §6.2 (camelCase JSON, `extra="forbid"`).
- Cursor pagination with `limit` and opaque `nextCursor`; filters `homeCity`, `availableBefore`, `hasVehicle`; a cursor from another filter set or a tampered cursor → `422`.
- `PATCH` with `version`: mismatch → `409 VERSION_CONFLICT`; success → `version + 1` (also for a body with only `version`).
- Assigning a vehicle already used by another driver → `409 DUPLICATE_RESOURCE`; unknown `vehicleId` → `404`.
- Delete through the `DriverUsageChecker` port: `"active"` → `409 DRIVER_HAS_ACTIVE_ASSIGNMENT`; `"historical"` → soft delete (`deleted_at`, hidden from lists, a second delete → `404`); `"none"` → hard delete. `main.py` injects a checker that always answers `"none"` until 004/5.
- Driver state: every `POST` inserts a new immutable row (`source = "user"`, `valid_from` from the `Clock`); list newest first; the driver embeds `vehicle` and the newest `state`; negative counters → `422`.
- Audit rows for create, update and delete through the audit port.
EOF
  txt T_OUT <<'EOF'
- Vehicles and cost profiles (001/5), offers (001/6); the real `DriverUsageChecker` (004/5).
- Working-time remaining bars (computed in FEAT-005 from API data) and any rules logic (FEAT-003).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/fleet/{api,service,domain,repository}/**` (drivers, driver states), `apps/api/src/routepilot/fleet/ports.py` — new
- `apps/api/src/routepilot/shared/pagination.py` (*suggested* cursor helper) — new
- `apps/api/src/routepilot/main.py` (router, stub checker) — changed
- `apps/api/tests/api/{test_drivers.py,test_driver_state.py}`, `apps/api/tests/factories.py` — new
- `contracts/openapi.json` — regenerated
EOF
  txt T_IFACE <<'EOF'
```text
DriverCreate  { name (1–120), phone?, homeCity, homeCountry (ISO 3166-1 alpha-2), homeLat, homeLon,
                defaultRulesProfile? ("pl_domestic_employee_v1" default | "eu561_van_international_v1"), vehicleId? }
DriverUpdate  { version, ...any DriverCreate field }
Driver        { id, name, phone, homeCity, homeCountry, homeLat, homeLon, defaultRulesProfile, vehicleId,
                isSynthetic, version, createdAt, updatedAt, vehicle?: Vehicle, state?: DriverState }
DriverStateCreate { currentCity?, currentLat, currentLon, availableFrom, workTodayMin, driveTodayMin,
                workSinceBreakMin, driveSinceBreakMin, workWeekMin, driveWeekMin, drivePrevWeekMin,
                lastDailyRestEnd?, lastWeeklyRestEnd?, homeBy? }
DriverState   { id, driverId, validFrom, source, ...DriverStateCreate fields }
```

```python
class DriverUsageChecker(Protocol):              # fleet/ports.py
    def assignment_usage(self, driver_id: UUID) -> Literal["none", "historical", "active"]: ...
```
Minimum role: read = any logged-in role; write = `dispatcher` (dispatcher, demo, admin — OQ-001-01 decision).
EOF
  txt T_TESTS <<'EOF'
- `tests/api/test_drivers.py` — `201` + `Location` + `version = 1` → AC-04; 7 drivers paged 3/3/1 without duplicates, last cursor `null`, `homeCity=Katowice` filter → AC-05; `GET` embeds vehicle and newest state, unknown id `404 NOT_FOUND` → AC-06; `PATCH` bumps version, a stale second `PATCH` gives `409 VERSION_CONFLICT` and changes nothing → AC-07; delete with fake checker answers `none` / `historical` / `active` → AC-08; `homeLat = 123` plus an unknown field → `422` problem+json `VALIDATION_ERROR` naming both fields → AC-09.
- `tests/api/test_driver_state.py` — two `POST`s → both `201`, list newest first with `source = "user"`, driver embeds the second; negative counter → `422`. → AC-15
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/api/test_drivers.py tests/api/test_driver_state.py -q
make check && make openapi && git diff --stat contracts/openapi.json
```
EOF
  txt T_TIPS <<'EOF'
- Two concurrent `PATCH`es with the same version must give exactly one `200` and one `409`: do the version check in the `UPDATE … WHERE id = ? AND version = ?` statement, not in Python before it.
- Coordinates are `REAL`; lat −90…90, lon −180…180 (§6.1 ranges).
- Soft-deleted drivers never appear in lists or in `GET` (they give `404`).
- Keep the cursor opaque (for example base64 of the sort key plus a hash of the filters) so that a tampered cursor is detected.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-001-01 (owner, 2026-11-11): drivers and vehicles may be created, edited and deleted by `admin`, `dispatcher` and `demo`; cost profiles stay `admin` only.
EOF
}
register s_001_4

s_001_5() {
  I_ID="001/5"; I_FEAT="001"; I_TITLE="Vehicles CRUD and cost-profiles CRUD"
  I_AREA="backend"; I_SIZE="M"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-12"
  I_ACS="10 11"; I_DEPS="001/4"
  I_GATES="make check, uv run pytest tests/api, make openapi"
  I_LOCK="\`contracts/openapi.json\`"
  I_BRANCH="feat/FEAT-001-vehicles-cost-profiles"; I_REQS="REQ-006, NFR-015"; I_ADRS="0010 0014"; I_SCOPE_TAG="fleet"
  txt T_GOAL <<'EOF'
Full REST CRUD for vehicles (vans up to 3.5 t with pallet places, payload, interior and fuel parameters) and for cost profiles (money in integer minor units, assumption provenance), with uniqueness, range and delete-conflict rules.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-001-domain-sqlite-crud-auth.md` §4 FR-4–FR-6 (vehicle and cost-profile rules), §6.1 (`vehicles`, `cost_profiles`, value ranges), §6.2 (Vehicles and Cost profiles tables and schemas), §6.5
- `docs/adr/ADR-0014-van-capacity.md` (pallet places, layout templates), `docs/adr/ADR-0010-units-and-money.md`
- `docs/report.md` §17.4 (cost parameters and which are assumptions)
EOF
  txt T_SCOPE <<'EOF'
- `GET/POST /vehicles`, `GET/PATCH/DELETE /vehicles/{id}` with `VehicleCreate`/`Vehicle` of §6.2; filters `palletPlaces`, `unassigned`; unique `label` → `409 DUPLICATE_RESOURCE`; unknown `costProfileId` → `404`; delete while a driver references the vehicle → `409 VEHICLE_ASSIGNED_TO_DRIVER`.
- Ranges (§6.1): `payloadKg` 100–2 000, `gvwKg` ≤ 3 500, `palletPlaces` 1–12; interior dimensions as decimal metres (2 places) in the API and millimetres in the DB; fuel in tenths of a litre in the DB; `fuel.provenance` server-set.
- `GET/POST /cost-profiles`, `GET/PATCH/DELETE /cost-profiles/{id}` (write = `admin` only) with `CostProfileCreate`/`CostProfile`; unique `name`; delete while a vehicle references it → `409 COST_PROFILE_IN_USE`; money fields accept integers only (a decimal → `422`); `provenance` per field.
- Version conflicts, `Location` headers, audit rows as in 001/4.
EOF
  txt T_OUT <<'EOF'
- The `DEMO-DEFAULT` profile values and the seed (002/5); cost formulas (003/2).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/fleet/{api,service,domain,repository}/**` (vehicles, cost profiles) — new or changed
- `apps/api/tests/api/{test_vehicles.py,test_cost_profiles.py}` — new
- `contracts/openapi.json` — regenerated
EOF
  txt T_IFACE <<'EOF'
```text
VehicleCreate { label, vehicleType ("VEHICLE_UP_TO_3_5_T"), bodyType ("CURTAIN_SIDER"|"TAUTLINER"|"BOX"),
                innerLengthM?, innerWidthM?, innerHeightM? (decimal, 2 places), palletPlaces,
                layoutTemplate ("EUR_MIXED_5X3"|"EUR_MIXED_6X4"|"DECLARED_ONLY"), sideAccess ("LEFT"|"RIGHT"|"BOTH"|"NONE"),
                payloadKg, gvwKg, sleeperCab,
                fuel { lPer100kmEmptyAt90, lPer100kmFullAt90, speedCurve ("VAN_DEFAULT_V1") }, costProfileId }
Vehicle       { id, ...VehicleCreate fields, fuel.provenance, isSynthetic, version, createdAt, updatedAt }
CostProfileCreate { name, currency ("EUR"), fuelPriceMinorPerL, driverCostMinorPerHour, vehicleCostMinorPerKm,
                    accommodationMinor, perDiem {<country>: minorPerDay}, tolls {perKm: {<country>: minorPerKm}, annualVignettes: [<country>]},
                    fxRates {<currency>: "<decimal>"}, minProfitMinor, minMarginPct ("<decimal>") }
CostProfile       { id, ...fields, provenance {<field>: "source"|"assumption"|"user"}, isSynthetic, version, createdAt, updatedAt }
```
EOF
  txt T_TESTS <<'EOF'
- `tests/api/test_vehicles.py` — create `201` + `Location`, read `200`, update `200` with version bump, delete `204`; duplicate label `409 DUPLICATE_RESOURCE`; `gvwKg = 3600` → `422`; delete of a referenced vehicle `409 VEHICLE_ASSIGNED_TO_DRIVER`; unknown id `404`. → AC-10
- `tests/api/test_cost_profiles.py` — create/read/update/delete; stale version `409 VERSION_CONFLICT`; referenced profile `409 COST_PROFILE_IN_USE`; decimal money value → `422`. → AC-11
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/api/test_vehicles.py tests/api/test_cost_profiles.py -q
make check && make openapi
```
EOF
  txt T_TIPS <<'EOF'
- Use strict integer types for money in Pydantic so `12.5` and `"12"` are rejected instead of coerced.
- `minMarginPct` and `fxRates` values are decimal **strings** — never floats.
- Conversion m → mm uses `Decimal` and half-up rounding; test 4.85 m → 4 850 mm.
EOF
}
register s_001_5

s_001_6() {
  I_ID="001/6"; I_FEAT="001"; I_TITLE="Freight offers: manual CRUD, read-only provider offers, filters with completeness and provenance"
  I_AREA="backend data"; I_SIZE="L"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-12"
  I_ACS="12 13 14"; I_DEPS="001/3"
  I_GATES="make check, uv run pytest tests/api, make openapi"
  I_LOCK="\`contracts/openapi.json\`"
  I_BRANCH="feat/FEAT-001-freight-offers"; I_REQS="REQ-001, REQ-006, REQ-007"; I_ADRS="0003 0009 0014"; I_SCOPE_TAG="freight"
  txt T_GOAL <<'EOF'
Dispatchers can add, edit and delete their own manual offers through the API, imported provider offers are read-only, and the offer list can be filtered and shows completeness, missing fields, quality flags and per-field provenance.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-001-domain-sqlite-crud-auth.md` §4 FR-6 (offer delete rule), FR-7, FR-8, §6.1 (`freight_offers`, `freight_stops`, ranges), §6.2 (Freight offers table and schemas), §8 (edge cases), §11 OQ-001-06
- `specs/FEAT-002-demo-data-generators.md` §4.1 FR-1, FR-2 (cities lookup and country → time-zone map) — read only
- `context.md` → Core Domain Rules 3–5, Glossary (Provenance)
EOF
  txt T_SCOPE <<'EOF'
- `GET/POST /freight-offers`, `GET/PATCH/DELETE /freight-offers/{id}` with `FreightOfferCreate`, `Stop`, `FreightOffer` of §6.2.
- Create (FR-7): `source = "manual"`, `isSynthetic = false`, `sourceOfferId = MAN-<uuid8>`, `status = open`, user fields with provenance `user`; exactly two stops (first `LOADING`, last `UNLOADING`); missing coordinates geocoded from `data/mock/cities.json` by `(city, countryCode)` with provenance `derived`, else `MISSING_COORDINATES`; stop time zone inferred from the country (`inferred`). Server-set fields in a body → `422`.
- `completenessScore` and `missingFields` (FR-8): share of present values among revenue, weight, pallet count, both coordinate pairs, both windows.
- Provider offers (`source != manual`): `PATCH`/`DELETE` → `409 PROVIDER_OFFER_READ_ONLY`, unchanged. Manual offer in an active assignment → soft delete (status `withdrawn`).
- Filters: `source`, `status`, `originCountry`, `destinationCountry`, `originCity`, `destinationCity`, `pickupFrom`, `pickupTo`, `maxWeightKg`, `maxPallets`, `minCompleteness`, `hasPrice`; an unknown query parameter → `422`.
- Until 002/1 lands, the geocoder reads a three-city test fixture; the real file path is configuration.
EOF
  txt T_OUT <<'EOF'
- Import of provider offers and the TIMOCOM mapper (002/3, 002/4); AI enrichment (FEAT-008, P1); multi-stop offers (P2).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/freight/{api,service,domain,repository}/**` — new
- `apps/api/src/routepilot/freight/geocoding.py` (*suggested*, reads `cities.json`) — new
- `apps/api/tests/api/test_freight_offers.py`, `apps/api/tests/fixtures/cities_small.json` — new
- `contracts/openapi.json` — regenerated
EOF
  txt T_IFACE <<'EOF'
```text
FreightOfferCreate { description (3–50), revenue? {amountMinor, currency}, weightKg, palletCount?, palletType
                     ("EUR_1200x800"|"IND_1200x1000"|"HALF_800x600"|"UNKNOWN"), loadingLengthM?, requiredBodyTypes[],
                     publicRemark? (≤ 500), stops[2] }
Stop               { stopType ("LOADING"|"UNLOADING"), city, postalCode?, countryCode, lat?, lon?,
                     windowStart, windowEnd, serviceMinutes? }
FreightOffer       { id, source, sourceOfferId, status, isSynthetic, description, revenue?, weightKg, palletCount?, palletType,
                     loadingLengthM?, requiredBodyTypes[], requiredVehicleTypes[], publicRemark?, completenessScore,
                     missingFields[], qualityFlags[], fieldProvenance {<field>: <provenance>}, stops[] (+ sequence, timezone, provenance),
                     version, createdAt, updatedAt }
```
EOF
  txt T_TESTS <<'EOF'
- `tests/api/test_freight_offers.py` — dispatcher creates a manual offer: `201` + `Location`, `source = manual`, `isSynthetic = false`, `status = open`, `MAN-` id, provenance `user`; a body with `source` → `422` → AC-12; a `mock_timocom_v3` offer cannot be patched or deleted (`409 PROVIDER_OFFER_READ_ONLY`), a manual one can → AC-13; filters on two sources return only matches with completeness, missing fields, flags and provenance; an unknown query parameter → `422` → AC-14.
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/api/test_freight_offers.py -q
make check && make openapi
```
EOF
  txt T_TIPS <<'EOF'
- FastAPI ignores unknown query parameters by default; AC-14 needs an explicit check against the declared ones.
- Offer free text (`description`, `publicRemark`) is untrusted: store it unchanged, never interpret it.
- City matching is exact on `(name, countryCode)` after case folding and trimming; an exonym is not matched (FEAT-002 §8).
- A manual offer without a price is stored (`missingFields` contains `revenue`); the engine rejects it later with `MISSING_REVENUE`.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-001-06 (accepted): a manual offer has `is_synthetic = false`, shown with `source = manual` in the UI; the "SYNTHETIC DATA" badge applies to generated data.
EOF
}
register s_001_6

s_001_7() {
  I_ID="001/7"; I_FEAT="001"; I_TITLE="Cross-cutting API checks: problem+json, CORS, permission matrix, audit, OpenAPI + schemathesis"
  I_AREA="backend"; I_SIZE="M"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-12"
  I_ACS="16 17 18 19 27 30 32"; I_DEPS="001/4 001/5 001/6"
  I_GATES="make check, uv run pytest tests/security tests/contract, make test-db, make openapi"
  I_LOCK="\`contracts/openapi.json\`, \`apps/api/uv.lock\` (schemathesis)"
  I_BRANCH="test/FEAT-001-cross-cutting"; I_REQS="NFR-008, NFR-009, NFR-011, NFR-015"; I_ADRS="0009 0012"; I_SCOPE_TAG="api"
  txt T_GOAL <<'EOF'
Prove, across the whole FEAT-001 API, that errors share one problem+json shape with a traceable `requestId`, CORS behaves exactly as configured, every role gets exactly the permissions of the matrix, every change leaves an audit row without secrets, and the committed contract matches the implementation.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-001-domain-sqlite-crud-auth.md` §4 FR-10, FR-11, FR-18, §5 (NFR measures), §6.2 (every endpoint and status code), §6.4 (problem codes), §6.5 (permission matrix), §10 (test plan rows 16–19, 27, 30, 32)
- `DEVELOPMENT.md` §4.5 (problem shape), §4.8 (OpenAPI workflow), §4.9 (CORS)
- `context.md` → Testing Standards (Security, API / CRUD rows)
EOF
  txt T_SCOPE <<'EOF'
- Close any gap the tests reveal in the shared error handler, CORS configuration, role dependencies and audit writes of 001/2 … 001/6 (inside the FEAT-001 modules only).
- Settings: `CORS_ALLOWED_ORIGINS` containing `*` stops the startup (if not already enforced by 000/1, add the test here).
- Audit (FR-18): every login attempt, logout and every create/update/delete of §6.2 writes `at`, `actor`, `action`, `entity_type`, `entity_id`, `diff` (changed field names and non-secret values).
- `contracts/openapi.json` contains every path, method and status code of §6.2; a schemathesis run over the CRUD endpoints with an authenticated session passes (subset suitable for `ci-fast`).
EOF
  txt T_OUT <<'EOF'
- New endpoints or features; endpoints of later features join the permission-matrix test in their own slices (FEAT-002 admin, FEAT-004, FEAT-006).
EOF
  txt T_FILES <<'EOF'
- `apps/api/tests/contract/{test_problem_json.py,test_schemathesis_crud.py}` — new
- `apps/api/tests/security/{test_cors.py,test_roles.py}` — new
- `apps/api/tests/db/test_audit.py` — new
- `apps/api/src/routepilot/{shared,identity,fleet,freight}/**` — changed only where a test exposes a defect
- `contracts/openapi.json` — regenerated
EOF
  txt T_TESTS <<'EOF'
- `tests/contract/test_problem_json.py` — `401`, `403`, `404`, `409`, `422`, `429`, `500` all have `application/problem+json` with `type`, `title`, `status`, `code`, `requestId`; `requestId` equals the log line's `request_id`; with `APP_ENV=demo` a forced `500` has no stack trace. → AC-16
- `tests/security/test_cors.py` — allowed preflight with method `POST` and headers `content-type,x-csrf-token,idempotency-key` → AC-17; `http://evil.example` gets no `Access-Control-Allow-Origin`; no response ever has `*` → AC-18; `*` in settings fails startup → AC-19.
- `tests/security/test_roles.py` — table-driven over every endpoint of §6.2 × `admin`/`dispatcher`/`demo`/anonymous, expectations from §6.5. → AC-27
- `tests/db/test_audit.py` — successful login, failed login, create/update/delete of a driver → five rows with the right fields and no password, token or hash. → AC-30
- `tests/contract/test_schemathesis_crud.py` — regenerated contract lists every path/method/status of §6.2; schemathesis over CRUD with a session reports no violation. → AC-32
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/contract tests/security tests/db/test_audit.py -q
make check && make test-db && make openapi && uv run python ../scripts/export_openapi.py --check
```
EOF
  txt T_TIPS <<'EOF'
- Build the permission table from the router list so a new endpoint without an expectation makes the test fail (instead of being silently untested).
- For the `500` test register a failing route only in the test app.
- schemathesis needs a valid session cookie and the CSRF header for state-changing calls — provide them through hooks; keep the `ci-fast` subset small (target ≤ 8 min for the whole workflow).
- Verify the schemathesis version in the registry and record it.
EOF
}
register s_001_7
