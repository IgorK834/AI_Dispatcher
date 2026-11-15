---
id: FEAT-010
title: LTL consolidation — realistic demo offers, partner-aware pool and load metrics
status: approved
owner: project owner
requirements: [REQ-003, REQ-009, REQ-034]
adrs: [ADR-0003, ADR-0014]
modules: [freight (generator), optimization.engine (prefilter, models), optimization.jobs (plan read model), web features/plans, bench, specs/golden]
revision: 4
---

# FEAT-010: LTL consolidation — realistic demo offers, partner-aware pool and load metrics

> **Approved by the owner on 2026-11-15 (revision 2 under backlog owner action O-12; revision 3 and the GOLD-011 values later the same day).** P1 (after the MVP).
> Research and measurements behind this specification: [`docs/raport.md`](../docs/raport.md).
> Every number marked *assumption* is a configurable modelling choice, not market data. Demo data stays synthetic (`is_synthetic = true`).

## 1. Goal

The demo offers behave like real van LTL (part loads) traffic:
- Small consignments pay a share of a full-van price.
- Weight follows the pallet count.
- Several offers start close together and go the same way.

The engine keeps cheap add-on offers when it cuts the pool, and every plan reports how full the van was. When this is done, the profit plans for the demo fleet collect several consignments in one area and carry them together, instead of chaining single orders A→B→C. The dispatcher can see the van fill on every plan.

## 2. Business context

`docs/raport.md` §6 measured the current demo:
- 81% of offers have no consolidation partner;
- half of the fleet profit plans never carry more than one order at a time;
- vans run at 46% pallet fill and 40% weight fill per km.

The engine already supports interleaved pickups and deliveries with two-dimensional capacity (FEAT-003, `GOLD-001`). The causes are in the inputs (`docs/raport.md` §6.3):
1. FEAT-002 FR-13 prices every offer like a full van (`rate × distance`, whatever its size). A lone 1-pallet order is already profitable, so consolidation is never needed.
2. FEAT-002 FR-10 draws lanes at random over 39 cities, so consolidation is almost never possible.
3. Offer mass (40–1 085 kg) is unrelated to the pallet count.
4. FEAT-003 FR-17 ranks offers one at a time when it cuts the pool to 60. In all 20 benchmark runs at least one pool was cut.

In LTL the load factor decides profit (`docs/raport.md` §3.4). The demo should show the engine doing what REQ-009 already promises: "consolidated loads + chain of orders".

## 3. Scope / Out of scope

**In scope:**
- `offers-generator v3` (tariff, mass, consignment groups along corridors) and the regenerated committed offer files.
- A pure consolidation-partner metric.
- A partner-aware pool cut in the engine.
- Plan load metrics in the engine, the API and the plan UI.
- One new golden case (GOLD-011).
- 16 named towns and 550 generated synthetic towns in `cities.json` (605 places) and the regenerated `routing-matrix.json` (revision 3, OQ-010-07).
- Reachable delivery windows for the generated offers (revision 3, FR-4a).
- Consolidation KPIs in the benchmark report.

**Out of scope:**
- Changes to `fleet.json`, the cost profile, the legal profiles, the objectives or the validators.
- Hub / cross-dock modelling.
- Loading-order (LIFO) modelling.
- A separate clustering stage before the search.
- New agent tools or prompt changes (OQ-010-08).
- Real market prices.

## 4. Functional requirements

### 4.1 Offer generator v3 (replaces FEAT-002 FR-10, the mass part of FR-11 and FR-13 for v3)

