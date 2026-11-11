---
id: FEAT-002
title: Demo data generators, TIMOCOM v3 mapper, import and first-start seed
status: approved
owner: project owner
requirements: [REQ-001, REQ-002, REQ-003, REQ-004, REQ-006, REQ-032]
adrs: [ADR-0003, ADR-0010, ADR-0014]
modules: [fleet (generator), freight (import, normalisation), integrations.mock, integrations.timocom, data/mock, main.py (seed)]
revision: 1
---

# FEAT-002: Demo data generators, TIMOCOM v3 mapper, import and first-start seed

Priority: **P0**. Nothing in this specification is implemented yet.

> All data produced by this feature is **synthetic**: `is_synthetic = true`, IDs start with `MOCK-`, people, companies and phone numbers are fictional. It is never presented as real TIMOCOM offers or real people, and the UI shows it without TIMOCOM branding.

## 1. Goal

After the first start the application contains a believable demo world without any external service: five drivers with vans and working-time states, 150 freight offers in the TIMOCOM Freight Exchange API v3 format imported through the same mapper a real adapter would use, a default cost profile, and a city table with coordinates. An admin can regenerate or reset this data.

## 2. Business context

There is no access to TIMOCOM ([`context.md`](../context.md) → Project Constraints 2). The optimizer, the agents and the demo need data with realistic structure and deliberate difficulties (missing prices, overweight loads, prompt-injection text). Using the real API format keeps the path to a real adapter open (ADR-0003). Source material: [`docs/report.md`](../docs/report.md) §5, §16, §17.

## 3. Scope / Out of scope

**In scope:** `data/mock/cities.json`; `fleet-generator v1`; `offers-generator v2`; raw TIMOCOM v3 subset schemas; `TimocomV3Mapper` with tolerant parsing and fixtures; `MockFreightProvider`; idempotent import with batches; default cost profile; first-start seed; admin endpoints `demo-data/generate` and `demo-data/reset`; CLI entry points behind `make seed-fleet`.

**Out of scope:** a network client for TIMOCOM (`TimocomFreightProvider` stays a skeleton without HTTP calls; post-MVP); geocoding of arbitrary addresses; multi-stop offers (only 2 stops are generated; P2); interpretation of offer text by AI (FEAT-008); the routing matrix file (FEAT-004).

## 4. Functional requirements

### 4.1 City table — `data/mock/cities.json`

- **FR-1.** The file lists the cities of §6.1 with `name`, `countryCode`, `lat`, `lon` (WGS84, 4 decimals) and `timezone` (IANA). It is the only geocoding source in the MVP: lookup by exact `(name, countryCode)`, case-insensitive.
- **FR-2.** A second, small map `country → timezone` covers the single-zone countries used (PL, DE, CZ, SK, AT, HU, NL, BE, FR, IT, DK). Time zones set from it have provenance `inferred`.

### 4.2 Fleet generator — `fleet-generator v1`

- **FR-3.** Pure function `generate_fleet(seed, reference_date) -> FleetSnapshot`; same inputs → byte-identical JSON output (`data/mock/fleet.json`).
- **FR-4.** It always produces the five drivers and vans of the table in §6.2 (values from report §17.2). Names come from a fixed, committed list of fictional first and last names; phone numbers use an obviously fictional pattern. No library with real personal data is used at runtime.
- **FR-5.** Every vehicle has `vehicle_type = VEHICLE_UP_TO_3_5_T`, `body_type = CURTAIN_SIDER`, `gvw_kg = 3500`, `side_access = BOTH`, fuel parameters with provenance `assumption`, and the default cost profile.
- **FR-6.** One `DriverState` per driver, drawn deterministically from the seed: position = home base or another Polish city of `cities.json`; `available_from` within 0–24 h after 00:00 UTC of the reference date, on a whole 15 minutes; `work_week_min` between 0 and 60 % of 3 600; `drive_week_min` ≤ `work_week_min` and between 0 and 60 % of 3 360; `drive_prev_week_min` between 0 and 2 700; daily counters 0; `last_daily_rest_end` = `available_from`; `home_by` = Friday 18:00 local time of the base in the week of the reference date (the following week if the reference date is a Friday, Saturday or Sunday); `source = generated_mock`.

### 4.3 Offer generator — `offers-generator v2`

