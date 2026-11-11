# FEAT-002 — Demo data generators and import. Sourced by scripts/create_github_issues.sh.
# shellcheck shell=bash disable=SC2034

s_002_1() {
  I_ID="002/1"; I_FEAT="002"; I_TITLE="cities.json and fleet-generator v1 with the committed fleet.json"
  I_AREA="backend data"; I_SIZE="M"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-12"
  I_ACS="01 02 03 08"; I_DEPS="001/1"
  I_GATES="make check, make test-props"
  I_LOCK="\`data/mock/cities.json\`, \`data/mock/fleet.json\`"
  I_BRANCH="feat/FEAT-002-cities-fleet-generator"; I_REQS="REQ-004, REQ-032"; I_ADRS="0003 0014"; I_SCOPE_TAG="fleet"
  txt T_GOAL <<'EOF'
The fixed geography of the demo (39 cities with coordinates and time zones) and a deterministic generator for the five synthetic drivers and their vans, whose committed output is byte-identical on every run. Golden cases, routing and the engine all read these files.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-002-demo-data-generators.md` §4.1 FR-1, FR-2, §4.2 FR-3 … FR-6, §6.1 (city table — binding values), §6.2 (fleet table), §8 (reference date on a weekend), §11 OQ-002-01, OQ-002-07
- `docs/report.md` §17.2 (fleet), `docs/adr/ADR-0014-van-capacity.md`
- `context.md` → Core Domain Rules 16, Agent Collaboration Protocol 14 (mock vs production data)
EOF
  txt T_SCOPE <<'EOF'
- `data/mock/cities.json` with exactly the 39 cities of §6.1 (`name`, `countryCode`, `lat`, `lon` with 4 decimals, IANA `timezone`) and its JSON schema; lookup by exact `(name, countryCode)`, case-insensitive (FR-1).
- The `country → timezone` map for PL, DE, CZ, SK, AT, HU, NL, BE, FR, IT, DK (provenance `inferred`, FR-2).
- `generate_fleet(seed, reference_date) -> FleetSnapshot` — pure, seeded `random.Random`, byte-identical JSON (FR-3).
- Always the five drivers and vans of §6.2: bases, labels `BUS-01` … `BUS-05`, pallet places 10/10/9/8/8, layout templates, interiors (D3 null), payloads, sleeper cab only for D2; `gvw_kg = 3500`, `CURTAIN_SIDER`, `side_access = BOTH`, fuel 11.0 / 13.0 l/100 km with `VAN_DEFAULT_V1` and provenance `assumption` (FR-4, FR-5, OQ-002-01).
- Fictional names from a committed list; obviously fictional phone numbers; no personal-data library.
- One `DriverState` per driver inside the ranges of FR-6 (`available_from` on whole 15 minutes, weekly counters, `home_by` = Friday 18:00 local time of the base, the following week when the reference date is Fri–Sun, `source = generated_mock`).
- CLI: `uv run python -m routepilot.fleet.generator --seed 20261109 --reference-date 2026-11-16 --out data/mock/fleet.json` (FR-28); commit the output.
EOF
  txt T_OUT <<'EOF'
- Offers (002/2), mapper (002/3), import and seed (002/4, 002/5); writing to the database.
- The routing matrix (004/1).
EOF
  txt T_FILES <<'EOF'
- `data/mock/cities.json`, `data/mock/cities.schema.json`, `data/mock/fleet.json` — new
- `apps/api/src/routepilot/fleet/generator.py`, `apps/api/src/routepilot/fleet/generator_names.py` (*suggested*) — new
- `apps/api/src/routepilot/shared/geo.py` (*suggested*: cities loader, country → time-zone map) — new
- `apps/api/tests/unit/fleet/test_generator.py`, `apps/api/tests/props/test_fleet_generator.py`, `apps/api/tests/unit/test_cities.py` — new
EOF
  txt T_IFACE <<'EOF'
```python
def generate_fleet(seed: int, reference_date: date) -> FleetSnapshot: ...   # pure
def load_cities(path: Path) -> CityTable: ...                               # suggested
class CityTable:
    def lookup(self, name: str, country_code: str) -> City | None: ...      # exact, case-insensitive
```
`cities.json` shape: `{ "version": 1, "cities": [ { "name", "countryCode", "lat", "lon", "timezone" } ] }`.
EOF
  txt T_TESTS <<'EOF'
- `tests/unit/fleet/test_generator.py` — seed 20261109 + 2026-11-16 twice → byte-identical and equal to the committed `fleet.json` → AC-01; exactly 5 drivers / 5 vehicles with the §6.2 values, `gvw_kg = 3500`, fuel provenance `assumption`, D3 interior null → AC-02.
- `tests/props/test_fleet_generator.py` — any seed and date: states within FR-6 ranges, `home_by` a Friday 18:00 base-local after `available_from`, `is_synthetic = true`, `source = generated_mock`. → AC-03
- `tests/unit/test_cities.py` — schema-valid, the 39 cities with those coordinates and zones, no duplicate `(name, countryCode)`. → AC-08
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run python -m routepilot.fleet.generator --seed 20261109 --reference-date 2026-11-16 --out ../../data/mock/fleet.json
git diff --exit-code ../../data/mock/fleet.json   # second run: no change
uv run pytest tests/unit/fleet tests/unit/test_cities.py tests/props/test_fleet_generator.py -q
make check && make test-props
```
EOF
  txt T_TIPS <<'EOF'
- City coordinates are inputs of the golden cases — copy them exactly from §6.1; changing one is a spec change.
- Byte-identical JSON: `sort_keys=True`, fixed separators, `ensure_ascii=False`, UTF-8, trailing newline; Polish and German names (Wrocław, Łódź, Köln) must stay NFC.
- Compute `home_by` with `zoneinfo` in the base's zone, then convert to UTC — DST matters in some weeks.
- Never use the global `random` module; pass a seeded `random.Random`.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-002-01 (accepted): the same fuel values (11.0 / 13.0 l/100 km) for every van, provenance `assumption`.
- OQ-002-07 (accepted): with `MOCK_REFERENCE_DATE` empty the reference date is the UTC date of the first start (used by the seed in 002/5; the committed files use 2026-11-16).
EOF
}
register s_002_1

