---
id: FEAT-001
title: Domain model, SQLite, CRUD API, CORS/CSRF and authentication
status: approved
owner: project owner
requirements: [REQ-001, REQ-005, REQ-006, REQ-007, REQ-008, REQ-032, NFR-008, NFR-009, NFR-011, NFR-015]
adrs: [ADR-0001, ADR-0002, ADR-0009, ADR-0010, ADR-0012]
modules: [shared, identity, fleet, freight, main.py, apps/api/migrations]
revision: 4
---

# FEAT-001: Domain model, SQLite, CRUD API, CORS/CSRF and authentication

Priority: **P0**. Slice 001/1 (shared types and the initial schema) is available for review. CRUD and authentication remain planned; status remains `approved`.

## 1. Goal

A working REST API on SQLite with full CRUD for drivers, vehicles, cost profiles and manual freight offers, a login with captcha and roles, explicit CORS with CSRF protection, and an audit trail — everything the frontend and the later features build on.

## 2. Business context

The dispatcher must be able to maintain the fleet and add offers by hand (REQ-006, REQ-008). A clean, predictable REST API with correct status codes and CORS is one of the project's delivery standards ([`DEVELOPMENT.md`](../DEVELOPMENT.md) §1, rows 2, 4, 7c). The API design rules are in `DEVELOPMENT.md` §4; this specification is their binding contract.

## 3. Scope / Out of scope

**In scope:** SQLite engine setup and type conventions; the initial Alembic migration; CRUD endpoints for `drivers`, `drivers/{id}/state`, `vehicles`, `cost-profiles`, `freight-offers`; problem+json errors; pagination and filters; CORS, CSRF token and `Origin` check; `identity` (Argon2id, server-side sessions, Turnstile, roles, rate limit); first-start accounts; audit events.

**Out of scope:** demo data generators and seed content (FEAT-002); optimisation jobs, plans, assignments (FEAT-004); agent endpoints (FEAT-006); user administration endpoints `/admin/users` and account lockout (P1); password reset; self-registration (not in the MVP at all).

## 4. Functional requirements

- **FR-1 Engine.** One SQLAlchemy engine for `DATABASE_URL`. A connect listener sets `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000` on every connection. Sessions are short-lived (one per request / unit of work).
- **FR-2 Types.** Shared column types and mixins implement `DEVELOPMENT.md` §5.2: `UuidText`, `UtcDateTime` (rejects naive datetimes), money as integer + currency, `JSON` for lists and structures, `version` (integer, starts at 1), `created_at`, `updated_at`.
- **FR-3 Migration.** `0001_initial` creates all MVP tables listed in [`docs/report.md`](../docs/report.md) §14 plus `app_meta(key TEXT PRIMARY KEY, value JSON, updated_at)`. Tables owned by later features (jobs, plans, assignments, agents, routing cache) are created here so that later features do not need a schema migration to start; their column details are fixed in FEAT-004 §6 and FEAT-006 §6 and must be final before this migration is written. `downgrade` drops everything.
- **FR-4 CRUD.** The endpoints of §6.2 with the semantics of `DEVELOPMENT.md` §4.2–4.4.
- **FR-5 Optimistic concurrency.** `PATCH` bodies carry `version`. On mismatch → `409 VERSION_CONFLICT`. On success `version` increases by 1.
- **FR-6 Delete rules.**
  - Driver: `409 DRIVER_HAS_ACTIVE_ASSIGNMENT` if an active assignment exists; soft delete (`deleted_at` set, hidden from lists) if only historical assignments exist; hard delete otherwise. The check goes through the port `DriverUsageChecker` (§6.3).
  - Vehicle: `409 VEHICLE_ASSIGNED_TO_DRIVER` while a driver references it.
  - Cost profile: `409 COST_PROFILE_IN_USE` while a vehicle references it.
  - Freight offer: only `source = manual`; otherwise `409 PROVIDER_OFFER_READ_ONLY`. A manual offer that is part of an active assignment → `409 PLAN_NOT_ASSIGNABLE` is **not** used here; the offer is soft-deleted (status `withdrawn`).