- **FR-1 Version.** `generate_offers(seed, reference_date, count=150)` keeps its signature, purity and determinism (FEAT-002 FR-7). The enrichment file records `generatorVersion = "offers-generator v3"`. The committed files `data/mock/offers.timocom.json` and `data/mock/offers.enrichment.json` are regenerated for seed 20261109 and reference date 2026-11-16. FEAT-002 FR-8, FR-9, FR-12 (except its delivery-date rule, see FR-4a), FR-14 and FR-15 still apply.
- **FR-2 Tag layout unchanged.** The index ranges of the difficulty tags (FEAT-002 §6.4) are unchanged. Every tagged offer keeps its `MOCK-…` id and its tags, and the minimum counts still hold. `RETURN_TO_BASE`, `UNPROFITABLE_DETOUR` and `MUTUALLY_EXCLUSIVE` keep their own lane rules. Each `MUTUALLY_EXCLUSIVE` pair forms one group of two. Each `RETURN_TO_BASE` or `UNPROFITABLE_DETOUR` offer is a group of one.
- **FR-3 Pallets and mass.**
  - The pallet count is drawn with the weights (26, 24, 18, 12, 7, 5, 3, 2, 2, 1) for 1 … 10. This still "favours 1–4", as FEAT-002 FR-11 requires.
  - For an untagged offer, `weight_kg = min(1085, max(40, round(eq × u)))`, where `eq` is the pallet equivalent and `u` is drawn uniformly from 50–200 kg per EP (*assumption*, §6.4).
  - The mass overrides of `TOO_HEAVY_ALL`, `HEAVY_FOR_8EP` and `MUTUALLY_EXCLUSIVE` are unchanged.
  - `length_m` follows FEAT-002 FR-11.
- **FR-4 Consignment groups.**
  - Offers that FR-2 does not pin are generated in **groups**. A group is one corridor of §6.3 (drawn with its weight), one loading date (a working day within 7 days) and a size of 1–4 offers (weights 35, 30, 20, 15).
  - Each offer of a group:
    - picks up in a city of the corridor's origin zone: the group's anchor city with probability 0.6, otherwise another city of that zone;
    - delivers in a city of the destination zone;
    - has origin ≠ destination.
  - The windows of the offers in one group overlap by at least 1 hour. A whole-day window overlaps every window.
  - Over the 150 offers the domestic share stays between 35% and 55% (FEAT-002 AC-05). Poland is at one end of every lane.
- **FR-4a Delivery window (revision 3; replaces the delivery-date rule of FEAT-002 FR-12 for v3).** Measurements on the first v3 files showed that 49% of the timed offers could not reach their own delivery window, because the delivery reused the pickup's clock window on the same day (§12, revision 3). For every offer:
  - `drive_min = ceil(distance_km × 60 × 1.08 / 65)` (the fallback speed of FEAT-003 OQ-003-01, *assumption*) and `ready = pickup window start + 30 min + drive_min`.
  - If `ready` is not later than 20:00 on the loading date, the delivery is on the loading date and its window starts at `ready` rounded up to the full hour.
  - Otherwise the delivery is on the working day `max(1, ceil(distance_km / 600))` days after the loading date, and its window starts at the pickup's start hour.
  - The delivery window has the length of the pickup window (end capped at 23:00). Whole-day offers (`DAY_ONLY_WINDOW`) only get the date.
  - `RETURN_TO_BASE` offers still deliver on a Thursday or Friday: the date moves forward to the next such day, with the pickup's start hour.
  - The second offer of a `MUTUALLY_EXCLUSIVE` pair copies both windows of the first.
- **FR-4b Return groups (revision 3, proposal).** After a group, the next group is with probability 0.5 (*assumption*) its **return group**: the reverse corridor of §6.3 (when the table has one and the domestic-share limits allow it), loading on the next working day inside the 7-day window. Otherwise the next group is drawn as in FR-4. A return group gives a van that delivered the first group a load back the next morning.
- **FR-5 Enrichment.** Each offer's enrichment adds `groupId` (`G-001` …), `zoneFrom`, `zoneTo`, `billableShare` and `ltlPremium`. `price_formula` records `rate`, `distance_km`, `share`, `premium`, `handling`, `noise`, `min_fare` and the provenance (`assumption` for the tariff constants).
- **FR-6 LTL tariff.**
  - `share = min(1, max(eq / ref_ep, weight_kg / ref_kg))` and `premium = 1 + ltl_premium_max × (1 − share)`.
  - `handling = ltl_handling_per_ep × eq` (revision 3: a charge per pallet equivalent for collection and delivery, independent of the distance).
  - `price = max(ltl_min_fare, round((handling + rate × distance_km × share × premium) × noise))` in whole euros, rounded half-up.
  - `rate` comes from FEAT-002 §6.3 (unchanged). `distance_km` (haversine × 1.25) and `noise` (log-normal, σ = 0.15) are the same as in FEAT-002 FR-13. The constants are in §6.4.
  - For `NO_PALLETS` offers, `eq` is derived from the length as `ceil(length_m × 2.4)`.
  - The `UNPROFITABLE_DETOUR` override of FEAT-002 FR-13 still applies, with `ltl_min_fare` in place of the old minimum fare.