- **FR-7.** Pure function `generate_offers(seed, reference_date, count=150) -> (raw_payload, enrichment)`. Output files: `data/mock/offers.timocom.json` (shape `{ "meta": {"requestId", "responseTimestamp"}, "payload": [freightOffer…] }`) and `data/mock/offers.enrichment.json` (keyed by offer `id`). Same inputs → byte-identical files.
- **FR-8.** Raw offers use only fields that exist in TIMOCOM OpenAPI 3.0.6 as listed in report §5.1 (T17, T18): `id`, `vehicleProperties.{type, body, equipment}`, `trackable`, `acceptQuotes`, `publicRemark`, `creationDateTime`, `freightDescription`, `length_m`, `weight_t`, `distance_km`, `paymentDueWithinDays`, `price.{amount, currency}`, `loadingPlaces[].{loadingType, address.{city, country, postalCode, geoCoordinate, geocoded}, earliestLoadingDate, latestLoadingDate, startTime, endTime}`. No contact person (a search result has none). Everything TIMOCOM does not model — pallets, pallet type, service time, difficulty tags — goes to the enrichment file with provenance `generated_mock`.
- **FR-9.** Every offer: `id = "MOCK-" + 6 digits`, `vehicleProperties.type = ["VEHICLE_UP_TO_3_5_T"]`, exactly two loading places (`LOADING` then `UNLOADING`), currency `EUR`.
- **FR-10 Geography.** Each lane has Poland at one end or both: about 45 % domestic PL→PL, about 55 % international (PL→X or X→PL), along the corridors of report §17.3. Origin ≠ destination.
- **FR-11 Load.** Pallets 1–10 with weights favouring 1–4; pallet type 85 % EUR, 10 % industrial, 5 % half; mass 40–1 100 kg; `length_m` consistent with the pallets (`ceil(eq / 2.4 × 10) / 10`).
- **FR-12 Time windows.** Loading on working days within 7 days from the reference date; delivery on the same or a later working day; window lengths 2–8 h; a share of whole-day windows (no `startTime`/`endTime`) and a share of tight 2-hour windows.
- **FR-13 Price.** `price = max(min_fare, round(rate × distance_km × noise))` in whole euros, where `distance_km` is the haversine distance × 1.25, `noise` is log-normal with σ = 0.15 from the seeded generator, `min_fare = 120` and `rate` comes from §6.3. Prices are generated values, not market data.
- **FR-14 Difficulty categories.** The 150 offers contain at least the counts of §6.4. Each tagged offer lists its tags in the enrichment file so that tests and the demo can find it.
- **FR-15 Tolerance cases.** Some offers use the alternative formats that the official OpenAPI itself shows (report T29): `startTime` as `HH:MM:SSZ`, the key `"creationDateTime "` with a trailing space, `distance_km` above 200.

### 4.4 Mapper and normalisation

- **FR-16.** `integrations/timocom/schemas.py` defines Pydantic models for the subset of OpenAPI 3.0.6 used here, with a comment naming the version and the source URL. Unknown extra fields are ignored at this layer (provider data), never an error.
- **FR-17.** `TimocomV3Mapper.to_domain(record) -> NormalizedOffer | MappingFailure` applies the mapping table of §6.5 and sets `field_provenance` for every mapped field.
- **FR-18 Tolerant parsing.** Accept `startTime`/`endTime` as `HH:MM` and as `HH:MM:SSZ` (the `Z` is ignored: the time is local to the stop, provenance `inferred`); accept `distance_km` > 200; read `creationDateTime` also from the key with a trailing space. Each tolerated deviation adds a quality flag (`TIME_FORMAT_TOLERATED`, `KEY_WHITESPACE_TOLERATED`).
- **FR-19 Missing data.** No `price` → `revenue = null`, `missing_fields += ["revenue"]`. No `geoCoordinate` → geocode from `cities.json` (`derived`); if not found → `lat/lon = null`, flag `MISSING_COORDINATES`. No times → window 00:00–23:59 local, flag `TIME_WINDOW_DAY_ONLY`. No pallets in the enrichment → `pallet_count = ceil(length_m × 2.4)` with provenance `derived` and flag `PALLETS_DERIVED`; no pallets and no length → `pallet_count = null`, flag `MISSING_CAPACITY_DATA`. `service_minutes` = 30 with provenance `default` and flag `SERVICE_TIME_DEFAULTED`.
- **FR-20 Failures.** A record that cannot become an offer at all (fewer than two loading places, first place not `LOADING`, last not `UNLOADING`, unparsable dates, non-numeric weight) returns `MappingFailure(code, detail)`; it is counted in the batch and never stored as an offer.
- **FR-21 Suspicious text.** `publicRemark` and `freightDescription` are stored as untrusted text. A deterministic detector flags offers whose text matches instruction-like patterns (for example "ignore previous", "system:", "assign this", "you must") with `SUSPICIOUS_TEXT`. The detector is a helper for the UI and the agents, not a security boundary.

