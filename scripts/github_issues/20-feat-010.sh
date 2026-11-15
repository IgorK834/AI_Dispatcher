# FEAT-010 — LTL consolidation and load metrics (P1, after the MVP). Sourced by scripts/create_github_issues.sh.
# The specification is `draft`: every slice depends on owner action O-12 and must not start before it is closed.
# shellcheck shell=bash disable=SC2034

F010_CONTEXT_COMMON='- `docs/raport.md` (LTL research: how van part loads work, the measurements of the current demo, root causes with code references)
- `specs/FEAT-010-ltl-consolidation.md` §1 – §3 (goal, why, scope) and §11 (open questions with the owner'"'"'s answers in O-12)'

o_12() {
  I_ID="O-12"; I_KIND="owner"; I_TITLE="Review and approve FEAT-010 (LTL consolidation) and its assumptions"; I_DAY="post-MVP"; I_SIZE="45 min"
  txt T_GOAL <<'EOF'
FEAT-010 moves from `draft` to `approved` (or gets change requests), so that slices 010/1 … 010/6 may start. The approval fixes the demo tariff constants, the zones and corridors, and how the replaced parts of the approved FEAT-002 and FEAT-003 are recorded.
EOF
  txt T_WHY <<'EOF'
`docs/raport.md` measured that demo plans chain single orders (A→B→C): 81 % of the offers have no consolidation partner, half of the fleet profit plans never carry more than one order at a time, and vans run at 46 % pallet fill. FEAT-010 changes the demo data and one engine rule. FEAT-002 and FEAT-003 are `approved`, so only the owner can approve a specification that replaces parts of them (`AGENTS.md` §9: specification status, golden values, new requirements).
EOF
  txt T_STEPS <<'EOF'
1. Read `docs/raport.md` §1, §5 and §6, then `specs/FEAT-010-ltl-consolidation.md`.
2. Answer the open questions in §11 (comment here): OQ-010-01 tariff constants (§6.1), OQ-010-02 zones and corridors (§6.2, §6.3), OQ-010-03 metrics computed on read (no migration), OQ-010-06 eval fixtures, OQ-010-09 matrix km for pool partners.
3. Add REQ-034 to `specs/requirements.md` (OQ-010-05) and the traceability row REQ-034 → FEAT-010 → AC-FEAT-010-01 … 14.
4. Add the changelog lines to FEAT-002 (rev. 5: FR-10, FR-11 mass, FR-13 and AC-FEAT-002-07 superseded for `offers-generator v3`) and FEAT-003 (FR-17 ranking and OQ-003-10 superseded by FEAT-010 FR-8) — OQ-010-04.
5. Set `status: approved` in the FEAT-010 front matter and add a changelog line; re-run this script so the slice issues show the new status.
EOF
  txt T_DONE <<'EOF'
- [ ] FEAT-010 has `status: approved` and a changelog line with the date.
- [ ] REQ-034 exists in `specs/requirements.md`; FEAT-002 and FEAT-003 changelogs name the superseded parts.
- [ ] The answers to OQ-010-01 … 09 are in §11 of the specification.
- [ ] `uv run python scripts/trace.py --check` is green (approved ACs without tests are expected to be reported as open slices, not hidden).
EOF
}
register o_12

s_010_1() {
  I_ID="010/1"; I_FEAT="010"; I_PRIORITY="P1"; I_TITLE="offers-generator v3, part 1: mass from pallets and the LTL tariff"
  I_AREA="backend data"; I_SIZE="M"; I_DAY="post-MVP"
  I_ACS="02 03 04 05"; I_DEPS="O-12"
  I_GATES="make check, make test-props"
  I_LOCK="\`data/mock/offers.timocom.json\`, \`data/mock/offers.enrichment.json\`"
  I_BRANCH="feat/FEAT-010-offers-ltl-tariff"; I_REQS="REQ-003, REQ-034 (proposed)"; I_ADRS="0003 0014"; I_SCOPE_TAG="freight"
  txt T_GOAL <<'EOF'
Demo offers are priced like van part loads: a consignment pays a share of a full-van price that depends on its pallets and mass, with a small-consignment premium and a minimum fare. Mass follows the pallet count. A lone 1–2 pallet order stops being profitable on its own, so the engine has a reason to consolidate.
EOF
  T_CONTEXT="$F010_CONTEXT_COMMON
- \`specs/FEAT-010-ltl-consolidation.md\` §4.1 FR-1 … FR-3, FR-5, FR-6, §6.1 (tariff constants), §8 (missing pallets, share above 1)
- \`specs/FEAT-002-demo-data-generators.md\` FR-7 … FR-15, §6.3 (lane rates, unchanged), §6.4 (tags and minimum counts, unchanged)
- \`context.md\` → Core Domain Rule 16 (synthetic data), Coding Standards (money as int minor units in the domain)
"
  txt T_SCOPE <<'EOF'
- `generatorVersion = "offers-generator v3"` in the enrichment file (FR-1); signature and purity of `generate_offers` unchanged.
- Pallet-count weights (26, 24, 18, 12, 7, 5, 3, 2, 2, 1); mass of untagged offers `min(1085, max(40, round(eq × u)))` with `u ~ U(50, 200)` (FR-3); tag mass overrides unchanged.
- LTL tariff (FR-6): `share = min(1, max(eq / 10, kg / 1000))`, `premium = 1 + 0.6 × (1 − share)`, `price = max(60, round(rate × distance_km × share × premium × noise))`, half-up; `NO_PALLETS` offers priced from `ceil(length_m × 2.4)`; `UNPROFITABLE_DETOUR` override with the new minimum fare.
- Enrichment `billableShare`, `ltlPremium` and the extended `price_formula` (FR-5); constants as named module constants with provenance `assumption`.
- Tag index ranges unchanged (FR-2): the same `MOCK-…` ids carry the same tags.
- Regenerate and commit the two offer files for seed 20261109 / 2026-11-16.
EOF
  txt T_OUT <<'EOF'
- Consignment groups, zones, corridors and the partner metric (010/2) — lanes stay as in v2 in this slice.
- Any engine, API or UI change; `cities.json`, `fleet.json`, `routing-matrix.json`.
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/freight/generator.py` — change
- `data/mock/offers.timocom.json`, `data/mock/offers.enrichment.json` — regenerated, committed
- `apps/api/tests/unit/freight/test_offers_generator.py`, `apps/api/tests/props/test_offers_generator.py` — change (replace the AC-FEAT-002-07 price check by AC-FEAT-010-04 once FEAT-002 rev. 5 withdraws it)
EOF
  txt T_IFACE <<'EOF'
```python
def ltl_price(rate: float, distance_km: float, eq: Decimal, weight_kg: int, noise: float) -> int: ...  # suggested, pure
LTL_REF_EP = 10; LTL_REF_KG = 1000; LTL_PREMIUM_MAX = 0.6; LTL_MIN_FARE = 60   # assumption
KG_PER_EP_RANGE = (50, 200)                                                   # assumption
```
EOF
  txt T_TESTS <<'EOF'
- `tests/unit/freight/test_offers_generator.py` — tags on the same ids as the FEAT-002 index ranges, minimum counts met → AC-02; recompute every priced offer from its enrichment → AC-04; the four tariff examples (60, 185, 340, 340 €) → AC-05.
- `tests/props/test_offers_generator.py` — FEAT-002 AC-05 bounds still hold for any seed; untagged mass within the FR-3 band → AC-03.
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run python -m routepilot.freight.generator --seed 20261109 --reference-date 2026-11-16 --out ../../data/mock/offers.timocom.json --enrichment-out ../../data/mock/offers.enrichment.json
uv run pytest tests/unit/freight/test_offers_generator.py tests/props/test_offers_generator.py -q
make check && make test-props
```
EOF
  txt T_TIPS <<'EOF'
- Keep the order of random draws stable for the tagged offers so their ids and tags do not move (AC-02); draw new values (pallet weights, kg per EP) from the same seeded `random.Random`, never the global module.
- Round only once, at the end (half-up to whole euros); keep the intermediate values in the enrichment file so AC-04 can recompute them.
- Expect agent fixtures and evals that name `MOCK-…` ids to change behaviour (OQ-010-06): run `make test-agents` and list every changed scenario in the completion report.
- Fleet profit in the benchmark may fall — that is the intended effect (single small orders stop paying); do not tune constants to keep old numbers.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-010-01 (tariff constants) and OQ-010-04 (how FEAT-002 records the superseded parts) — take the owner's answers from O-12.
EOF
}
register s_010_1

s_010_2() {
  I_ID="010/2"; I_FEAT="010"; I_PRIORITY="P1"; I_TITLE="offers-generator v3, part 2: consignment groups along corridors and the partner metric"
  I_AREA="backend data"; I_SIZE="L"; I_DAY="post-MVP"
  I_ACS="01 06 07"; I_DEPS="010/1"
  I_GATES="make check, make test-props, make test-agents"
  I_LOCK="\`data/mock/offers.timocom.json\`, \`data/mock/offers.enrichment.json\`"
  I_BRANCH="feat/FEAT-010-offer-groups"; I_REQS="REQ-003, REQ-034 (proposed)"; I_ADRS="0003"; I_SCOPE_TAG="freight"
  txt T_GOAL <<'EOF'
Offers come in small groups that start in one area on the same day and go the same way, along weighted corridors between zones of the existing 39 cities. At least half of the committed offers have a consolidation partner (today 18.6 %), so the engine can actually fill a van.
EOF
  T_CONTEXT="$F010_CONTEXT_COMMON
- \`specs/FEAT-010-ltl-consolidation.md\` §4.1 FR-1, FR-2, FR-4, FR-5, §4.2 FR-7, §6.2 (zones), §6.3 (corridors), §8 (one-city zones, offers without coordinates)
- \`specs/FEAT-002-demo-data-generators.md\` FR-10 … FR-12, AC-05 (bounds that still hold), §6.4
- \`docs/report.md\` §17.3 (corridors)
"
  txt T_SCOPE <<'EOF'
- Zone table (§6.2) and corridor table with weights (§6.3) as constants; every city of `cities.json` in exactly one zone (checked by a test).
- Group generation (FR-4): corridor by weight, one working-day loading date, size 1–4 (35/30/20/15), anchor city with probability 0.6, windows overlapping by ≥ 1 h; tagged offers keep their FR-2 lanes (`MUTUALLY_EXCLUSIVE` pairs = one group of two).
- Enrichment `groupId`, `zoneFrom`, `zoneTo` (FR-5).
- `consolidation_partners(offers, pickup_km=80, delivery_km=150)` and the partner share (FR-7), pure.
- Regenerate and commit the final v3 offer files; check that the domestic share stays 35–55 %.
- Run the agent tests and the eval fixtures that name `MOCK-…` ids; record any changed behaviour (OQ-010-06).
EOF
  txt T_OUT <<'EOF'
- New cities or satellite towns (OQ-010-07); any change to `cities.json` or `routing-matrix.json`.
- Engine, API and UI changes (010/3 … 010/5).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/freight/generator.py` — change
- `apps/api/src/routepilot/freight/consolidation.py` (*suggested*: zones, corridors, `consolidation_partners`) — new
- `data/mock/offers.timocom.json`, `data/mock/offers.enrichment.json` — regenerated, committed
- `apps/api/tests/unit/freight/test_offers_generator.py`, `apps/api/tests/props/test_offers_generator.py` — change
- `apps/api/tests/unit/freight/test_consolidation_partners.py` (*suggested*) — new
- Agent test fixtures and `evals/**` only if a referenced offer changed — list each one in the PR
EOF
  txt T_IFACE <<'EOF'
```python
ZONES: dict[str, tuple[str, ...]]                 # zone id -> city names of cities.json
CORRIDORS: tuple[tuple[str, str, int], ...]       # (origin zone, destination zone, weight), total 100
def consolidation_partners(offers, pickup_km: float = 80, delivery_km: float = 150) -> dict[str, list[str]]: ...
def partner_share(offers, **radii) -> Decimal: ...
```
EOF
  txt T_TESTS <<'EOF'
- `tests/unit/freight/test_offers_generator.py` — two runs byte-identical and equal to the committed files, `generatorVersion` v3, 150 unique ids → AC-01.
- `tests/props/test_offers_generator.py` — every offer has a `groupId`; group sizes, shared loading date, zones of one corridor, windows overlapping ≥ 1 h → AC-06.
- `tests/unit/freight/test_consolidation_partners.py` — the 3-offer fixture (A↔B partners, C none) and partner share ≥ 0.50 on the committed offers → AC-07.
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run python -m routepilot.freight.generator --seed 20261109 --reference-date 2026-11-16 --out ../../data/mock/offers.timocom.json --enrichment-out ../../data/mock/offers.enrichment.json
git diff --stat ../../data/mock/
uv run pytest tests/unit/freight tests/props/test_offers_generator.py -q
make check && make test-props && make test-agents
```
EOF
  txt T_TIPS <<'EOF'
- Generate the FR-2 tagged offers first (fixed indices), then fill the remaining indices group by group; never let a group overwrite a tagged index.
- Window overlap: draw one group start hour and offset each member by at most 1 h; whole-day windows overlap everything.
- `make seed-fleet` regenerates the committed files byte for byte; keep it working (it is covered by `tests/unit/test_seed_fleet_target.py`).
EOF
  txt T_DECISIONS <<'EOF'
- OQ-010-02 (zones and corridor weights) and OQ-010-06 (eval fixtures) — take the owner's answers from O-12.
EOF
}
register s_010_2

s_010_3() {
  I_ID="010/3"; I_FEAT="010"; I_PRIORITY="P1"; I_TITLE="Engine: partner-aware pool cut"
  I_AREA="engine"; I_SIZE="M"; I_DAY="post-MVP"
  I_ACS="08 09"; I_DEPS="O-12"
  I_GATES="make check, make test-props"
  I_BRANCH="feat/FEAT-010-pool-partners"; I_REQS="REQ-009, NFR-002"; I_ADRS="0004"; I_SCOPE_TAG="engine"
  txt T_GOAL <<'EOF'
When more offers pass the prefilter than fit in the pool, the engine keeps the offers that are cheap to carry together with the best offers instead of cutting them. Half of the pool goes by revenue per km as today, then partners of the kept offers, then the rest.
EOF
  T_CONTEXT="$F010_CONTEXT_COMMON
- \`specs/FEAT-010-ltl-consolidation.md\` §4.3 FR-8, FR-9, §8 (ties, offers without coordinates)
- \`specs/FEAT-003-optimizer-and-working-time.md\` FR-17 (current ranking, superseded), OQ-003-10, FR-25 (determinism), the default parameters
- \`context.md\` → Optimization Engine Invariants
"
  txt T_SCOPE <<'EOF'
- `offer_pool` (FR-8): unchanged when ≤ `max_pool_per_driver` offers pass; otherwise phase 1 = `⌈max/2⌉` best ratio (ties by id), phase 2 = best-ratio pool partners of kept offers (pickup ≤ `pool_partner_pickup_km` and delivery ≤ `pool_partner_delivery_km`, matrix km), phase 3 = fill by ratio; `pool_truncated = true`; returned pool sorted by id.
- `EngineParams.pool_partner_pickup_km = 80`, `pool_partner_delivery_km = 150` (FR-9), `> 0`.
EOF
  txt T_OUT <<'EOF'
- Search, objectives, validators, baselines, fleet assignment; plan metrics (010/4); generator changes (010/1, 010/2).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/prefilter.py` — change
- `apps/api/src/routepilot/optimization/engine/models.py` — `EngineParams` fields only
- `apps/api/tests/unit/optimization/test_prefilter.py` — change; `apps/api/tests/unit/optimization/factories.py` — helpers if needed
- `apps/api/tests/props/test_pool_partners.py` (*suggested*) — new
EOF
  txt T_IFACE <<'EOF'
```python
def offer_pool(snapshot: EngineSnapshot, driver: DriverSnapshot) -> tuple[list[OfferSnapshot], dict[str, str], bool]: ...  # signature unchanged
class EngineParams:
    pool_partner_pickup_km: Decimal = Field(default=Decimal("80"), gt=0)      # assumption
    pool_partner_delivery_km: Decimal = Field(default=Decimal("150"), gt=0)   # assumption
```
EOF
  txt T_TESTS <<'EOF'
- `tests/unit/optimization/test_prefilter.py` — 70 passing offers, the 61st-best offer P is a pool partner of the best one → P kept, pool of 60, the 30 best kept → AC-08.
- `tests/props/test_pool_partners.py` — determinism; equality with the FR-17 pool when not truncated; size and phase-1 content when truncated → AC-09.
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/unit/optimization/test_prefilter.py tests/props/test_pool_partners.py -q
make check && make test-props
cd ../.. && make bench   # optional: p95 must stay within NFR-002; report the numbers
```
EOF
  txt T_TIPS <<'EOF'
- Use `snapshot.matrix.leg(a, b)` distances (OQ-010-09), the same numbers the search uses; offers without coordinates never reach the pool.
- Phase 2 is a loop over kept offers × candidates (≤ 150 × 150) — no index structure needed.
- Keep the rejection codes and order of FEAT-003 FR-15 … FR-19 untouched.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-010-09 (matrix km vs haversine) and OQ-010-04 (FEAT-003 changelog) — take the owner's answers from O-12.
EOF
}
register s_010_3

s_010_4() {
  I_ID="010/4"; I_FEAT="010"; I_PRIORITY="P1"; I_TITLE="Plan load metrics in the engine and the plan API"
  I_AREA="engine backend"; I_SIZE="M"; I_DAY="post-MVP"
  I_ACS="10 11"; I_DEPS="010/3"
  I_GATES="make check, make test-props, make openapi"
  I_LOCK="\`contracts/openapi.json\`, \`apps/web/src/lib/api/schema.d.ts\` (generated)"
  I_BRANCH="feat/FEAT-010-plan-load-metrics"; I_REQS="REQ-009, REQ-034 (proposed)"; I_ADRS=""; I_SCOPE_TAG="optimization"
  txt T_GOAL <<'EOF'
Every plan says how full the van was: the km-weighted share of pallet places and of payload used, and the highest number of orders on board at once — in the engine result, the job result and `GET /route-plans/{id}`, without a migration.
EOF
  T_CONTEXT="$F010_CONTEXT_COMMON
- \`specs/FEAT-010-ltl-consolidation.md\` §4.4 FR-10, FR-11, §6 (API), §8 (zero km, old stored plans)
- \`specs/FEAT-004-routing-and-jobs.md\` PlanSummary / RoutePlan shapes, \`route_stops\` columns
- \`DEVELOPMENT.md\` §4 (API rules, problem+json)
"
  txt T_SCOPE <<'EOF'
- Engine `RoutePlan`: `load_factor_ep`, `load_factor_kg` (Decimal 0 … 1, 4 places, half-up; 0 when no km) and `max_orders_on_board` (FR-10), computed from legs, actions and the vehicle; no effect on ranks, objectives or validators.
- API `PlanSummary` and `RoutePlan`: `loadFactorEp`, `loadFactorKg` (decimal strings) and `maxOrdersOnBoard` (integer), computed on read from `route_stops` (`leg_m`, `load_*_after`, `kind`) and the vehicle limits (FR-11, OQ-010-03).
- Regenerate `contracts/openapi.json` and the web `schema.d.ts`; additive change only.
EOF
  txt T_OUT <<'EOF'
- A migration or new columns; UI (010/5); agent tool facts (OQ-010-08).
EOF
  txt T_FILES <<'EOF'
- `apps/api/src/routepilot/optimization/engine/models.py` (`RoutePlan` fields), `apps/api/src/routepilot/optimization/engine/plan_metrics.py` (*suggested*, pure) — new/change
- `apps/api/src/routepilot/optimization/engine/schedule.py` — fill the fields when a plan is finished
- `apps/api/src/routepilot/optimization/jobs/domain/__init__.py` (`PlanSummary`), `apps/api/src/routepilot/optimization/jobs/results.py` / `jobs/service/__init__.py` — read-model computation
- `contracts/openapi.json`, `apps/web/src/lib/api/schema.d.ts` — regenerated
- `apps/api/tests/unit/optimization/test_plan_metrics.py` (*suggested*), `apps/api/tests/api/test_route_plans.py` — new/change
EOF
  txt T_IFACE <<'EOF'
```python
def load_metrics(legs: list[PlanLeg], actions: list[Action], vehicle: VehicleSnapshot) -> tuple[Decimal, Decimal, int]: ...  # suggested, pure
```
JSON: `"loadFactorEp": "0.5333", "loadFactorKg": "0.5500", "maxOrdersOnBoard": 2`.
EOF
  txt T_TESTS <<'EOF'
- `tests/unit/optimization/test_plan_metrics.py` — the three-leg example (0.5333, 0.5500, 2) and the zero-km plan → AC-10.
- `tests/api/test_route_plans.py` — a finished job: fields present in the job result and the plan detail and equal to the engine values; OpenAPI declares them; no breaking change → AC-11.
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/unit/optimization/test_plan_metrics.py tests/api/test_route_plans.py -q
make openapi && git diff --stat contracts/openapi.json
make check && make test-props
```
EOF
  txt T_TIPS <<'EOF'
- Leg `i` of a stored plan ends at stop `i`; its load is the load *after* stop `i − 1` (the first leg starts empty unless the plan says otherwise) — test this with the GOLD-001 fixture.
- Decimal strings like `marginPct`; never floats.
EOF
  txt T_DECISIONS <<'EOF'
- OQ-010-03 (computed on read, no migration) — take the owner's answer from O-12; a migration would need its own review (🔒).
EOF
}
register s_010_4

s_010_5() {
  I_ID="010/5"; I_FEAT="010"; I_PRIORITY="P1"; I_TITLE="Plan UI: van fill and orders on board, part-empty hint"
  I_AREA="frontend"; I_SIZE="S"; I_DAY="post-MVP"
  I_ACS="12"; I_DEPS="010/4"
  I_GATES="make check (ESLint, Prettier, tsc --noEmit, Vitest), pnpm --filter web build"
  I_LOCK="\`apps/web/messages/*.json\`"
  I_BRANCH="feat/FEAT-010-plan-fill-ui"; I_REQS="REQ-009, REQ-021"; I_ADRS="0015"; I_SCOPE_TAG="web"
  txt T_GOAL <<'EOF'
The dispatcher sees at a glance how full the van runs on every variant: "Van fill: 46 % of pallet places · 40 % of payload" and "Orders on board: up to 2", with a neutral hint when a plan is only a chain of single orders.
EOF
  T_CONTEXT="$F010_CONTEXT_COMMON
- \`specs/FEAT-010-ltl-consolidation.md\` §4.4 FR-12
- \`specs/FEAT-005-frontend.md\` FR-14, FR-15 (variant cards, plan detail), design-system rules
- \`docs/design/README.md\` (tokens, status levels: grey text, red is the only accent)
"
  txt T_SCOPE <<'EOF'
- Variant cards and the plan header show both fill values (locale-formatted percent) and the maximum orders on board.
- Neutral hint when `maxOrdersOnBoard = 1` and both factors are below 0.5.
- EN and PL texts in `messages/en.json` and `messages/pl.json` (same keys, appended).
EOF
  txt T_OUT <<'EOF'
- Changes to the occupancy chart or the top-view load plan; new colours or accents; any API change.
EOF
  txt T_FILES <<'EOF'
- `apps/web/src/features/plans/variants.tsx`, `apps/web/src/features/plans/plan-screen.tsx` (header), `apps/web/src/features/plans/format.ts` — change
- `apps/web/messages/en.json`, `apps/web/messages/pl.json` — append keys
- `apps/web/src/features/plans/variants.test.tsx`, `apps/web/src/test/fixtures/` (a chain-plan fixture) — change/new
EOF
  T_IFACE=""
  txt T_TESTS <<'EOF'
- `variants.test.tsx` — `[AC-FEAT-010-12]` GOLD-001 fixture and a chain fixture, rendered in EN and PL: fill texts, orders on board, hint only for the chain → AC-12.
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/web && pnpm test -- variants && pnpm --filter web build
make check
```
EOF
  txt T_TIPS <<'EOF'
- Percent through `lib/format` with the active locale (`46 %` in PL, `46%` in EN).
- The hint is text, not colour — grey per the design system.
EOF
  T_DECISIONS=""
}
register s_010_5

s_010_6() {
  I_ID="010/6"; I_FEAT="010"; I_PRIORITY="P1"; I_TITLE="GOLD-011 consolidation golden case and consolidation KPIs in the benchmark"
  I_AREA="engine infra"; I_SIZE="M"; I_DAY="post-MVP"
  I_ACS="13 14"; I_DEPS="010/2 010/4"
  I_GATES="make check, uv run pytest tests/golden, make bench (manual), scripts/benchmark_report.py"
  I_LOCK="🔒 \`specs/golden/GOLD-011.md\` (golden values), \`docs/metrics.md\`"
  I_APPROVAL="yes"
  I_BRANCH="test/FEAT-010-gold-011-bench"; I_REQS="REQ-009, NFR-002"; I_ADRS=""; I_SCOPE_TAG="engine"
  txt T_GOAL <<'EOF'
A hand-checked golden case proves that the engine prefers a consolidated trip over a chain of single orders under the LTL tariff, and the benchmark report shows the van fill and the share of consolidated plans over the 20 fixed seeds, before and after FEAT-010.
EOF
  T_CONTEXT="$F010_CONTEXT_COMMON
- \`specs/FEAT-010-ltl-consolidation.md\` §4.5 FR-13, FR-14, §5 (targets A–C)
- \`specs/golden/README.md\` (golden rules), \`specs/golden/GOLD-001.md\` (format with shown arithmetic)
- \`bench/README.md\`, \`specs/FEAT-007-quality-readme-ci-full.md\` (benchmark report)
"
  txt T_SCOPE <<'EOF'
- `specs/golden/GOLD-011.md`: inputs (driver in Katowice, 10 EP / 1 085 kg van, the consolidated set and the chain set with FR-6 prices) and every expected value with shown arithmetic — **written first and approved by the owner before the test is written**.
- `tests/golden/test_gold_011.py` (+ the case in `tests/golden/cases.py`).
- `bench/fleet_5x60.py`: `consolidation` block per run and in the summary (FR-14); `scripts/benchmark_report.py`: "Consolidation" table in `docs/metrics.md`, targets recorded as met / not met.
EOF
  txt T_OUT <<'EOF'
- Changing any existing golden file or value; asserting the benchmark targets in CI.
EOF
  txt T_FILES <<'EOF'
- `specs/golden/GOLD-011.md` — new (🔒 owner approval of the values); `specs/golden/README.md` — one table row
- `apps/api/tests/golden/test_gold_011.py`, `apps/api/tests/golden/cases.py` — new/change
- `bench/fleet_5x60.py`, `scripts/benchmark_report.py`, `scripts/tests/test_benchmark_report.py`, `docs/metrics.md` — change
EOF
  T_IFACE=""
  txt T_TESTS <<'EOF'
- `tests/golden/test_gold_011.py` — top profit plan = the consolidated set; `max_orders_on_board`, `load_factor_ep`, revenue, costs, net profit equal GOLD-011 → AC-13.
- `scripts/tests/test_benchmark_report.py` — a benchmark JSON fixture with the `consolidation` block renders the table and the target line → AC-14.
EOF
  txt T_VERIFY <<'EOF'
```bash
cd apps/api && uv run pytest tests/golden -q
cd ../.. && make bench && uv run --project apps/api python scripts/benchmark_report.py
git diff docs/metrics.md
```
EOF
  txt T_TIPS <<'EOF'
- A golden mismatch means stop and report — never edit the golden file or the expected value to make the test pass.
- Report the consolidation numbers before (`docs/raport.md` §6.2: 46 % / 40 % fill, 7 of 14 plans single-order) and after in the completion report.
EOF
  T_DECISIONS=""
}
register s_010_6