### 4.2 Consolidation-partner metric

- **FR-7.** A pure function `consolidation_partners(offers, pickup_km=80, delivery_km=150) -> dict[offer_id, list[offer_id]]` (*suggested* name). Offer B is a partner of offer A when all of these hold:
  - B ≠ A;
  - both have coordinates at both stops;
  - their loading dates are equal;
  - the haversine distance between their pickups is ≤ `pickup_km`;
  - the haversine distance between their deliveries is ≤ `delivery_km`.

  The relation is symmetric. The share of priced offers with coordinates that have ≥ 1 partner is called the **partner share**.

### 4.3 Partner-aware pool cut (replaces the ranking of FEAT-003 FR-17 and OQ-003-10)

- **FR-8.** If more than `max_pool_per_driver` offers pass the prefilter, the pool is built in three phases:
  1. Keep the `⌈max_pool_per_driver / 2⌉` offers with the highest `revenue / (deadhead_km + loaded_km)` (FEAT-003 FR-17 ratio; ties by offer id).
  2. Repeatedly add the best-ratio offer that is not yet kept and is a **pool partner** of a kept offer, until the pool is full or no such offer exists. A pool partner has a pickup within `pool_partner_pickup_km` and a delivery within `pool_partner_delivery_km` of the kept offer, measured as matrix distances of the snapshot's `TravelMatrix`.
  3. Fill the remaining places by ratio.

  `pool_truncated = true` as before. When the pool does not exceed `max_pool_per_driver`, the pool is identical to FEAT-003 FR-17. The order inside the returned pool stays "by offer id".
- **FR-9.** `EngineParams` gains `pool_partner_pickup_km = 80` and `pool_partner_delivery_km = 150` (*assumptions*, configurable, both > 0).

### 4.4 Plan load metrics

- **FR-10.** Every `RoutePlan` exposes:
  - `load_factor_ep = Σ(leg.load_pallet_eq × leg.distance_km) / (vehicle.pallet_places × Σ leg.distance_km)`;
  - `load_factor_kg = Σ(leg.load_kg × leg.distance_km) / (vehicle.payload_kg × Σ leg.distance_km)`;
  - `max_orders_on_board`: the highest number of offers on board at the same time, from the actions.

  Both factors are Decimals in 0 … 1 rounded half-up to 4 places, and 0 when `Σ km = 0`. They are pure functions of the plan and the vehicle. They change no objective, rank or validator.
- **FR-11 API.** `PlanSummary` (job result) and `RoutePlan` (`GET /api/v1/route-plans/{id}`) gain `loadFactorEp` and `loadFactorKg` (decimal strings, like `marginPct`) and `maxOrdersOnBoard` (integer). For stored plans they are computed on read from `route_stops` (`leg_m`, `load_pallet_eq_after`, `load_kg_after`, `kind`) and the vehicle's limits (OQ-010-03). The change only adds fields. Existing fields and status codes are unchanged.
- **FR-12 UI.**
  - Each variant card and the plan detail header show "Van fill: 46% of pallet places · 40% of payload" and "Orders on board: up to 2", in EN and PL through next-intl.
  - When `maxOrdersOnBoard = 1` and both factors are below 0.5, a neutral (grey, text-only) hint says "Single orders in a chain — the van runs mostly part-empty".
  - Colours follow the design system (no new accent, no colour-only meaning).

### 4.5 Golden case and benchmark

- **FR-13 GOLD-011 "Consolidation beats a chain".**
  - A driver in Katowice with a 10 EP / 1 085 kg van and two candidate sets:
    - (a) four Silesia → Saxony consignments (2–3 EP each, ≤ 1 085 kg together) with one corridor return;
    - (b) a chain of three single orders over a similar distance.
  - Prices follow FR-6.
  - Expected: the top profit plan uses set (a), `max_orders_on_board ≥ 3`, and its `load_factor_ep` and net profit equal the values computed by hand in `specs/golden/GOLD-011.md`.
  - The golden file is written with shown arithmetic and approved by the owner before the test exists.