### 4.5 Provider, import and seed

- **FR-22.** `MockFreightProvider` implements `FreightProvider` (`name = "mock_timocom_v3"`): `search` yields `RawOfferRecord`s from the generated payload filtered by the query; `lookup` returns an empty list (no contact data exists). It performs no network access.
- **FR-23 Import.** `ImportService.run(provider, query) -> ImportBatch`: for every raw record compute `payload_sha256`; if `(source, source_offer_id, payload_sha256)` exists → count as `unchanged`; if the offer exists with another hash → store the new raw record, update the offer (`version + 1`), count as `updated`; otherwise insert and count as `imported`. Mapping failures count as `failed`. The batch row stores `counts` and status. Running the same import twice changes nothing.
- **FR-24.** Imported offers have `source = "mock_timocom_v3"`, `is_synthetic = true`, `status = open`, `retention_until` = latest loading date + 1 day.
- **FR-25 Default cost profile.** `DEMO-DEFAULT` with the values of §6.6, each field's provenance `source` or `assumption` exactly as labelled in report §17.4.
- **FR-26 First-start seed.** In the application lifespan, after the first-start accounts (FEAT-001): if `app_meta["seed_version"]` is absent → create `DEMO-DEFAULT`, generate and store the fleet, generate and import the offers (seed `MOCK_SEED`, reference date `MOCK_REFERENCE_DATE` or, if empty, the current UTC date), write `seed_version` and an audit event. The whole seed runs in one transaction per step and is idempotent.
- **FR-27 Admin endpoints.** `POST /admin/demo-data/generate` re-runs the generators with the given seed and reference date and upserts the result. `POST /admin/demo-data/reset` deletes all synthetic data and everything derived from it, then runs the seed again with the defaults (§6.7).
- **FR-28 CLI.** `uv run python -m routepilot.fleet.generator --seed … --reference-date … --out data/mock/fleet.json` and the equivalent for offers; `make seed-fleet` wraps them. The committed files are produced with `seed = 20261109` and `reference_date = 2026-11-16`.

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| — | Determinism | same seed and reference date → byte-identical output files; a snapshot test compares against the committed files |
| — | No network | generators, mapper, provider and seed run with networking disabled in tests |
| — | Seed time | first start including seed finishes in ≤ 10 s on a typical laptop (measured, target) |
| — | Coverage | `freight`, `fleet` ≥ 85/75; mapper branches for every tolerance and failure case |
| — | Honesty | 100 % of generated rows have `is_synthetic = true` |

## 6. Contracts (API, data/migrations, ports, agent tools)

### 6.1 `data/mock/cities.json`

```json
{ "version": 1, "cities": [ { "name": "Katowice", "countryCode": "PL", "lat": 50.2649, "lon": 19.0238, "timezone": "Europe/Warsaw" } ] }
```

Coordinates are approximate city-centre values (confidence **A**), chosen by this specification as demo data. They are inputs of the golden cases, so changing one is a specification change.

