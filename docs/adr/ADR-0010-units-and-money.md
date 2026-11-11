# ADR-0010: Units and money — SI units, integer minor units, UTC

- Status: accepted (2026-11-11)
- Date: 2026-11-09

## Context

The system adds up kilograms, pallet places, kilometres, minutes, litres and money across many small steps and compares results exactly (golden cases, "profit = revenue − Σ costs" to one minor unit, deterministic ranking). Offers come from several countries and time zones; TIMOCOM gives window times without a zone. SQLite has weak numeric and date types. Floating-point money and mixed units are a classic source of silent errors. Source: [`docs/report.md`](../report.md) §13.3, §14.

## Decision

- **Money:** integer **minor units** plus an ISO-4217 currency code. `float` is forbidden for money. Conversions use explicit `fx_rates` and round half-up once.
- **Domain units:** mass in kg (`int`), lengths in m and distances in km (`Decimal`, 2 places), durations in minutes (`int`), fuel in litres (`Decimal`, 3 places), CO₂ in kg (`Decimal`, 2 places).
- **Database storage (SQLite, portable to PostgreSQL):** money `INTEGER` + `TEXT(3)`; lengths in **mm**, distances in **m**, masses in **kg**, durations in minutes — all `INTEGER`; coordinates `REAL`; UUIDs as `TEXT`.
- **Time:** stored and computed in **UTC** (aware `datetime`); the IANA time zone of each stop is stored separately and used only for display and for rules that depend on local dates. Domain code never calls `datetime.now()`; a `Clock` is injected.
- **Missing values:** `None` plus `missing_fields`; no invented defaults without provenance and a flag.
- **API:** money as `{ "amountMinor": int, "currency": "EUR" }`; timestamps as ISO 8601 with `Z`.
- **Rounding points** are specified once per computed value (FEAT-003 §4.2), so that reconstruction from a stored breakdown is exact.

## Alternatives

| Alternative | Why it was rejected |
|---|---|
| `float` for money and distances | binary rounding errors; results differ between runs and platforms; reconstruction to one minor unit impossible |
| `Decimal` / `NUMERIC` columns for money | SQLite stores them as floating point or text; precision is not guaranteed; integers are exact and portable |
| Local time in the database | ambiguous around daylight-saving changes and across countries; comparisons need conversions everywhere |
| Storing kilometres and metres as decimals in the database | the same SQLite precision issue; integer metres and millimetres are exact |
| A units library with runtime dimension checks | more dependency and overhead than the problem needs; naming conventions (`_kg`, `_km`, `_min`, `_minor`) and typed value objects are enough |

## Consequences

- Conversion code sits at the boundaries (repository ↔ domain, API ↔ domain) and needs tests.
- Field and column names carry their unit suffix.
- Every displayed amount is formatted by one frontend module with the active locale ([`DEVELOPMENT.md`](../../DEVELOPMENT.md) §9).
- Time zones inferred from a country are marked `inferred`; multi-zone countries would need more data (none in the demo set).
- Half-up rounding at defined points is part of the golden-case contract; changing a rounding point changes golden values.