- **FR-14 Benchmark.** `bench/fleet_5x60.py` adds a `consolidation` block per run and in the summary:
  - `load_factor_ep` and `load_factor_kg` of the fleet profit solution (km-weighted);
  - `plans_with_2plus_on_board` / `plans`;
  - `empty_km_share`;
  - `partner_share` of the offers.

  `scripts/benchmark_report.py` writes them to a "Consolidation" table in `docs/metrics.md`. The targets of §5 are recorded as met or not met and never asserted.

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| NFR-002 (unchanged) | Engine performance with the partner-aware pool | p95 ≤ 15 s for the 5 × 60 benchmark (target); phase 2 of FR-8 is at most O(n²) over the prefiltered offers |
| Target A (new) | Consolidation potential of the demo offers | partner share ≥ 50% for the committed seed (today 18.6%) |
| Target B (new) | Consolidation in the fleet profit plans (target, recorded only) | km-weighted `load_factor_ep` ≥ 60% and ≥ 70% of plans with `max_orders_on_board ≥ 2` over the 20 benchmark seeds (today 46% and 50%) |
| Target C (new) | Determinism | same seed → byte-identical offer files; same snapshot → identical pool and plans |

## 6. Contracts (API, data/migrations, ports, agent tools)

- **API:** `PlanSummary` and `RoutePlan` gain `loadFactorEp: string`, `loadFactorKg: string` and `maxOrdersOnBoard: integer` (all required in responses). No new endpoint, status code or problem `code`. `contracts/openapi.json` and the generated web `schema.d.ts` are regenerated.
- **Data / migrations:** no migration (values computed on read, OQ-010-03). The committed files `data/mock/offers.timocom.json` and `offers.enrichment.json` are regenerated (FR-1). Revision 3: `data/mock/cities.json` gains 16 named towns and 550 generated towns (FEAT-002 §6.1 revision 6, appended, existing order unchanged) and `data/mock/routing-matrix.json` is regenerated by `scripts/generate_routing_matrix.py` (haversine, 605 × 605, about 10 MB).
- **Ports:** no change.
- **Configuration:** `EngineParams.pool_partner_pickup_km`, `EngineParams.pool_partner_delivery_km` (FR-9). No new environment variable.
- **Agent tools:** no change (OQ-010-08).

### 6.1 Generator v3 tariff constants (assumptions)

| Constant | Value | Provenance |
|---|---|---|
| `ref_ep` | 10 EP (the largest demo van) | assumption |
| `ref_kg` | 1 000 kg | assumption |
| `ltl_premium_max` | 0.6 (a 1-EP consignment pays 1.54 × its share) | assumption |
| `ltl_min_fare` | 60 € | assumption |
| `ltl_handling_per_ep` | 35 € per pallet equivalent (revision 3) | assumption, set below the public per-pallet quotes of `docs/raport.md` §3.6 |
| kg per EP for untagged offers | uniform 50–200 | assumption |

Illustration (`docs/raport.md` §3.4): with the demo costs of about 0.50 €/km, a single 2-EP consignment earns about 0.25 €/km on a PL→PL lane. Four of them on board earn about 1.0 €/km.

### 6.2 Zones (every named city of `cities.json` belongs to exactly one zone; revision 3 adds the towns in *italics*)

A generated town (`<City> area NN`, FEAT-002 §6.1) belongs to the zone of its city.


| Zone | Cities |
|---|---|
| `PL-SIL` | Katowice, Bielsko-Biała, Częstochowa, Kraków, *Gliwice, Tychy, Sosnowiec, Rybnik* |
| `PL-OPW` | Wrocław, Opole, *Legnica, Wałbrzych* |
| `PL-WLK` | Poznań, *Gniezno, Leszno, Konin* |
| `PL-CEN` | Łódź, Warszawa, *Piotrków Trybunalski, Radom* |
| `PL-POM` | Gdańsk, *Gdynia* |
| `PL-ZPM` | Szczecin |
| `PL-PDK` | Rzeszów |
| `DE-SAX` | Dresden, Leipzig, *Chemnitz, Halle* |
| `DE-BER` | Berlin, *Potsdam* |
| `DE-NOR` | Hamburg, Hannover |
| `DE-SOU` | München, Nürnberg |
| `DE-RHM` | Köln, Frankfurt |
| `UPPER-RHINE` | Stuttgart, Strasbourg |
| `BENELUX` | Venlo, Rotterdam, Antwerpen |
| `CZ-BOH` | Praha |
| `MOR-SIL` | Ostrava, Žilina, *Olomouc* |
| `DANUBE` | Brno, Wien, Bratislava, Győr |
| `AT-LNZ` | Linz |
| `HU-BUD` | Budapest |
| `IT-NOR` | Verona, Milano |
| `FR-LYO` | Lyon |
| `DK` | Kolding |