| Country | City | Lat | Lon | Time zone |
|---|---|---|---|---|
| PL | Katowice | 50.2649 | 19.0238 | Europe/Warsaw |
| PL | Wrocław | 51.1079 | 17.0385 | Europe/Warsaw |
| PL | Opole | 50.6751 | 17.9213 | Europe/Warsaw |
| PL | Kraków | 50.0647 | 19.9450 | Europe/Warsaw |
| PL | Łódź | 51.7592 | 19.4560 | Europe/Warsaw |
| PL | Poznań | 52.4064 | 16.9252 | Europe/Warsaw |
| PL | Warszawa | 52.2297 | 21.0122 | Europe/Warsaw |
| PL | Gdańsk | 54.3520 | 18.6466 | Europe/Warsaw |
| PL | Szczecin | 53.4285 | 14.5528 | Europe/Warsaw |
| PL | Rzeszów | 50.0412 | 21.9991 | Europe/Warsaw |
| PL | Bielsko-Biała | 49.8224 | 19.0584 | Europe/Warsaw |
| PL | Częstochowa | 50.8118 | 19.1203 | Europe/Warsaw |
| DE | Dresden | 51.0504 | 13.7373 | Europe/Berlin |
| DE | Leipzig | 51.3397 | 12.3731 | Europe/Berlin |
| DE | Berlin | 52.5200 | 13.4050 | Europe/Berlin |
| DE | Hamburg | 53.5511 | 9.9937 | Europe/Berlin |
| DE | München | 48.1351 | 11.5820 | Europe/Berlin |
| DE | Nürnberg | 49.4521 | 11.0767 | Europe/Berlin |
| DE | Köln | 50.9375 | 6.9603 | Europe/Berlin |
| DE | Frankfurt | 50.1109 | 8.6821 | Europe/Berlin |
| DE | Stuttgart | 48.7758 | 9.1829 | Europe/Berlin |
| DE | Hannover | 52.3759 | 9.7320 | Europe/Berlin |
| CZ | Praha | 50.0755 | 14.4378 | Europe/Prague |
| CZ | Brno | 49.1951 | 16.6068 | Europe/Prague |
| CZ | Ostrava | 49.8209 | 18.2625 | Europe/Prague |
| SK | Žilina | 49.2231 | 18.7394 | Europe/Bratislava |
| SK | Bratislava | 48.1486 | 17.1077 | Europe/Bratislava |
| AT | Wien | 48.2082 | 16.3738 | Europe/Vienna |
| AT | Linz | 48.3069 | 14.2858 | Europe/Vienna |
| HU | Budapest | 47.4979 | 19.0402 | Europe/Budapest |
| HU | Győr | 47.6875 | 17.6504 | Europe/Budapest |
| NL | Venlo | 51.3704 | 6.1724 | Europe/Amsterdam |
| NL | Rotterdam | 51.9244 | 4.4777 | Europe/Amsterdam |
| BE | Antwerpen | 51.2194 | 4.4025 | Europe/Brussels |
| FR | Strasbourg | 48.5734 | 7.7521 | Europe/Paris |
| FR | Lyon | 45.7640 | 4.8357 | Europe/Paris |
| IT | Verona | 45.4384 | 10.9916 | Europe/Rome |
| IT | Milano | 45.4642 | 9.1900 | Europe/Rome |
| DK | Kolding | 55.4904 | 9.4722 | Europe/Copenhagen |

39 cities (the report says "~40"). The five driver bases are among them, so the routing matrix of FEAT-004 is 39 × 39.

### 6.2 Fleet (report §17.2)

| Driver | Base | Van label | Pallet places | Layout template | Interior L × W × H (m) | Payload kg | Sleeper cab |
|---|---|---|---|---|---|---|---|
| D1 | Katowice | `BUS-01` | 10 | `EUR_MIXED_6X4` | 4.85 × 2.10 × 2.10 | 1 085 | no |
| D2 | Wrocław | `BUS-02` | 10 | `EUR_MIXED_6X4` | 4.85 × 2.10 × 2.10 | 1 050 | yes |
| D3 | Poznań | `BUS-03` | 9 | `DECLARED_ONLY` | not set (dimensions unknown, Q11) | 1 000 | no |
| D4 | Łódź | `BUS-04` | 8 | `EUR_MIXED_5X3` | 4.20 × 2.10 × 2.30 | 880 | no |
| D5 | Kraków | `BUS-05` | 8 | `EUR_MIXED_5X3` | 4.20 × 2.10 × 2.15 | 765 | no |

Dimensions and payloads match ranges seen in listings (confidence A). Default rules profile: `pl_domestic_employee_v1`; the engine switches to `eu561_van_international_v1` for a plan with an international leg. Fuel parameters for every van: 11.0 l/100 km empty, 13.0 l/100 km full, curve `VAN_DEFAULT_V1`, provenance `assumption` (the report gives these numbers for the 10 EP van only — OQ-002-01).

### 6.3 Rates used by the price formula (report §17.4)