- **FR-7 Manual offers.** `POST /freight-offers` always creates `source = "manual"`, `is_synthetic = false`, a generated `source_offer_id` (`MAN-<uuid8>`), status `open`, all user-entered fields with provenance `user`. Exactly two stops in the MVP: first `LOADING`, last `UNLOADING`. Missing coordinates are geocoded from `data/mock/cities.json` by `(city, countryCode)` (provenance `derived`); if that fails the offer is still stored, with `missing_fields` and the quality flag `MISSING_COORDINATES`. The stop time zone is inferred from the country (provenance `inferred`).
- **FR-8 Completeness.** `completeness_score` (0–1) = share of present values among: revenue, weight, pallet count, both coordinates pairs, both windows. `missing_fields` lists the absent ones.
- **FR-9 Driver state.** `POST /drivers/{id}/state` inserts a new row (`source = "user"`, `valid_from = now`); earlier rows are kept. `GET /drivers/{id}` embeds the latest state.
- **FR-10 Errors.** All errors are problem+json with a `code` from §6.4 and a `requestId`. No stack traces unless `APP_ENV=local`.
- **FR-11 CORS.** As in `DEVELOPMENT.md` §4.9. Startup fails if the allowlist contains `*`.
- **FR-12 CSRF.** For `POST`, `PATCH`, `PUT`, `DELETE` (except `POST /auth/login`): the `Origin` header must be in the allowlist (`403 ORIGIN_NOT_ALLOWED`), and `X-CSRF-Token` must equal the `rp_csrf` cookie and be valid for the session (`403 CSRF_FAILED`). The token is `HMAC-SHA256(SECRET_KEY, session_id)`, hex encoded. `POST /auth/login` is protected by the `Origin` check and the captcha.
- **FR-13 Login.** Order of checks: rate limit → `Origin` → body validation → Turnstile verification (server side, through `CaptchaVerifier`) → user lookup and Argon2id verification (a dummy hash is verified when the email is unknown, so timing does not reveal existence) → session creation → audit. Wrong password and unknown email give the same response.
- **FR-14 Sessions.** A random token of 32 bytes (256 bits) from a CSPRNG, sent as cookie `rp_session` (`HttpOnly; SameSite=Lax; Path=/`; `Secure` when the request scheme is HTTPS). The database stores only `SHA-256(token)`. Sessions expire after `SESSION_TTL_HOURS`. Logout deletes the session and clears both cookies. A password change deletes all sessions of the user.
- **FR-15 Roles.** FastAPI dependencies `require_user`, `require_role(...)`. Permission matrix in §6.5.
- **FR-16 Rate limit.** slowapi on `POST /auth/login`: per client IP and per normalised email. Exceeding → `429 RATE_LIMITED` with `Retry-After`.
- **FR-17 First-start accounts.** On start, if no user exists, create `admin` (`ADMIN_EMAIL`/`ADMIN_PASSWORD`) and `demo` (`DEMO_EMAIL`/`DEMO_PASSWORD`, role `demo`). Idempotent. With `APP_ENV` other than `local`/`test`, default passwords from `.env.example`, Turnstile test keys or an empty `SECRET_KEY` stop the startup.
- **FR-18 Audit.** Every login attempt, logout, and every create/update/delete of §6.2 writes an `audit_events` row (`at`, `actor` = user id or `"anonymous"`, `action`, `entity_type`, `entity_id`, `diff` with changed field names and non-secret values). Passwords, tokens and hashes never appear in `diff`.
- **FR-19 Security headers.** A middleware adds `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and a `Content-Security-Policy` suitable for a JSON API (`default-src 'none'; frame-ancestors 'none'`), relaxed only for the `/docs` page.

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| NFR-015 | REST semantics and CORS are correct | every status code of §6.2 has a test; preflight tests for allowed and disallowed origins |
| NFR-009 | The implementation matches the contract | schemathesis run against `contracts/openapi.json` passes (subset in `ci-fast`) |
| NFR-008 | Authentication follows OWASP ASVS L1 basics | Argon2id, no plaintext storage, generic login errors, session invalidation, rate limit — each with a test |
| NFR-011 | Requests are traceable | every log line and every problem response carries the same `request_id` |
| — | Coverage | `identity` ≥ 90/80, `fleet` and `freight` ≥ 85/75, routers ≥ 75 (lines/branches) |

## 6. Contracts (API, data/migrations, ports, agent tools)

### 6.1 Data

Type conventions: `DEVELOPMENT.md` §5.2. Every editable table has `id TEXT PK`, `version INTEGER NOT NULL DEFAULT 1`, `created_at`, `updated_at` (both `UtcDateTime`). Columns below extend the short list of report §14.

| Table | Columns (type; constraint) |
|---|---|
| `users` | `email` (TEXT; lower-case, UNIQUE), `password_hash` (TEXT), `role` (TEXT; `admin`/`dispatcher`/`demo`), `locale` (TEXT; `en`/`pl`), `is_active` (BOOLEAN), `failed_logins` (INTEGER), `locked_until` (UtcDateTime NULL), `last_login_at` (UtcDateTime NULL) |
| `sessions` | `token_hash` (TEXT; UNIQUE), `user_id` (FK users, ON DELETE CASCADE), `expires_at`, `created_at`, `ip_hash` (TEXT), `ua_hash` (TEXT) |
| `cost_profiles` | `name` (TEXT; UNIQUE), `currency` (TEXT(3)), `fuel_price_minor_per_l` (INTEGER), `driver_cost_minor_per_hour` (INTEGER), `vehicle_cost_minor_per_km` (INTEGER), `accommodation_minor` (INTEGER), `per_diem` (JSON; country → minor per day), `tolls` (JSON; country → minor per km, plus `annual_vignettes` list), `fx_rates` (JSON; currency → decimal string), `min_profit_minor` (INTEGER), `min_margin_pct` (TEXT decimal), `provenance` (JSON; field → `source`/`assumption`), `is_synthetic` (BOOLEAN) |
| `vehicles` | `label` (TEXT; UNIQUE), `vehicle_type` (TEXT), `body_type` (TEXT), `inner_length_mm`, `inner_width_mm`, `inner_height_mm` (INTEGER NULL), `pallet_places` (INTEGER), `layout_template` (TEXT), `side_access` (TEXT), `payload_kg` (INTEGER), `gvw_kg` (INTEGER), `sleeper_cab` (BOOLEAN), `fuel_l_per_100km_empty_x10` and `fuel_l_per_100km_full_x10` (INTEGER; tenths of a litre), `fuel_speed_curve` (TEXT), `fuel_provenance` (TEXT), `cost_profile_id` (FK cost_profiles, RESTRICT), `is_synthetic` (BOOLEAN) |
| `drivers` | `name` (TEXT), `phone` (TEXT NULL), `home_city` (TEXT), `home_country` (TEXT(2)), `home_lat`, `home_lon` (REAL), `default_rules_profile` (TEXT), `vehicle_id` (FK vehicles, UNIQUE, NULL, RESTRICT), `is_synthetic` (BOOLEAN), `deleted_at` (UtcDateTime NULL) |
| `driver_states` | `driver_id` (FK drivers, CASCADE), `valid_from`, `current_city` (TEXT NULL), `current_lat`, `current_lon` (REAL), `available_from`, `work_today_min`, `drive_today_min`, `work_since_break_min`, `drive_since_break_min`, `work_week_min`, `drive_week_min`, `drive_prev_week_min` (INTEGER ≥ 0), `last_daily_rest_end`, `last_weekly_rest_end` (UtcDateTime NULL), `home_by` (UtcDateTime NULL), `source` (TEXT); index `(driver_id, valid_from DESC)`; no `version` (rows are immutable) |
| `freight_offers` | as report §14; `revenue_amount_minor` NULL allowed; `UNIQUE(source, source_offer_id)`; `status` (`open`/`assigned`/`expired`/`withdrawn`); `public_remark` (TEXT NULL; untrusted text) |
| `freight_stops` | as report §14; `UNIQUE(offer_id, sequence)`; `lat`/`lon` NULL allowed; `window_start` ≤ `window_end` (CHECK) |
| `import_batches`, `raw_freight_records` | as report §14 (used by FEAT-002) |
| `audit_events` | `at`, `actor` (TEXT), `action` (TEXT), `entity_type` (TEXT), `entity_id` (TEXT NULL), `diff` (JSON); index `(entity_type, entity_id)` |
| `app_meta` | `key` (TEXT PK), `value` (JSON), `updated_at` |

Domain value ranges enforced by the API schemas (proposed, OQ-001-03): `payloadKg` 100–2 000; `gvwKg` ≤ 3 500; `palletPlaces` 1–12; `weightKg` 1–3 500; `palletCount` 1–33; counters ≥ 0; `windowStart ≤ windowEnd`; latitude −90…90, longitude −180…180.

### 6.2 API

All paths are under `/api/v1`. JSON is camelCase. "Auth" names the minimum role (§6.5). Every endpoint can also return `401 UNAUTHENTICATED`, `403 FORBIDDEN`, `403 CSRF_FAILED` / `ORIGIN_NOT_ALLOWED` (state-changing methods), `422 VALIDATION_ERROR` and `500 INTERNAL_ERROR`; the table lists the specific ones.

**Authentication**

| Method | Path | Auth | Request | Success | Specific errors |
|---|---|---|---|---|---|
| GET | `/auth/captcha-config` | none | — | `200 {provider:"turnstile", siteKey}` | — |
| POST | `/auth/login` | none | `{email, password, captchaToken}` | `200 {user:{id,email,role,locale}, csrfToken}` + cookies `rp_session`, `rp_csrf` | `400 CAPTCHA_FAILED`, `401 INVALID_CREDENTIALS`, `403 ORIGIN_NOT_ALLOWED`, `429 RATE_LIMITED` |
| POST | `/auth/logout` | any user | — | `204`, cookies cleared | — |
| GET | `/auth/me` | any user | — | `200 {user, csrfToken}` | — |

**Drivers**

| Method | Path | Auth | Request | Success | Specific errors |
|---|---|---|---|---|---|
| GET | `/drivers` | demo | query: `limit`, `cursor`, `homeCity`, `availableBefore`, `hasVehicle` | `200 {items: Driver[], nextCursor}` | — |
| POST | `/drivers` | dispatcher | `DriverCreate` | `201 Driver` + `Location` | `409 DUPLICATE_RESOURCE` (vehicle already assigned), `404 NOT_FOUND` (unknown `vehicleId`) |
| GET | `/drivers/{id}` | demo | — | `200 Driver` (with `vehicle` and latest `state`) | `404` |
| PATCH | `/drivers/{id}` | dispatcher | `DriverUpdate` (with `version`) | `200 Driver` | `404`, `409 VERSION_CONFLICT`, `409 DUPLICATE_RESOURCE` |
| DELETE | `/drivers/{id}` | dispatcher | — | `204` | `404`, `409 DRIVER_HAS_ACTIVE_ASSIGNMENT` |
| GET | `/drivers/{id}/state` | demo | query: `limit`, `cursor` | `200 {items: DriverState[], nextCursor}` (newest first) | `404` |
| POST | `/drivers/{id}/state` | dispatcher | `DriverStateCreate` | `201 DriverState` + `Location: /api/v1/drivers/{id}/state` | `404` |

```
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