### 6.3 Corridors (origin zone → destination zone, weight; total 100)

Domestic (45):
- `PL-SIL→PL-CEN` 8
- `PL-CEN→PL-SIL` 6
- `PL-SIL→PL-OPW` 5
- `PL-OPW→PL-SIL` 5
- `PL-WLK→PL-CEN` 4
- `PL-CEN→PL-WLK` 3
- `PL-CEN→PL-POM` 4
- `PL-POM→PL-CEN` 3
- `PL-OPW→PL-WLK` 3
- `PL-WLK→PL-OPW` 2
- `PL-SIL→PL-PDK` 1
- `PL-ZPM→PL-WLK` 1

Outbound (30):
- `PL-SIL→DE-SAX` 6
- `PL-OPW→DE-SAX` 4
- `PL-SIL→CZ-BOH` 3
- `PL-SIL→MOR-SIL` 2
- `PL-SIL→DANUBE` 3
- `PL-SIL→HU-BUD` 2
- `PL-WLK→DE-BER` 3
- `PL-WLK→DE-NOR` 3
- `PL-CEN→BENELUX` 2
- `PL-OPW→DE-SOU` 1
- `PL-SIL→IT-NOR` 1

Returns (25):
- `DE-SAX→PL-SIL` 5
- `DE-SAX→PL-OPW` 3
- `CZ-BOH→PL-SIL` 2
- `MOR-SIL→PL-SIL` 2
- `DANUBE→PL-SIL` 2
- `HU-BUD→PL-SIL` 1
- `DE-BER→PL-WLK` 3
- `DE-NOR→PL-WLK` 2
- `BENELUX→PL-CEN` 2
- `DE-RHM→PL-OPW` 1
- `UPPER-RHINE→PL-SIL` 1
- `DK→PL-ZPM` 1

These follow the corridors of `docs/report.md` §17.3 (Silesia ↔ Saxony/Czechia/Slovakia, Greater Poland ↔ Berlin/Hamburg, PL → Hungary, PL ↔ Benelux).

## 7. Acceptance criteria