| Lane | Rate €/km | Label |
|---|---|---|
| PL→CZ, PL→SK | 0.93 | source (V) — Trans.eu Freight Radar spot medians, August/September 2026 |
| PL→HU | 0.79 | source (V) |
| PL→DE | 0.68 | source (V) |
| PL→FR | 0.60 | source (V) |
| PL→PL | 0.85 | assumption |
| X→PL (returns) | 0.7 × rate(PL→X) | assumption |
| PL→AT, NL, BE, DK | 0.68 (the PL→DE value) | assumption — not in the report's table (OQ-002-03) |
| PL→IT | 0.60 (the PL→FR value) | assumption — not in the report's table (OQ-002-03) |
| Minimum fare | 120 € | assumption |

### 6.4 Difficulty categories (minimum counts in the 150 generated offers)

| Tag | Meaning | Min count |
|---|---|---|
| `NO_PRICE` | `price` absent | 6 |
| `NO_PALLETS` | no enrichment pallets (length present) | 5 |
| `NO_COORDINATES` | `geoCoordinate` null, `geocoded = false`; half of them in a city that is in `cities.json`, half with a place name that is not | 4 |
| `INCOMPATIBLE_BODY` | requires a refrigerated body only | 5 |
| `INCOMPATIBLE_EQUIPMENT` | requires a tail lift | 4 |
| `TOO_HEAVY_ALL` | mass above 1 085 kg (no demo van can carry it) | 4 |
| `HEAVY_FOR_8EP` | mass 766–1 050 kg (fits 10 EP vans only) | 10 |
| `TIGHT_WINDOW` | 2-hour windows | 15 |
| `DAY_ONLY_WINDOW` | no `startTime`/`endTime` | 10 |
| `RETURN_TO_BASE` | destination is one of the five bases, delivery on Thursday or Friday | 15 |
| `UNPROFITABLE_DETOUR` | minimum fare on a long lane | 5 |
| `MUTUALLY_EXCLUSIVE` | pairs with overlapping windows and combined load above capacity | 4 pairs |
| `PROMPT_INJECTION` | instruction-like text in `publicRemark` | 3 (2 %) |
| `ALT_TIME_FORMAT` | `HH:MM:SSZ` | 5 |
| `KEY_WITH_SPACE` | `"creationDateTime "` | 2 |

An offer may carry several tags. Body and equipment enumeration values are copied from the official OpenAPI enumerations at implementation time (OQ-002-02).

### 6.5 Mapping TIMOCOM v3 → internal offer (report §16.0a)

| Internal field | Source | Provenance |
|---|---|---|
| `source_offer_id` | `id` | `source` |
| `description` | `freightDescription` | `source` (untrusted text) |
| `public_remark` | `publicRemark` | `source` (untrusted text) |
| `revenue_amount_minor`, `revenue_currency` | `price.amount` × 100, `price.currency` | `source` |
| `weight_kg` | `weight_t` × 1000, rounded half-up | `source` |
| `loading_length_m` | `length_m` | `source`; its meaning as loading metres is `inferred` |
| `required_body_types`, `required_vehicle_types` | `vehicleProperties.body[]`, `.type[]` | `source` |
| stops, `stop_type` | `loadingPlaces[]`, `loadingType` | `source` |
| `city`, `postal_code`, `country_code` | `address.*` | `source` |
| `lat`, `lon` | `address.geoCoordinate` or `cities.json` | `source` / `derived` |
| `timezone` | country map | `inferred` |
| `window_start`, `window_end` | `earliestLoadingDate` + `startTime`, `latestLoadingDate` + `endTime`, local → UTC | `source` + `inferred` (zone) |
| `pallet_count`, `pallet_type` | enrichment file | `generated_mock` (or `derived`) |
| `service_minutes` | — | `default` |
| TIMOCOM `distance_km` | `distance_km` | `source`, informational only (kept in the raw record, not used by the engine) |

### 6.6 Default cost profile `DEMO-DEFAULT` (report §17.4)