**Vehicles**

| Method | Path | Auth | Request | Success | Specific errors |
|---|---|---|---|---|---|
| GET | `/vehicles` | demo | query: `limit`, `cursor`, `palletPlaces`, `unassigned` | `200 {items: Vehicle[], nextCursor}` | — |
| POST | `/vehicles` | dispatcher | `VehicleCreate` | `201 Vehicle` + `Location` | `409 DUPLICATE_RESOURCE` (label), `404` (unknown `costProfileId`) |
| GET | `/vehicles/{id}` | demo | — | `200 Vehicle` | `404` |
| PATCH | `/vehicles/{id}` | dispatcher | `VehicleUpdate` | `200 Vehicle` | `404`, `409 VERSION_CONFLICT`, `409 DUPLICATE_RESOURCE` |
| DELETE | `/vehicles/{id}` | dispatcher | — | `204` | `404`, `409 VEHICLE_ASSIGNED_TO_DRIVER` |

```
VehicleCreate { label, vehicleType ("VEHICLE_UP_TO_3_5_T"), bodyType ("CURTAIN_SIDER"|"TAUTLINER"|"BOX"),
                innerLengthM?, innerWidthM?, innerHeightM? (decimal, 2 places), palletPlaces,
                layoutTemplate ("EUR_MIXED_5X3"|"EUR_MIXED_6X4"|"DECLARED_ONLY"), sideAccess ("LEFT"|"RIGHT"|"BOTH"|"NONE"),
                payloadKg, gvwKg, sleeperCab,
                fuel { lPer100kmEmptyAt90, lPer100kmFullAt90, speedCurve ("VAN_DEFAULT_V1") }, costProfileId }
Vehicle       { id, ...VehicleCreate fields, fuel.provenance, isSynthetic, version, createdAt, updatedAt }
```