- **AC-FEAT-010-01** [unit] Given seed 20261109 and reference date 2026-11-16 When `generate_offers` v3 runs twice Then both files are byte-identical, equal to the committed files, the enrichment records `generatorVersion = "offers-generator v3"`, and the payload has 150 offers with unique ids matching `^MOCK-\d{6}$`.
- **AC-FEAT-010-02** [unit] Given the committed v3 offers When the tags are read from the enrichment file Then every tag of FEAT-002 §6.4 sits on the same offer ids as its FEAT-002 index range, meets its minimum count, and each tagged offer really has the property.
- **AC-FEAT-010-03** [property] Given any seed When `generate_offers` v3 runs Then every offer still meets FEAT-002 AC-05 (two loading places, Poland at one end, 1–10 pallets, 40–1 100 kg, working-day windows within 7 days, domestic share 35–55%), and every untagged offer with pallets has `weight_kg = min(1085, max(40, round(eq × u)))` for some `u` in 50–200.
- **AC-FEAT-010-04** [unit] Given a committed offer without `NO_PRICE` When its price is recomputed from the enrichment values (`handling`, `rate`, `distance_km`, `share`, `premium`, `noise`) Then `price.amount` is a whole number ≥ 60 and equals `max(60, round((handling + rate × distance_km × share × premium) × noise))`, with `share` and `premium` matching FR-6 for the offer's pallets and mass.
- **AC-FEAT-010-05** [unit] Given rate 0.85 €/km, distance 400 km and noise 1 When the tariff is applied to (1 EP, 100 kg), (4 EP, 400 kg), (10 EP, 900 kg) and (2 EP, 1 000 kg) Then the prices are 87 €, 325 €, 690 € and 410 € (35 € per pallet equivalent plus the line haul; the last is weight-bound), and a half pallet of 40 kg over 40 km costs the minimum fare of 60 €. *(Revision 2 values: 60, 185, 340, 340.)*
- **AC-FEAT-010-06** [property] Given any seed When `generate_offers` v3 runs Then every offer has a `groupId`, every group has 1–4 offers (2 for a `MUTUALLY_EXCLUSIVE` pair), all offers of a group share the loading date, `zoneFrom` and `zoneTo` of one §6.3 corridor (or the lane of their FR-2 tag), and their windows overlap by at least 1 hour.
- **AC-FEAT-010-07** [unit] Given a fixture of three offers (A and B picked up 30 km apart on the same day with deliveries 100 km apart, C on another day) When `consolidation_partners` runs Then A and B are partners of each other and C has none; and Given the committed v3 offers Then the partner share is ≥ 0.50.
- **AC-FEAT-010-08** [unit] Given a snapshot with 70 offers that pass the prefilter, where offer P has the 61st-best ratio and is a pool partner of the best offer When the pool is built Then P is in the pool, the pool has 60 offers, `pool_truncated = true`, and the 30 best-ratio offers are all included.
- **AC-FEAT-010-09** [property] Given random snapshots When the pool is built twice Then the result is identical; when ≤ `max_pool_per_driver` offers pass, the pool equals the FEAT-003 FR-17 pool; otherwise it has exactly `max_pool_per_driver` offers and contains the `⌈max_pool_per_driver / 2⌉` best-ratio offers.
- **AC-FEAT-010-10** [unit] Given a plan with legs 100 km at 4 EP / 300 kg, 50 km empty and 150 km at 8 EP / 900 kg on a 10 EP / 1 000 kg van, with the actions PICKUP A, PICKUP B, DELIVERY A, DELIVERY B When the metrics are computed Then `load_factor_ep = 0.5333`, `load_factor_kg = 0.5500` and `max_orders_on_board = 2`; and Given a plan with zero km Then both factors are 0.
- **AC-FEAT-010-11** [contract] Given a finished optimisation job When `GET …/result` and `GET /api/v1/route-plans/{id}` are called Then every plan has `loadFactorEp`, `loadFactorKg` (decimal strings in 0 … 1) and `maxOrdersOnBoard` (integer ≥ 0) equal to the engine values for that plan, `contracts/openapi.json` declares them, and the OpenAPI diff against `main` reports no breaking change.
- **AC-FEAT-010-12** [unit] Given the GOLD-001 plan fixture and a chain plan fixture (one order on board, fills below 50%) When the variant cards render in EN and in PL Then both show the van fill in % of pallet places and of payload and the maximum orders on board, only the chain fixture shows the part-empty hint, and every text comes from `messages/en.json` / `messages/pl.json`.
- **AC-FEAT-010-13** [golden] Given the GOLD-011 inputs When `optimize` runs Then the top profit plan contains exactly the consolidated set, `max_orders_on_board`, `load_factor_ep`, revenue, costs and net profit equal the GOLD-011 values, and the chain set is not the top plan.
- **AC-FEAT-010-15** [property] Given any seed When `generate_offers` v3 runs Then every offer with timed windows can reach its delivery from its own pickup: the delivery window ends no earlier than the pickup window start plus 30 minutes plus `drive_min` of FR-4a, the delivery is never before the loading date, and both dates are working days. *(Listed after AC-14 in the test plan; added in revision 3.)*
- **AC-FEAT-010-14** [integration] Given the benchmark run with the 20 fixed seeds When `bench/fleet_5x60.py` writes its JSON and `scripts/benchmark_report.py` runs Then each run and the summary contain the `consolidation` block of FR-14, `docs/metrics.md` has the "Consolidation" table, and the target-B line says "met" or "not met" without failing the run.

## 8. Edge cases

- **Offers without coordinates:** excluded from the partner metric, and they are never pool partners.
- **Missing pallets:** a `NO_PALLETS` offer is priced from the `eq` derived from its length (FR-6). An offer without mass is not priced (it is already `MISSING_CAPACITY_DATA` in the prefilter).
- **`share` above 1** (heavy or large offers): clipped to 1, so the premium is 1 and the price is a full van.
- **`DECLARED_ONLY` van (D3):** `pallet_places` is known (9), so the factors are defined. The UI shows the counter as today.
- **Group zones:** a group in a one-city zone (`PL-ZPM`, `CZ-BOH`) uses the same city for every pickup. The FR-4 rule origin ≠ destination still holds because zones differ.
- **Pool phase 2 (FR-8) ties:** broken by ratio, then by offer id. A partner of several kept offers is added once.
- **Stored plans created before this feature:** the metrics are computed from their stops (FR-11), so old plans get the fields too.
- **Fleet profit may fall** with the LTL tariff (single small orders stop paying). That is expected, and the benchmark records it. Baselines use the same prices.