s_002_2() {
  I_ID="002/2"; I_FEAT="002"; I_TITLE="offers-generator v2: 150 synthetic offers in the TIMOCOM v3 shape plus enrichment"
  I_AREA="backend data"; I_SIZE="L"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-12"
  I_ACS="04 05 06 07"; I_DEPS="002/1 O-4"
  I_GATES="make check, make test-props"
  I_LOCK="\`data/mock/offers.timocom.json\`, \`data/mock/offers.enrichment.json\`"
  I_BRANCH="feat/FEAT-002-offers-generator"; I_REQS="REQ-003"; I_ADRS="0003 0014"; I_SCOPE_TAG="freight"
  txt T_GOAL <<'EOF'
A deterministic generator of 150 synthetic van offers shaped like TIMOCOM Freight Exchange API v3.0.6 search results, with a separate enrichment file for everything TIMOCOM does not model and with the difficulty categories that make the demo and the tests meaningful.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-002-demo-data-generators.md` §4.3 FR-7 … FR-15, §6.3 (rates), §6.4 (difficulty categories and minimum counts), §8 (edge cases), §11 OQ-002-02, OQ-002-03, OQ-002-05
- `docs/report.md` §5.1 (TIMOCOM fields T17, T18, T29), §17.3 (corridors), §17.4 (rates)
- `context.md` → TIMOCOM Adapter Rules 1, 10; Core Domain Rule 16
EOF
  txt T_SCOPE <<'EOF'
- `generate_offers(seed, reference_date, count=150) -> (raw_payload, enrichment)`; files `data/mock/offers.timocom.json` (`{ "meta": {"requestId", "responseTimestamp"}, "payload": [...] }`) and `data/mock/offers.enrichment.json` (keyed by offer id); byte-identical for the same inputs (FR-7).
- Raw offers use only the TIMOCOM 3.0.6 fields listed in FR-8; no contact person; pallets, pallet type, service time and tags go to the enrichment file with provenance `generated_mock`.
- `id = "MOCK-" + 6 digits`, `vehicleProperties.type = ["VEHICLE_UP_TO_3_5_T"]`, two loading places (`LOADING`, `UNLOADING`), currency `EUR` (FR-9).
- Geography (FR-10): Poland at one or both ends, about 45 % domestic, corridors of report §17.3, origin ≠ destination.
- Load (FR-11), time windows on working days within 7 days (FR-12), price formula with seeded log-normal noise σ = 0.15, `min_fare = 120`, rates of §6.3 (FR-13).
- Difficulty tags with at least the counts of §6.4, listed per offer in the enrichment file (FR-14); tolerance cases `HH:MM:SSZ`, the key `"creationDateTime "`, `distance_km` > 200 (FR-15).
- Body and equipment enumeration values copied from the official OpenAPI (O-4, OQ-002-02).
- CLI entry point next to the fleet generator; commit the outputs for seed 20261109 and reference date 2026-11-16.
EOF
  txt T_OUT <<'EOF'
- Mapping and import (002/3, 002/4); multi-stop offers (P2); any real market data — prices are generated values.
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/integrations/mock/offers_generator.py` (*suggested* location; it produces provider-shaped raw data) — new
- `data/mock/offers.timocom.json`, `data/mock/offers.enrichment.json` — new (generated, committed)
- `apps/api/tests/unit/freight/test_offers_generator.py`, `apps/api/tests/props/test_offers_generator.py` — new
EOF
  txt T_IFACE <<'EOF'
```python
def generate_offers(seed: int, reference_date: date, count: int = 150) -> tuple[dict, dict]: ...   # (raw_payload, enrichment)
```
Enrichment entry per offer id (*suggested* shape): `{ "palletCount", "palletType", "serviceMinutes"?, "tags": [...], "lane": {...}, "noise": <decimal string>, "provenance": "generated_mock" }` — it must contain what AC-07 needs to recompute the price.
EOF
  txt T_TESTS <<'EOF'
- `tests/unit/freight/test_offers_generator.py` — two runs byte-identical and equal to the committed files; exactly 150 offers with unique `^MOCK-\d{6}$` ids → AC-04; tag counts ≥ §6.4 and each tagged offer really has the property (e.g. `NO_PRICE` ⇒ no `price`) → AC-06; untagged offers: `price.amount` integer ≥ 120 and equal to `max(120, round(rate × distance × noise))` from the enrichment → AC-07.
- `tests/props/test_offers_generator.py` — any seed: two loading places in different cities of `cities.json` with Poland at one end, type `VEHICLE_UP_TO_3_5_T`, 1–10 pallets, 40–1 100 kg, working-day loading within 7 days, `windowStart ≤ windowEnd`, domestic share 35–55 %. → AC-05
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run python -m routepilot.integrations.mock.offers_generator --seed 20261109 --reference-date 2026-11-16 --out-dir ../../data/mock
git diff --exit-code ../../data/mock/offers.*.json
uv run pytest tests/unit/freight/test_offers_generator.py tests/props/test_offers_generator.py -q
```
EOF
  txt T_TIPS <<'EOF'
- Generate tagged offers deliberately first (to guarantee the minimum counts), then fill the rest randomly — and record every tag in the enrichment file.
- `TOO_HEAVY_ALL` needs a mass above 1 085 kg while AC-05 bounds every offer to 40–1 100 kg, so these offers must weigh 1 086–1 100 kg. Generate them in that band.
- `PROMPT_INJECTION` remarks are fictional instruction-like text (exactly 3); they must not contain real names, links or code.
- Distances for prices use haversine × 1.25 (the golden formula); rounding of the price to whole euros is half-up.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-002-02 (accepted): body/equipment enumeration values come from the official OpenAPI (owner action O-4); `customer` is omitted.
- OQ-002-03 (accepted): PL→AT/NL/BE/DK 0.68 €/km and PL→IT 0.60 €/km, labelled `assumption`.
- OQ-002-05 (accepted): the minimum counts of §6.4.
EOF
}
register s_002_2

s_002_3() {
  I_ID="002/3"; I_FEAT="002"; I_TITLE="TIMOCOM v3 subset schemas and tolerant TimocomV3Mapper with official fixtures"
  I_AREA="backend data"; I_SIZE="L"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-12"
  I_ACS="09 10 11 12 19"; I_DEPS="002/1 O-4"
  I_GATES="make check, uv run pytest tests/contract"
  I_LOCK="🔒 fixtures copied from the official OpenAPI file (\`apps/api/tests/fixtures/timocom/\`)"; I_APPROVAL="yes"
  I_BRANCH="feat/FEAT-002-timocom-mapper"; I_REQS="REQ-001"; I_ADRS="0003 0010 0014"; I_SCOPE_TAG="integrations"
  txt T_GOAL <<'EOF'
One mapper turns TIMOCOM v3 raw offers — real or mock — into the internal offer model with provenance for every field, tolerates the format quirks the official OpenAPI itself shows, handles missing data honestly and flags instruction-like text.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-002-demo-data-generators.md` §4.4 FR-16 … FR-21, §6.5 (mapping table — binding), §6.8 (value objects), §8 (edge cases), §10 (test plan rows 09–12, 19)
- `context.md` → TIMOCOM Adapter Rules 1–4, 9–11; External Integration Contracts (`OfferMapper`); Core Domain Rules 3–5
- `docs/report.md` §16.0a (mapping), §5.1 (T29 tolerance cases)
EOF
  txt T_SCOPE <<'EOF'
- `integrations/timocom/schemas.py`: Pydantic models for the subset of OpenAPI 3.0.6 used here, with a comment naming the version and the source URL; unknown extra fields are ignored (provider data) (FR-16).
- `TimocomV3Mapper.to_domain(record) -> NormalizedOffer | MappingFailure` applying §6.5 with `field_provenance` for every mapped field (FR-17).
- Tolerant parsing (FR-18): `startTime`/`endTime` as `HH:MM` and `HH:MM:SSZ` (`Z` ignored, local time, provenance `inferred`), `distance_km` > 200, `creationDateTime` also from `"creationDateTime "`; flags `TIME_FORMAT_TOLERATED`, `KEY_WHITESPACE_TOLERATED`.
- Missing data (FR-19): no price → `revenue = null` + `missing_fields`; no coordinates → geocode from `cities.json` (`derived`) or `MISSING_COORDINATES`; no times → 00:00–23:59 local + `TIME_WINDOW_DAY_ONLY`; pallets from enrichment, else `ceil(length_m × 2.4)` (`derived`, `PALLETS_DERIVED`), else `MISSING_CAPACITY_DATA`; `service_minutes = 30` (`default`, `SERVICE_TIME_DEFAULTED`).
- Failures (FR-20): fewer than two loading places, wrong first/last type, unparsable dates, non-numeric weight → `MappingFailure(code, detail)`.
- Deterministic `SUSPICIOUS_TEXT` detector on `publicRemark`/`freightDescription` (FR-21) — a helper, not a security boundary.
- Fixtures in `apps/api/tests/fixtures/timocom/` from the official OpenAPI examples, each with a source annotation.
EOF
  txt T_OUT <<'EOF'
- A network client for TIMOCOM (`TimocomFreightProvider` stays a skeleton without HTTP; post-MVP); the `RepeatIntervalLimiter` beyond a stub; import into the database (002/4).
- Persisting lookup results or contact data (TIMOCOM rule 8).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/integrations/ports.py` (`FreightProvider`, `OfferMapper`, value objects) — new
- `apps/api/src/routepilot/integrations/timocom/{schemas.py,mapper.py,suspicious.py}` — new
- `apps/api/src/routepilot/freight/domain/normalized.py` (*suggested*: `NormalizedOffer` target model owned by `freight`) — new
- `apps/api/tests/contract/test_timocom_mapper.py`, `apps/api/tests/fixtures/timocom/*.json` — new
EOF
  txt T_IFACE <<'EOF'
```python
class OfferMapper(Protocol):                     # integrations/ports.py
    source: str
    def to_domain(self, record: RawOfferRecord) -> NormalizedOffer | MappingFailure: ...

@dataclass(frozen=True)
class RawOfferRecord:  source: str; source_offer_id: str; payload: dict; fetched_at: datetime
@dataclass(frozen=True)
class MappingFailure:  code: str; detail: str
```
Mapping: exactly the table of FEAT-002 §6.5 (for example `weight_kg = round_half_up(weight_t × 1000)`, `revenue_amount_minor = price.amount × 100`).
EOF
  txt T_TESTS <<'EOF'
- `tests/contract/test_timocom_mapper.py` — the official example maps to a `NormalizedOffer` following §6.5 with provenance for every field → AC-09; `08:15:22Z`, `"creationDateTime "` and `distance_km = 4711` map with the right flags and the window starts 08:15 local → AC-10; missing price / coordinates (known and unknown city) / times / pallets with `length_m = 1.7` → AC-11; Germany 08:00 on 2026-11-17 → `2026-11-17T07:00Z`, `Europe/Berlin`, `inferred`; one loading place → `MappingFailure` → AC-12; the three `PROMPT_INJECTION` remarks get `SUSPICIOUS_TEXT` and stay unchanged in `public_remark`, an ordinary remark does not → AC-19.
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/contract/test_timocom_mapper.py -q && make check
```
EOF
  txt T_TIPS <<'EOF'
- Every fixture file carries a source note (URL, version 3.0.6, access date). Do not attribute to TIMOCOM any field outside the OpenAPI.
- A duplicate offer id inside one payload is a `MappingFailure` (`DUPLICATE_IN_BATCH`, §8) — that check belongs to the batch logic of 002/4 but the code is defined here.
- `weight_t = 0` → 0 kg with `ZERO_WEIGHT`; a non-EUR currency is stored as is (the cost model converts it).
- `NormalizedOffer` belongs to `freight`; `integrations` may import `freight`'s target model but not the reverse (Module Boundaries).
EOF
}
register s_002_3

s_002_4() {
  I_ID="002/4"; I_FEAT="002"; I_TITLE="MockFreightProvider and idempotent import with batches"
  I_AREA="backend data"; I_SIZE="M"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-12"
  I_ACS="13 14 18 20"; I_DEPS="002/2 002/3 001/6"
  I_GATES="make check, make test-db"
  I_LOCK="—"
  I_BRANCH="feat/FEAT-002-import"; I_REQS="REQ-002, REQ-003"; I_ADRS="0003"; I_SCOPE_TAG="freight"
  txt T_GOAL <<'EOF'
Generated offers enter the database exactly like a real provider's would: through `MockFreightProvider`, the shared mapper and an idempotent import that records raw payloads, counts what happened and never duplicates an offer.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-002-demo-data-generators.md` §4.5 FR-22, FR-23, FR-24, §6.8 (ports and value objects), §8 (duplicate in batch), §10 (rows 13, 14, 18, 20)
- `context.md` → External Integration Contracts (`FreightProvider`), TIMOCOM Adapter Rules 5–8, 10–11
EOF
  txt T_SCOPE <<'EOF'
- `MockFreightProvider` (`name = "mock_timocom_v3"`): `search(query)` yields `RawOfferRecord`s from the committed payload filtered by the query (vehicle type, origin area, dates, weight); `lookup` returns `[]`; no network access (FR-22).
- `ImportService.run(provider, query) -> ImportBatch` (FR-23): `payload_sha256` per raw record; same `(source, source_offer_id, payload_sha256)` → `unchanged`; same offer with another hash → new raw record, offer updated (`version + 1`) → `updated`; new → `imported`; mapping failure → `failed`, no offer; batch row with counts and status.
- Imported offers: `source = "mock_timocom_v3"`, `is_synthetic = true`, `status = open`, `retention_until` = latest loading date + 1 day (FR-24).
EOF
  txt T_OUT <<'EOF'
- The first-start seed and the admin endpoints (002/5); a real TIMOCOM client (post-MVP).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/integrations/mock/provider.py` — new
- `apps/api/src/routepilot/freight/service/import_service.py`, `apps/api/src/routepilot/freight/repository/**` (batches, raw records) — new or changed
- `apps/api/tests/db/test_import.py`, `apps/api/tests/unit/integrations/test_mock_provider.py`, `apps/api/tests/conftest.py` (socket-blocking fixture) — new or changed
EOF
  txt T_IFACE <<'EOF'
```python
class FreightProvider(Protocol):           # integrations/ports.py
    name: str
    def capabilities(self) -> ProviderCapabilities: ...
    def search(self, query: FreightSearchQuery) -> Iterator[RawOfferRecord]: ...
    def lookup(self, source_offer_ids: list[str]) -> list[RawOfferRecord]: ...

@dataclass(frozen=True)
class FreightSearchQuery:
    vehicle_type: str; origin: GeoPoint | None = None; destination: GeoPoint | None = None
    radius_km: int | None = None; loading_from: date | None = None; loading_to: date | None = None
    max_weight_kg: int | None = None

class ImportService:
    def run(self, provider: FreightProvider, query: FreightSearchQuery) -> ImportBatch: ...
```
EOF
  txt T_TESTS <<'EOF'
- `tests/db/test_import.py` — two imports of the generated payload: first `imported = 150 − failed`, second all `unchanged`, equal row counts → AC-13; a changed price creates a second raw record, bumps revenue and `version`, counts `updated`; a failing record is `failed` and creates no offer → AC-14; every imported row is synthetic with `MOCK-` ids and `source = mock_timocom_v3`, no real-looking phone/email → AC-18.
- `tests/unit/integrations/test_mock_provider.py` — with sockets blocked, `search` yields only matching records, `lookup` returns `[]`, no socket opened. → AC-20
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/db/test_import.py tests/unit/integrations -q && make check && make test-db
```
EOF
  txt T_TIPS <<'EOF'
- Compute `payload_sha256` over a canonical JSON serialisation (sorted keys), not over the raw file bytes.
- One short transaction per batch step keeps SQLite writers short (WAL, `busy_timeout`).
- Raw search records carry `retention_until`; never persist lookup results (TIMOCOM rule 8).
EOF
}
register s_002_4

s_002_5() {
  I_ID="002/5"; I_FEAT="002"; I_TITLE="First-start seed, DEMO-DEFAULT cost profile, admin demo-data generate/reset, CLI"
  I_AREA="backend data"; I_SIZE="M"; I_DAY="2026-11-10"; I_CATCHUP="2026-11-12"
  I_ACS="15 16 17"; I_DEPS="002/4 001/5"
  I_GATES="make check, uv run pytest -m integration tests/integration/test_first_start_seed.py, make openapi"
  I_LOCK="\`Makefile\` (\`seed-fleet\`), \`contracts/openapi.json\`, \`apps/api/.env.example\` (\`MOCK_SEED\`, \`MOCK_REFERENCE_DATE\`)"
  I_BRANCH="feat/FEAT-002-seed-admin"; I_REQS="REQ-004, REQ-006, REQ-032"; I_ADRS="0007"; I_SCOPE_TAG="seed"
  txt T_GOAL <<'EOF'
A fresh clone with no API keys starts with a complete, reproducible demo world — users, the default cost profile, five drivers with vans and states, 150 offers — and an admin can regenerate or reset it from the API.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-002-demo-data-generators.md` §4.5 FR-25 … FR-28, §6.6 (`DEMO-DEFAULT` values and provenance — binding), §6.7 (admin API and what reset deletes), §6.9 (`app_meta` key), §8 (reset by `demo` → 403), §11 OQ-002-04, OQ-002-06, OQ-002-07
- `DEVELOPMENT.md` §5.4 (first-start seed), §6.1 (`MOCK_SEED`, `MOCK_REFERENCE_DATE`)
- `docs/report.md` §17.4 (cost parameters)
EOF
  txt T_SCOPE <<'EOF'
- `DEMO-DEFAULT` cost profile with exactly the §6.6 values and per-field provenance (FR-25): fuel 181, driver 1 400/h, vehicle 12/km, accommodation 5 500, per diem `{"PL": 1059}` (domestic only), tolls `{"PL": 0, "DE": 0, "FR": 12, "IT": 12}`, vignettes AT/CZ/SK/HU, `fx_rates {"PLN": "4.25"}`, thresholds 0.
- Lifespan seed after the first-start accounts (FR-26): if `app_meta["seed_version"]` is absent → profile, fleet, offers (seed `MOCK_SEED`, date `MOCK_REFERENCE_DATE` or the UTC date of first start), `seed_version` and an audit event; one transaction per step; idempotent.
- `POST /admin/demo-data/generate` (admin) re-runs the generators with `seed`, `referenceDate`, `offers` (1–500) and upserts; `drivers` ≠ 5 → `422` (FR-27).
- `POST /admin/demo-data/reset` (admin) deletes everything of §6.7 (synthetic rows, jobs, plans, assignments, agent threads and runs, approvals, explanations, routing cache, manual offers and user-created fleet rows) and seeds again; users, sessions and audit events stay. Both endpoints write audit events.
- `make seed-fleet` wraps the generator CLIs (FR-28).
EOF
  txt T_OUT <<'EOF'
- The admin screen (005/8); user administration (P1).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/fleet/service/seed.py` (*suggested*), `apps/api/src/routepilot/fleet/api/admin_demo_data.py` (*suggested*) — new
- `apps/api/src/routepilot/main.py` (lifespan step, router) — changed
- `apps/api/.env.example`, `Makefile` — changed
- `apps/api/tests/integration/test_first_start_seed.py`, `apps/api/tests/api/test_admin_demo_data.py` — new
- `contracts/openapi.json` — regenerated
EOF
  txt T_IFACE <<'EOF'
```text
POST /api/v1/admin/demo-data/generate  { seed?: int, referenceDate?: date, drivers?: 5, offers?: int (1–500, default 150) }
     -> 200 { importBatchId, drivers, vehicles, offers: {imported, updated, unchanged, failed} } | 422
POST /api/v1/admin/demo-data/reset     -> 200 (same shape)
```
`app_meta["seed_version"] = {"version": 1, "seed": …, "referenceDate": …, "at": …}`.
EOF
  txt T_TESTS <<'EOF'
- `tests/integration/test_first_start_seed.py` — empty DB, no keys: after start users, `DEMO-DEFAULT`, 5 drivers, 5 vehicles, 5 states and the offers exist and `seed_version` is set; a second start changes no row count. → AC-15
- `tests/api/test_admin_demo_data.py` — admin `generate {seed: 7}` → `200` with counts + audit; dispatcher → `403 FORBIDDEN`; `{drivers: 6}` → `422` → AC-16; reset with a manual offer, a job and an assignment present → `200`, those rows gone, users and audit kept, data equals a fresh seed → AC-17.
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && rm -f data/routepilot.db* && uv run alembic upgrade head && uv run uvicorn routepilot.main:app --port 8000
# second terminal: log in on /docs and call GET /api/v1/drivers → 5 drivers
uv run pytest -m integration tests/integration/test_first_start_seed.py tests/api/test_admin_demo_data.py -q
make check && make openapi
```
EOF
  txt T_TIPS <<'EOF'
- Rows for jobs and assignments in the reset test can be inserted directly (the tables exist since 001/1); FEAT-004 is not needed.
- Generation while an optimisation job runs is allowed — jobs work on their snapshot (§8).
- Values marked "assumption" in report §17.4 keep provenance `assumption` (Core Domain Rule 17).
EOF
  txt T_DECISIONS <<'EOF'
- OQ-002-04 (owner, 2026-11-11): no per diem on international plans; domestic `{"PL": 1059}`; toll defaults accepted as assumptions.
- OQ-002-06 (accepted): reset restores the exact first-start state, including removal of user-created data.
EOF
}
register s_002_5