**Cost profiles**

| Method | Path | Auth | Request | Success | Specific errors |
|---|---|---|---|---|---|
| GET | `/cost-profiles` | demo | `limit`, `cursor` | `200 {items, nextCursor}` | — |
| POST | `/cost-profiles` | admin | `CostProfileCreate` | `201` + `Location` | `409 DUPLICATE_RESOURCE` (name) |
| GET | `/cost-profiles/{id}` | demo | — | `200 CostProfile` | `404` |
| PATCH | `/cost-profiles/{id}` | admin | `CostProfileUpdate` | `200` | `404`, `409 VERSION_CONFLICT` |
| DELETE | `/cost-profiles/{id}` | admin | — | `204` | `404`, `409 COST_PROFILE_IN_USE` |

```
CostProfileCreate { name, currency ("EUR"), fuelPriceMinorPerL, driverCostMinorPerHour, vehicleCostMinorPerKm,
                    accommodationMinor, perDiem {<country>: minorPerDay}, tolls {perKm: {<country>: minorPerKm}, annualVignettes: [<country>]},
                    fxRates {<currency>: "<decimal>"}, minProfitMinor, minMarginPct ("<decimal>") }
CostProfile       { id, ...fields, provenance {<field>: "source"|"assumption"|"user"}, isSynthetic, version, createdAt, updatedAt }
```

The report lists only `GET`/`PATCH` for `/cost-profiles/{id}`; `DELETE` is added so that CRUD is complete for this resource (non-negotiable decision "full CRUD for … cost profiles").

**Freight offers**