## 9. Dependencies

- FEAT-002 (generator, tags, rates).
- FEAT-003 (prefilter, `RoutePlan`, golden harness).
- FEAT-004 (plan read model, job result).
- FEAT-005 (variant cards, plan detail).
- FEAT-007 (benchmark report).
- No new library.
- Shared files: `data/mock/offers.*.json`, `data/mock/cities.json`, `data/mock/routing-matrix.json` (revision 3), `contracts/openapi.json`, `apps/web/messages/*.json`, `specs/golden/GOLD-011.md` (🔒 golden values), `docs/metrics.md`.
- Owner approval (O-12):
  - this specification and the assumptions of §6.1–6.3;
  - REQ-034 in `specs/requirements.md` (OQ-010-05);
  - the FEAT-002 / FEAT-003 changelog lines that mark the replaced parts (OQ-010-04).

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| AC-FEAT-010-01, 02, 04, 05 | `apps/api/tests/unit/freight/test_offers_generator.py` | committed v3 files |
| AC-FEAT-010-03, 06, 15 | `apps/api/tests/props/test_offers_generator.py` | Hypothesis seeds |
| AC-FEAT-010-07 | `apps/api/tests/unit/freight/test_consolidation_partners.py` (*suggested*) | 3-offer fixture, committed offers |
| AC-FEAT-010-08 | `apps/api/tests/unit/optimization/test_prefilter.py` | `tests/unit/optimization/factories.py` |
| AC-FEAT-010-09 | `apps/api/tests/props/test_pool_partners.py` (*suggested*) | random snapshots |
| AC-FEAT-010-10 | `apps/api/tests/unit/optimization/test_plan_metrics.py` (*suggested*) | hand-made legs |
| AC-FEAT-010-11 | `apps/api/tests/api/test_route_plans.py`, OpenAPI drift check | seeded job |
| AC-FEAT-010-12 | `apps/web/src/features/plans/variants.test.tsx` | GOLD-001 fixture + chain fixture |
| AC-FEAT-010-13 | `apps/api/tests/golden/test_gold_011.py` | `specs/golden/GOLD-011.md` |
| AC-FEAT-010-14 | `scripts/tests/test_benchmark_report.py` + manual `make bench` | benchmark JSON fixture |

Agent evals: no new scenario. The fake-model agent tests (`make test-agents`) must stay green on the regenerated offers (OQ-010-06).

## 11. Open questions