| Field | Value | Provenance |
|---|---|---|
| `currency` | EUR | — |
| `fuel_price_minor_per_l` | 181 | source |
| `driver_cost_minor_per_hour` | 1400 | assumption |
| `vehicle_cost_minor_per_km` | 12 | assumption |
| `accommodation_minor` | 5500 | assumption |
| `per_diem` | `{"PL": 1059}` (45 zł ÷ 4.25), used for domestic plans only (FEAT-003 FR-12); no entries for other countries | source (Act on Drivers' Working Time Art. 21a and 26f; regulation on business-trip allowances) |
| `tolls.perKm` | `{"PL": 0, "DE": 0, "FR": 12, "IT": 12}` (minor units per km) | PL, DE: source; FR: assumption; IT: assumption (OQ-002-04) |
| `tolls.annualVignettes` | `["AT", "CZ", "SK", "HU"]` → marginal cost 0 with the plan flag `VIGNETTE_ASSUMED_ANNUAL` | assumption |
| `fx_rates` | `{"PLN": "4.25"}` | assumption |
| `min_profit_minor`, `min_margin_pct` | 0, `"0"` | assumption (OQ-003-09) |

### 6.7 API

| Method | Path | Auth | Request | Success | Errors |
|---|---|---|---|---|---|
| POST | `/api/v1/admin/demo-data/generate` | admin | `{ seed?: int, referenceDate?: date, drivers?: 5, offers?: int (1–500, default 150) }` | `200 { importBatchId, drivers, vehicles, offers: {imported, updated, unchanged, failed} }` | `422` (for example `drivers ≠ 5` in v1) |
| POST | `/api/v1/admin/demo-data/reset` | admin | — | `200` with the same shape | — |

`reset` deletes: all rows with `is_synthetic = true` (drivers, vehicles, driver states, offers, raw records, cost profile `DEMO-DEFAULT`), all optimisation jobs, plans, assignments, agent threads and runs, approval requests, explanations and the routing cache; manual offers and user-created fleet rows are also removed. Users, sessions and audit events stay. Then the seed runs again. Both endpoints write an audit event (`demo_data.generated`, `demo_data.reset`).

### 6.8 Ports

`FreightProvider`, `OfferMapper` as in [`context.md`](../context.md) → External Integration Contracts. Value objects: `RawOfferRecord(source, source_offer_id, payload: dict, fetched_at)`, `MappingFailure(code, detail)`, `FreightSearchQuery(origin?, destination?, radius_km?, loading_from?, loading_to?, max_weight_kg?, vehicle_type)`.

### 6.9 Data / migrations

No new migration (tables from FEAT-001). `app_meta` keys: `seed_version` (`{"version": 1, "seed": …, "referenceDate": …, "at": …}`).

### 6.10 Agent tools

No change.

## 7. Acceptance criteria

- **AC-FEAT-002-01** [unit] Given seed 20261109 and reference date 2026-11-16 When `generate_fleet` runs twice Then the outputs are byte-identical and equal to the committed `data/mock/fleet.json`.
- **AC-FEAT-002-02** [unit] Given the generated fleet When its content is inspected Then it has exactly 5 drivers and 5 vehicles with the bases, pallet places, layout templates, interior dimensions, payloads and sleeper-cab flags of §6.2, every vehicle has `gvw_kg = 3500` and fuel provenance `assumption`, and D3's interior dimensions are null.
- **AC-FEAT-002-03** [property] Given any seed and reference date When `generate_fleet` runs Then every generated `DriverState` satisfies the ranges of FR-6, `home_by` is a Friday 18:00 in the base's time zone after `available_from`, and all rows have `is_synthetic = true` and `source = generated_mock`.
- **AC-FEAT-002-04** [unit] Given seed 20261109 and reference date 2026-11-16 When `generate_offers` runs twice Then both files are byte-identical, equal to the committed files, and the payload has exactly 150 offers with unique ids matching `^MOCK-\d{6}$`.
- **AC-FEAT-002-05** [property] Given any seed When `generate_offers` runs Then every offer has exactly two loading places (`LOADING`, `UNLOADING`) in different cities of `cities.json` with Poland at one end at least, type `["VEHICLE_UP_TO_3_5_T"]`, 1–10 pallets, mass 40–1 100 kg, loading dates within 7 days of the reference date on working days, and `windowStart ≤ windowEnd`; over the 150 offers the domestic share is 35–55 %.
- **AC-FEAT-002-06** [unit] Given the committed offers When the tags in the enrichment file are counted Then every tag of §6.4 occurs at least the stated number of times according to the enrichment file, and each tagged offer really has the property (for example every `NO_PRICE` offer has no `price`).
- **AC-FEAT-002-07** [unit] Given an offer without the `NO_PRICE` tag When its price is recomputed Then `price.amount` is a whole number ≥ 120 and equals `max(120, round(rate × distance × noise))` recomputed from the recorded lane, distance and noise value in the enrichment file.
- **AC-FEAT-002-08** [unit] Given `data/mock/cities.json` When the file is loaded Then it validates against its schema, contains the 39 cities of §6.1 with those coordinates and time zones, and has no duplicate `(name, countryCode)`.
- **AC-FEAT-002-09** [contract] Given the freight-offer example from the official OpenAPI 3.0.6 file stored as a fixture with a source note When `TimocomV3Mapper.to_domain` runs Then it returns a `NormalizedOffer` whose fields follow §6.5 and whose `field_provenance` has an entry for every mapped field.
- **AC-FEAT-002-10** [contract] Given fixtures with `startTime = "08:15:22Z"`, with the key `"creationDateTime "` and with `distance_km = 4711` When the mapper runs Then all three map successfully, the first two carry the flags `TIME_FORMAT_TOLERATED` and `KEY_WHITESPACE_TOLERATED`, and the window of the first starts at 08:15 local time of the stop.
- **AC-FEAT-002-11** [unit] Given a raw offer without `price` When the mapper runs Then `revenue` is null and `missing_fields` contains `revenue`; Given one without `geoCoordinate` in Katowice Then the coordinates come from `cities.json` with provenance `derived`; Given one in an unknown place Then `lat/lon` are null with the flag `MISSING_COORDINATES`; Given one without times Then the window is 00:00–23:59 local with `TIME_WINDOW_DAY_ONLY`; Given one without pallets but with `length_m = 1.7` Then `pallet_count = 5` (`ceil(1.7 × 2.4)`) with provenance `derived`.
- **AC-FEAT-002-12** [unit] Given a stop in Germany with `startTime = "08:00"` on 2026-11-17 When the mapper runs Then `window_start` is `2026-11-17T07:00Z`, `timezone = "Europe/Berlin"` and the zone provenance is `inferred`; and Given a record with one loading place Then the mapper returns `MappingFailure`.
- **AC-FEAT-002-13** [db] Given an empty database When the import of the generated payload runs twice Then the first batch reports `imported = 150 − failed`, the second reports everything as `unchanged`, and the row counts of `freight_offers`, `freight_stops` and `raw_freight_records` are equal after both runs.
- **AC-FEAT-002-14** [db] Given an imported offer When the same offer arrives with a changed price Then a second raw record exists, the offer's revenue and `version` changed, and the batch counts it as `updated`; a record that fails mapping is counted as `failed` and creates no offer.
- **AC-FEAT-002-15** [integration] Given an empty database and no API keys When the API starts Then users, the `DEMO-DEFAULT` cost profile, 5 drivers, 5 vehicles, 5 driver states and the offers exist and `app_meta.seed_version` is set; When it starts a second time Then no row count changes.
- **AC-FEAT-002-16** [contract] Given an admin session When `POST /api/v1/admin/demo-data/generate` is called with `{ "seed": 7 }` Then the status is `200` with counts, an audit event exists, and a dispatcher session gets `403 FORBIDDEN`; `{ "drivers": 6 }` returns `422`.
- **AC-FEAT-002-17** [contract] Given a database with a manual offer, an optimisation job and an assignment When `POST /api/v1/admin/demo-data/reset` is called Then the status is `200`, those rows are gone, users and audit events remain, and the data equals a fresh seed.
- **AC-FEAT-002-18** [db] Given a seeded database When its rows are inspected Then every driver, vehicle, driver state, raw record and imported offer has `is_synthetic = true`, every imported offer has `source = "mock_timocom_v3"` and an id starting with `MOCK-`, and no row contains a phone number or email that matches a real-looking pattern outside the fictional pattern.
- **AC-FEAT-002-19** [unit] Given the three `PROMPT_INJECTION` offers When they are imported Then each is imported with the quality flag `SUSPICIOUS_TEXT` and its remark is stored unchanged in `public_remark`; and Given an ordinary remark Then the flag is absent.
- **AC-FEAT-002-20** [unit] Given `MockFreightProvider` with networking disabled When `search` is called with a query for vehicle type `VEHICLE_UP_TO_3_5_T` and an origin area Then it yields only matching records, `lookup` returns an empty list, and no socket is opened.

## 8. Edge cases

- Reference date on a weekend → loading dates start on the next working day; `home_by` moves to the following Friday.
- A generated lane shorter than the minimum-fare distance → price = 120.
- Duplicate offer id inside one payload → the second record is a `MappingFailure` (`DUPLICATE_IN_BATCH`).
- `weight_t = 0` → mapped to 0 kg and flagged `ZERO_WEIGHT`; the engine treats it as missing capacity data.
- A city name with different letter case or surrounding spaces → matched; a different spelling (for example an exonym) → not matched, `MISSING_COORDINATES`.
- `price.currency` other than EUR → stored as is; conversion happens in the cost model with `fx_rates`; an unknown currency → the engine rejects the offer with `MISSING_REVENUE`.
- `generate` called while an optimisation job is running → allowed; the job works on its snapshot.
- `reset` called by the `demo` role → `403`.

## 9. Dependencies

- FEAT-001 (tables, CRUD services, audit, first-start accounts).
- ADR-0003 (TIMOCOM integration), ADR-0014 (capacity).
- The official TIMOCOM OpenAPI 3.0.6 file as the source of the fixture examples and enumeration values ([`docs/report.md`](../docs/report.md) §40). It is read once by a human or an agent with approval and stored as fixtures; no test downloads it.
- Shared files: `data/mock/*.json`.

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| 01–03 | `apps/api/tests/unit/fleet/test_generator.py`, `tests/props/test_fleet_generator.py` | committed `data/mock/fleet.json` |
| 04–07 | `apps/api/tests/unit/freight/test_offers_generator.py`, `tests/props/test_offers_generator.py` | committed offers and enrichment files |
| 08 | `apps/api/tests/unit/test_cities.py` | `data/mock/cities.json` |
| 09–12, 19 | `apps/api/tests/contract/test_timocom_mapper.py` | `apps/api/tests/fixtures/timocom/*.json` with a source annotation per file |
| 13, 14, 18 | `apps/api/tests/db/test_import.py` | in-memory SQLite |
| 15 | `apps/api/tests/integration/test_first_start_seed.py` | temporary SQLite file |
| 16, 17 | `apps/api/tests/api/test_admin_demo_data.py` | admin and dispatcher sessions |
| 20 | `apps/api/tests/unit/integrations/test_mock_provider.py` | socket-blocking fixture |

## 11. Open questions

**Owner decisions (2026-11-11):** all proposed defaults in this table are accepted, except the per-diem part of OQ-002-04: no per diem is charged on international plans and the domestic rate is `{"PL": 1059}` (FEAT-003 FR-12; §6 cost-profile table updated). The toll defaults of OQ-002-04 are accepted as assumptions.

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-002-01 | Fuel consumption of the 8 EP and 9 EP vans. The report states 11.0 / 13.0 l/100 km only for the 10 EP van. | Use the same values for all vans, provenance `assumption`. | values in `fleet.json`; golden cases with 8 EP vans (GOLD-003, 006, 009, 010) |
| OQ-002-02 | Exact TIMOCOM enumeration values for a refrigerated body and a tail lift, and the sub-schema of `customer`. They are not quoted in the report. | Copy them from the official OpenAPI enumerations when the fixtures are created; omit `customer` from mock offers. | AC-FEAT-002-06 (tags `INCOMPATIBLE_*`), GOLD-006 offer O5 |
| OQ-002-03 | Rates for lanes PL→AT, NL, BE, DK, IT (not in the report's table). | 0.68 €/km (the DE value) and 0.60 €/km for IT, labelled `assumption`. | AC-FEAT-002-07 |
| OQ-002-04 | Per diems of countries other than DE and per-km tolls of IT, NL, BE, DK. The report marks them "to be verified". | Fallback per diem 49 € with the warning `PER_DIEM_DEFAULTED`; IT toll 0.12 €/km, others 0; all labelled `assumption`. Replace with verified values from the regulation table when available. | cost of international plans outside PL/DE |
| OQ-002-05 | Minimum counts of the difficulty categories (§6.4). The report gives categories and "2 %" for prompt injection, not counts. | The counts in §6.4. | AC-FEAT-002-06 |
| OQ-002-06 | Does `reset` also remove data created by users (manual offers, added vehicles)? | Yes — it restores the exact first-start state. | AC-FEAT-002-17 |
| OQ-002-07 | Reference date when `MOCK_REFERENCE_DATE` is empty. | The UTC date of the first start, so offers are always in the near future. | FR-26 |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-09 | Initial draft |
| 2 | 2026-11-11 | Owner decisions on the open questions recorded (§11); statutory per-diem values in the cost profile |
| 3 | 2026-11-11 | Status `draft` → `approved` by the owner |