| Method | Path | Auth | Request | Success | Specific errors |
|---|---|---|---|---|---|
| GET | `/freight-offers` | demo | `limit`, `cursor`, `source`, `status`, `originCountry`, `destinationCountry`, `originCity`, `destinationCity`, `pickupFrom`, `pickupTo`, `maxWeightKg`, `maxPallets`, `minCompleteness`, `hasPrice` | `200 {items: FreightOffer[], nextCursor}` | — |
| POST | `/freight-offers` | dispatcher | `FreightOfferCreate` | `201 FreightOffer` + `Location` | — |
| GET | `/freight-offers/{id}` | demo | — | `200 FreightOffer` | `404` |
| PATCH | `/freight-offers/{id}` | dispatcher | `FreightOfferUpdate` | `200` | `404`, `409 VERSION_CONFLICT`, `409 PROVIDER_OFFER_READ_ONLY` |
| DELETE | `/freight-offers/{id}` | dispatcher | — | `204` | `404`, `409 PROVIDER_OFFER_READ_ONLY` |

```
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

`source`, `sourceOfferId`, `isSynthetic`, `status`, `completenessScore`, `missingFields`, `qualityFlags` and `fieldProvenance` are server-set; sending them in a create or update body is a `422` (`extra="forbid"`).

### 6.3 Ports

```python
class CaptchaVerifier(Protocol):                 # identity/ports.py
    def verify(self, token: str, remote_ip: str | None) -> CaptchaResult: ...   # CaptchaResult(ok: bool, error_codes: list[str])

class DriverUsageChecker(Protocol):              # fleet/ports.py — implemented by optimization.jobs in FEAT-004
    def assignment_usage(self, driver_id: UUID) -> Literal["none", "historical", "active"]: ...