**Owner decisions (2026-11-15, O-12, issue #115):** all proposed defaults in this table are accepted.

| ID | Decision |
|---|---|
| OQ-010-01 | The tariff constants and the kg per EP range are those of §6.1, all with provenance `assumption`. |
| OQ-010-02 | The zones of §6.2 and the corridors and weights of §6.3 are accepted as listed. |
| OQ-010-03 | The load metrics are computed on read from `route_stops` and the vehicle's limits. No migration. |
| OQ-010-04 | FEAT-002 revision 5 marks FR-10, the mass part of FR-11, FR-13 and AC-FEAT-002-07 as superseded by FEAT-010 for `offers-generator v3` (AC-FEAT-002-07 withdrawn, AC-FEAT-002-04 … 06 stay). The FEAT-003 changelog marks the FR-17 ranking and OQ-003-10 as superseded by FEAT-010 FR-8. |
| OQ-010-05 | REQ-034 (P1) is added to `specs/requirements.md` with the proposed text and the traceability row REQ-034 → FEAT-010 → AC-FEAT-010-01 … 14. |
| OQ-010-06 | FR-2 keeps the tagged ids. Untagged ids referenced by evals and agent tests are checked after each regeneration and listed in the completion report. Live `ai-evals` are not re-run. |
| OQ-010-07 | Revision 2: no satellite towns. **Changed in revision 3 (owner instruction, 2026-11-15):** 16 named towns (§6.2) and 550 generated towns (ten around each of the 55 named places, FEAT-002 §6.1) are added to `cities.json`, so that pickups and deliveries can be close without sharing a city centre; `routing-matrix.json` is regenerated (605 × 605). |
| OQ-010-08 | Agent tools and prompts are unchanged in this feature. |
| OQ-010-09 | The pool-partner distance is the matrix distance of the snapshot's `TravelMatrix`. |

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-010-01 | Tariff constants and kg per EP (§6.1). | as in §6.1, all `assumption` | AC-04, 05 |
| OQ-010-02 | Zones and corridor weights (§6.2, §6.3). | as listed | AC-06, 07 |
| OQ-010-03 | Load metrics: computed on read from `route_stops`, or stored in new `route_plans` columns (needs a migration)? | computed on read; no migration | AC-11 |
| OQ-010-04 | How the approved FEAT-002 / FEAT-003 record the replaced parts. | FEAT-002 rev. 5: FR-10, FR-11 (mass), FR-13 and AC-FEAT-002-07 marked "superseded by FEAT-010 for offers-generator v3"; AC-07 withdrawn, AC-04 … 06 stay. FEAT-003 rev. n+1: the FR-17 ranking and OQ-003-10 superseded by FEAT-010 FR-8. | AC-01, 08 |
| OQ-010-05 | A requirement for this feature. | REQ-034 (P1): "Demo offers and plans reflect LTL consolidation: size-based prices, grouped lanes, partner-aware pool, load metrics." | traceability only |
| OQ-010-06 | Eval fixtures and agent tests name `MOCK-…` ids. | FR-2 keeps the tagged ids; untagged ids referenced by evals are checked after regeneration and listed in the completion report; live `ai-evals` are not re-run (budget O-7 used up) | AC-01 |
| OQ-010-07 | Satellite towns (Gliwice, Tychy, …) for a real "close radius" below city level. | not now; needs `cities.json`, `routing-matrix.json` and FEAT-002/004 changes | nothing |
| OQ-010-08 | Should agent tools (`get_plan`, plan comparison facts) export the load metrics? | not in this feature; a later spec with a tool change and `ai-evals` | nothing |
| OQ-010-09 | Pool-partner distance: matrix km (road or fallback) or haversine? | matrix km of the snapshot (the same numbers the search uses) | AC-08, 09 |
| OQ-010-10 | Price level (revision 3). With the constants of revision 2 and the demo cost profile the committed seed gave the demo fleet at most one marginally profitable plan (revenue 670 €, cost 593 € for a 798 km round trip of two groups). The tariff was only proportional to the distance; public per-pallet quotes (`docs/raport.md` §3.6) carry a large part that does not depend on the distance. | `ltl_handling_per_ep = 35 €` added to FR-6 (owner instruction of 2026-11-15 to research pallet prices and reconfigure the seed). Measured afterwards: every demo driver has profitable plans, and a lone 3-pallet order on a 250 km lane still loses money. The other constants of §6.1 are unchanged. | AC-04, 05 |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-15 | Initial draft from `docs/raport.md` (LTL research and measurements). |
| 2 | 2026-11-15 | Status `draft` → `approved` by the owner (O-12, issue #115): §6.1–6.3 accepted as drafted; owner decisions on OQ-010-01 … 09 recorded (§11); REQ-034 added to the requirements. |
| 3 | 2026-11-15 | Owner instruction after the first implementation run was reported `blocked`: with the tariff and the groups of revision 2 no demo driver had a profitable plan, because 69 of 140 timed offers could not reach their own delivery window (FEAT-002 FR-12 reused the pickup's clock window on the delivery day). Added FR-4a (reachable delivery windows) and AC-FEAT-010-15; OQ-010-07 reversed: 16 satellite towns in `cities.json` (§6.2), `routing-matrix.json` regenerated. The concrete rule of FR-4a and the list of towns were drafted by the coding agent and are open to review in the pull request. |
| 3 (cont.) | 2026-11-15 | Second owner instruction of the day: at least 500 towns and a price check. 550 generated towns added (FEAT-002 §6.1); FR-4b (return groups); `ltl_handling_per_ep` added to FR-6 after the price research in `docs/raport.md` §3.6; AC-FEAT-010-04 and 05 follow the new formula; OQ-010-10 recorded. |
| 4 | 2026-11-15 | The owner approved revision 3 (FR-4a, FR-4b, the handling charge of FR-6, the towns of §6.2 and FEAT-002 §6.1, AC-FEAT-010-15, OQ-010-10) and the values of `specs/golden/GOLD-011.md`. |