```

`TurnstileVerifier` posts the secret, the token and the IP to Cloudflare's verification endpoint. Until FEAT-004 exists, `main.py` injects a `DriverUsageChecker` that always returns `"none"`.

### 6.4 Problem codes introduced here

`VALIDATION_ERROR`, `MALFORMED_REQUEST`, `CAPTCHA_FAILED`, `UNAUTHENTICATED`, `INVALID_CREDENTIALS`, `FORBIDDEN`, `CSRF_FAILED`, `ORIGIN_NOT_ALLOWED`, `NOT_FOUND`, `VERSION_CONFLICT`, `DUPLICATE_RESOURCE`, `PROVIDER_OFFER_READ_ONLY`, `DRIVER_HAS_ACTIVE_ASSIGNMENT`, `VEHICLE_ASSIGNED_TO_DRIVER`, `COST_PROFILE_IN_USE`, `RATE_LIMITED`, `INTERNAL_ERROR`. HTTP statuses and meanings: `DEVELOPMENT.md` §4.5. Codes are stable: renaming one is a breaking change.

### 6.5 Permission matrix

| Capability | `admin` | `dispatcher` | `demo` |
|---|---|---|---|
| Read drivers, vehicles, cost profiles, offers | ✔ | ✔ | ✔ |
| Create/update/delete drivers, vehicles | ✔ | ✔ | ✔ |
| Create/update/delete cost profiles | ✔ | ✖ | ✖ |
| Add a driver state | ✔ | ✔ | ✔ |
| Create/update/delete manual offers | ✔ | ✔ | ✔ |
| Admin endpoints (`/admin/*`) | ✔ | ✖ | ✖ |

Reading the "Auth" columns of §6.2: `demo` = any logged-in role; `dispatcher` = `dispatcher`, `demo` and `admin`; `admin` = `admin` only. The `demo` role behaves like `dispatcher` except for the lower AI budget (FEAT-006) and the periodic data reset (FEAT-002). Drivers and vehicles are writable by every role; cost profiles by `admin` only (owner decision of 2026-11-11 on OQ-001-01).

### 6.6 Configuration

`DATABASE_URL`, `CORS_ALLOWED_ORIGINS`, `SECRET_KEY`, `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `DEMO_EMAIL`, `DEMO_PASSWORD`, `SESSION_TTL_HOURS` (default 12), `LOGIN_RATE_LIMIT_PER_IP` (default `10/minute`), `LOGIN_RATE_LIMIT_PER_ACCOUNT` (default `5/minute`), `PASSWORD_MIN_LENGTH` (default 12). Defaults marked here are proposals (OQ-001-02).

### 6.7 Agent tools

No change.

## 7. Acceptance criteria

**Database**

- **AC-FEAT-001-01** [db] Given a new connection from the application engine When the PRAGMAs are read Then `journal_mode` is `wal`, `foreign_keys` is `1` and `busy_timeout` is `5000`.
- **AC-FEAT-001-02** [db] Given a fresh SQLite file When `alembic upgrade head`, `downgrade base` and `upgrade head` run in sequence Then all three succeed and the final schema contains every table of report §14 plus `app_meta`.
- **AC-FEAT-001-03** [db] Given an entity saved with a UUID id, an aware UTC datetime and a money value of 12 345 minor units When it is read back Then the id is the same UUID, the datetime is aware and equal in UTC, and the amount is the integer 12345; and Given a naive datetime When it is bound to a `UtcDateTime` column Then a `ValueError` is raised.

**CRUD — drivers**

- **AC-FEAT-001-04** [contract] Given an admin session and a valid `DriverCreate` body When `POST /api/v1/drivers` is called Then the status is `201`, the `Location` header is `/api/v1/drivers/{id}`, and the body is the driver with `version = 1`.
- **AC-FEAT-001-05** [contract] Given 7 drivers When `GET /api/v1/drivers?limit=3` is called and then repeated with each `nextCursor` Then the pages contain 3, 3 and 1 items without duplicates, the last `nextCursor` is `null`, and `homeCity=Katowice` returns only matching drivers.
- **AC-FEAT-001-06** [contract] Given an existing driver with a vehicle and two states When `GET /api/v1/drivers/{id}` is called Then the status is `200` and the body embeds the vehicle and the newest state; and Given an unknown id Then the status is `404` with `code = NOT_FOUND`.
- **AC-FEAT-001-07** [contract] Given a driver with `version = 1` When `PATCH` is sent with `version = 1` and a new `name` Then the status is `200`, only `name` changed and `version = 2`; and When a second `PATCH` is sent with `version = 1` Then the status is `409` with `code = VERSION_CONFLICT` and nothing changed.
- **AC-FEAT-001-08** [contract] Given a driver with no assignments When `DELETE` is called Then the status is `204` and a later `GET` returns `404`; Given a driver whose `DriverUsageChecker` answer is `"historical"` Then the status is `204`, the row has `deleted_at` set and the driver is absent from the list; Given the answer `"active"` Then the status is `409` with `code = DRIVER_HAS_ACTIVE_ASSIGNMENT`.
- **AC-FEAT-001-09** [contract] Given a `DriverCreate` body with `homeLat = 123` and an unknown extra field When `POST /api/v1/drivers` is called Then the status is `422`, the content type is `application/problem+json`, `code = VALIDATION_ERROR`, and `errors[]` names both fields.

**CRUD — vehicles, cost profiles, offers, driver state**

- **AC-FEAT-001-10** [contract] Given an admin session When the vehicle endpoints are exercised Then create returns `201` + `Location`, read `200`, update `200` with a version bump, delete `204`; a duplicate `label` returns `409 DUPLICATE_RESOURCE`; `gvwKg = 3600` returns `422`; deleting a vehicle referenced by a driver returns `409 VEHICLE_ASSIGNED_TO_DRIVER`; an unknown id returns `404`.
- **AC-FEAT-001-11** [contract] Given an admin session When the cost-profile endpoints are exercised Then create `201` + `Location`, read `200`, update `200`, delete `204`; a stale version returns `409 VERSION_CONFLICT`; deleting a profile referenced by a vehicle returns `409 COST_PROFILE_IN_USE`; money fields accept only integers (a decimal value returns `422`).
- **AC-FEAT-001-12** [contract] Given a dispatcher session and a valid `FreightOfferCreate` with two stops When `POST /api/v1/freight-offers` is called Then the status is `201` with `Location`; the stored offer has `source = "manual"`, `isSynthetic = false`, `status = "open"`, a `sourceOfferId` starting with `MAN-`, and `fieldProvenance` marks the entered fields as `user`; a body that sets `source` returns `422`.
- **AC-FEAT-001-13** [contract] Given an offer with `source = "mock_timocom_v3"` When `PATCH` or `DELETE /api/v1/freight-offers/{id}` is called Then the status is `409` with `code = PROVIDER_OFFER_READ_ONLY` and the offer is unchanged; and Given a manual offer Then `PATCH` returns `200` and `DELETE` returns `204`.
- **AC-FEAT-001-14** [contract] Given offers from two sources with different countries, weights and completeness When `GET /api/v1/freight-offers` is called with `source`, `originCountry`, `maxWeightKg`, `minCompleteness` and `hasPrice` filters Then only matching offers are returned, each with `completenessScore`, `missingFields`, `qualityFlags` and `fieldProvenance`; an unknown query parameter returns `422`.
- **AC-FEAT-001-15** [contract] Given a driver When `POST /api/v1/drivers/{id}/state` is called twice with different positions Then both return `201`, `GET /api/v1/drivers/{id}/state` lists two rows newest first with `source = "user"`, and `GET /api/v1/drivers/{id}` embeds the second one; a negative counter returns `422`.

**Errors and CORS**

- **AC-FEAT-001-16** [contract] Given any error response of this API (`401`, `403`, `404`, `409`, `422`, `429`, `500`) When its headers and body are inspected Then its content type is `application/problem+json`, it contains `type`, `title`, `status`, `code` and `requestId`, the `requestId` equals the `request_id` of the server log line, and with `APP_ENV=demo` a forced `500` contains no stack trace.
- **AC-FEAT-001-17** [contract] Given `CORS_ALLOWED_ORIGINS=http://localhost:3000` When a preflight `OPTIONS /api/v1/drivers` arrives with `Origin: http://localhost:3000`, `Access-Control-Request-Method: POST` and `Access-Control-Request-Headers: content-type,x-csrf-token,idempotency-key` Then the response allows that origin, has `Access-Control-Allow-Credentials: true`, and lists the method and the three headers.
- **AC-FEAT-001-18** [contract] Given the same configuration When the preflight or a simple `GET` arrives with `Origin: http://evil.example` Then no `Access-Control-Allow-Origin` header is returned; and no response of the API ever contains `Access-Control-Allow-Origin: *`.
- **AC-FEAT-001-19** [unit] Given `CORS_ALLOWED_ORIGINS` that contains `*` When the settings load Then startup fails with a configuration error.

**Authentication and authorisation**

- **AC-FEAT-001-20** [contract] Given the Turnstile "always pass" test keys and the seeded demo account When `POST /api/v1/auth/login` is called with the correct password Then the status is `200`, the body contains the user and `csrfToken`, the `rp_session` cookie is `HttpOnly` with `SameSite=Lax`, the `rp_csrf` cookie equals `csrfToken`, and `GET /api/v1/auth/me` then returns `200`.
- **AC-FEAT-001-21** [contract] Given a wrong password for an existing email and any password for an unknown email When login is called Then both return `401` with `code = INVALID_CREDENTIALS` and identical bodies (apart from `requestId`), and no cookie is set.
- **AC-FEAT-001-22** [contract] Given the Turnstile "always fail" (`2x…`) secret When login is called with correct credentials Then the status is `400` with `code = CAPTCHA_FAILED`, and the password hash was not verified (the verifier is called before the user lookup).
- **AC-FEAT-001-23** [contract] Given a valid session When a `POST`, `PATCH` or `DELETE` is sent without `X-CSRF-Token`, with a wrong token, or with a token of another session Then the status is `403` with `code = CSRF_FAILED` and nothing is changed; with the correct token the request succeeds.
- **AC-FEAT-001-24** [contract] Given a valid session and token When a state-changing request arrives with an `Origin` outside the allowlist or without `Origin` Then the status is `403` with `code = ORIGIN_NOT_ALLOWED`.
- **AC-FEAT-001-25** [contract] Given a logged-in user When `POST /api/v1/auth/logout` is called Then the status is `204`, both cookies are cleared, the session row is gone, and the old cookie gives `401 UNAUTHENTICATED` on `GET /auth/me`.
- **AC-FEAT-001-26** [unit] Given a session created at T with `SESSION_TTL_HOURS = 12` and a `FixedClock` When a request arrives at T + 12 h + 1 s Then it is rejected with `401 UNAUTHENTICATED` and the session is deleted.
- **AC-FEAT-001-27** [contract] Given sessions for `admin`, `dispatcher` and `demo` When every endpoint of §6.2 is called by each role Then the results match the permission matrix of §6.5 (`403 FORBIDDEN` where not allowed) and anonymous calls return `401`.
- **AC-FEAT-001-28** [contract] Given `LOGIN_RATE_LIMIT_PER_ACCOUNT = 5/minute` When six login attempts for one email arrive within a minute Then the sixth returns `429` with `code = RATE_LIMITED` and a `Retry-After` header.
- **AC-FEAT-001-29** [integration] Given an empty database and `.env` copied from `.env.example` When the API starts twice Then exactly one `admin` and one `demo` user exist after each start; and Given `APP_ENV=production` with the default passwords or the Turnstile test keys Then startup fails.
- **AC-FEAT-001-30** [db] Given a successful login, a failed login, and a create, update and delete of a driver When `audit_events` is read Then five rows exist with the right `action`, `actor`, `entity_type` and `entity_id`, and no row contains a password, token or hash.
- **AC-FEAT-001-31** [unit] Given a created user When the stored row is read Then `password_hash` starts with `$argon2id$` and verifies with the password; and Given a created session Then `sessions.token_hash` is the SHA-256 of the cookie value and the raw token is stored nowhere.
- **AC-FEAT-001-32** [contract] Given the running app When `contracts/openapi.json` is regenerated Then it contains every path, method and status code of §6.2, and a schemathesis run over the CRUD endpoints with an authenticated session reports no schema violations.
- **AC-FEAT-001-33** [contract] Given the API When its routes and the OpenAPI document are inspected Then no endpoint creates a user without an admin session (`POST /api/v1/auth/register` and similar paths return `404`).
- **AC-FEAT-001-34** [contract] Given any JSON response When its headers are inspected Then it carries `X-Content-Type-Options: nosniff`, `Referrer-Policy` and `Content-Security-Policy` headers.

## 8. Edge cases

- Email with upper-case letters or surrounding spaces → normalised before lookup and before the per-account rate-limit key.
- `PATCH` with only `version` → `200`, nothing changes, `version` still increases (documented behaviour).
- `PATCH` that assigns a vehicle already used by another driver → `409 DUPLICATE_RESOURCE`.
- Deleting a soft-deleted driver again → `404`.
- Two concurrent `PATCH` requests with the same version → exactly one `200` and one `409`.
- Offer window crossing midnight or spanning days → allowed if `windowStart ≤ windowEnd`.
- Manual offer without a price → stored; `missingFields` contains `revenue`; the engine will reject it with `MISSING_REVENUE`.
- Manual offer in a city unknown to `cities.json` and without coordinates → stored with the flag `MISSING_COORDINATES`.
- `cursor` from another filter set or a tampered cursor → `422`.
- SQLite `database is locked` after `busy_timeout` → mapped to `503` problem+json `code = INTERNAL_ERROR` with a retry hint in the log (not expected with one worker).
- Cookies on plain HTTP localhost → `Secure` is not set; on HTTPS it is.

## 9. Dependencies

- FEAT-000 (skeleton, error handler, CORS middleware, settings).
- ADR-0002, ADR-0009, ADR-0010, ADR-0012.
- Libraries (versions in [`docs/report.md`](../docs/report.md) §9.2): fastapi, pydantic, sqlalchemy, alembic, argon2-cffi, slowapi, httpx (for the Turnstile call; verify version in the registry).
- `data/mock/cities.json` from FEAT-002 for geocoding manual offers; until it exists, tests use a fixture with three cities.
- Shared files: `apps/api/migrations/**`, `contracts/openapi.json`, `.env.example`.

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| 01–03, 30 | `apps/api/tests/db/` | temporary SQLite file; in-memory engine |
| 04–15 | `apps/api/tests/api/test_{drivers,vehicles,cost_profiles,freight_offers,driver_state}.py` | factory functions; fake `DriverUsageChecker`; fixture cities |
| 16, 32, 34 | `apps/api/tests/contract/test_problem_json.py`, `test_schemathesis_crud.py` | generated OpenAPI |
| 17–19, 23, 24 | `apps/api/tests/security/test_cors.py`, `test_csrf.py` | — |
| 20–22, 25–29, 31, 33 | `apps/api/tests/security/test_auth.py`, `test_roles.py`, `test_first_start.py` | `FakeCaptchaVerifier` plus one test per Turnstile test key against a stubbed HTTP transport; `FixedClock` |

No test calls Cloudflare: the verifier's HTTP transport is stubbed to return the documented pass/fail answers for the test keys.

## 11. Open questions

**Owner decisions (2026-11-11):** all proposed defaults in this table are accepted, except OQ-001-01: drivers and vehicles may be created, edited and deleted by `admin`, `dispatcher` and `demo`; cost profiles stay `admin` only (§6.2 and §6.5 are updated).

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-001-01 | Who may create, edit and delete drivers, vehicles and cost profiles? Report §3.3 gives fleet management to `admin`; the endpoint table of §11.3 lists "dispatcher · admin". | Read: all roles. Write: `admin` only (matrix in §6.5). The demo walkthrough logs in as admin for fleet CRUD. | AC-FEAT-001-27; FEAT-005 role-dependent buttons |
| OQ-001-02 | Session lifetime, login rate limits, minimum password length. The report gives no numbers. | 12 h; 10/min per IP and 5/min per account; 12 characters. All configurable. | AC-FEAT-001-26, 28 (values only) |
| OQ-001-03 | Validation ranges for vehicle and offer fields (payload, pallet places, weight). | The ranges in §6.1. | AC-FEAT-001-10 (values only) |
| OQ-001-04 | Default local credentials for `admin` and `demo` in `.env.example`: are committed local-only passwords acceptable given the rule "`.env.example` without secrets"? | Yes, with fixed local values that are rejected when `APP_ENV` is not `local`/`test`; add them to the gitleaks allowlist. | AC-FEAT-000-12, AC-FEAT-001-29 |
| OQ-001-05 | Should `0001_initial` create the tables of FEAT-004 and FEAT-006 as well (one reviewed migration), or should each feature add its own migration? | One initial migration with all MVP tables. | FR-3 |
| OQ-001-06 | Is a manual offer `is_synthetic = false`? It is typed by a user, not generated, but in the demo it is still not a real exchange offer. | `false`, with `source = manual` shown in the UI; the "SYNTHETIC DATA" badge applies to generated data. | AC-FEAT-001-12 |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-09 | Initial draft |
| 2 | 2026-11-11 | Owner decisions on the open questions recorded (§11); fleet writes opened to `dispatcher` and `demo` (§6.2, §6.5) |
| 3 | 2026-11-11 | Status `draft` → `approved` by the owner |
| 4 | 2026-11-11 | Slice 001/1 implementation and migration-cycle tests added for review. No AC changed. Front-matter revision aligned with the changelog. Validation: `docs/reports/FEAT-000-foundation-and-001-1.md`. |
