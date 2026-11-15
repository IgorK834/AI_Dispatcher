# GOLD-011: Consolidation beats a chain

- **Status:** proposed on 2026-11-15 — **waiting for the owner's approval**. Until then no golden test exists for this case (`apps/api/tests/golden/test_gold_011.py` and its entry in `cases.py` are not written). After approval the values are binding (a later change = spec change + human approval).
- **Covers:** FEAT-010 · AC-FEAT-010-13 · FR-6, FR-10, FR-13 · invariants 1–8, 10, 14, 17 ([`context.md`](../../context.md) → Optimization Engine Invariants).
- **Conventions:** [`specs/golden/README.md`](README.md) (G1–G14). The prices follow FEAT-010 FR-6 as proposed in revision 3 (handling charge of 35 € per pallet equivalent). If the owner changes that tariff, the prices and every money value below must be recalculated.
- **Data:** synthetic (`is_synthetic = true`); not real freight-exchange offers and not real people.

> The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance.

## 1. Scenario

Driver D1 stands in Katowice with a 10-pallet curtain-sider van (payload 1 085 kg). Two sets of offers compete:

- **Consolidated set (a):** four consignments Katowice → Dresden (3 + 2 + 3 + 2 pallets, 1 030 kg together) loaded on Monday morning, and one return consignment Dresden → Katowice (6 pallets) loaded on Tuesday morning.
- **Chain set (b):** three single orders over a similar distance: Katowice → Wrocław, Wrocław → Dresden, Dresden → Katowice.

The engine must choose set (a): `pick A1 → pick A2 → pick A3 → pick A4 → drop A1 → drop A2 → drop A3 → drop A4 → pick R → drop R`. Four orders are on board on the way out. The van is full (10 of 10 places), so no chain offer fits next to them. `home_by` is not set; the plan ends at the last delivery, which is in Katowice.

## 2. Inputs

**Reference date (`MOCK_REFERENCE_DATE`):** Monday 2026-11-16; all local times are CET (UTC+1).

**Engine parameters:** `horizon_days=5`, `max_offers_per_plan=6`, `top_k_per_driver=10`, `max_pool_per_driver=60`, `node_budget_per_driver=1_500_000`, `max_first_deadhead_km=350`, `default_service_min=30`, `van_speed_factor=1.08`, `pool_partner_pickup_km=80`, `pool_partner_delivery_km=150`; objective under test: `profit`.

### 2.1 Cities

| City | Country | Lat | Lon | Time zone |
|---|---|---|---|---|
| Katowice | PL | 50.2649 | 19.0238 | Europe/Warsaw |
| Wrocław | PL | 51.1079 | 17.0385 | Europe/Warsaw |
| Dresden | DE | 51.0504 | 13.7373 | Europe/Berlin |

### 2.2 Driver, state and vehicle — D1

Identical to GOLD-001 §2.2: home base and position Katowice, `available_from` Mon 2026-11-16 06:00 (05:00Z), no `home_by`, all counters 0, van `GOLD-VAN-10` (10 pallet places, `payload_kg` 1085, `sleeper_cab` false, 11.0 / 13.0 l per 100 km, curve `VAN_DEFAULT_V1`).

### 2.3 Cost profile

`GOLD-CP-1`, identical to GOLD-001 §2.3 (fuel 1.81 €/l, driver 14.00 €/h, vehicle 0.12 €/km, accommodation 55.00 €, no toll, `CO2_FACTOR_KG_PER_L` 2.6, `min_profit` 0, `min_margin_pct` 0).

### 2.4 Routing (conventions G1–G3)

| Leg | Haversine km | × 1.25 → `distance_km` | `km × 60 × 1.08 / 65` | `drive_min` (ceil) |
|---|---|---|---|---|
| Katowice ↔ Dresden | 382.665 | 478.33 | 476.858 | 477 |
| Katowice ↔ Wrocław | 168.360 | 210.45 | 209.802 | 210 |
| Wrocław ↔ Dresden | 230.684 | 288.36 | 287.473 | 288 |

### 2.5 Prices (FEAT-010 FR-6, noise = 1)

`share = min(1, max(eq / 10, kg / 1000))`, `premium = 1 + 0.6 × (1 − share)`, `handling = 35 × eq`, `price = max(60, round_half_up(handling + rate × distance_km × share × premium))`. Rates (FEAT-002 §6.3): PL→DE 0.68, DE→PL 0.7 × 0.68 = 0.476, PL→PL 0.85 €/km. All pallets are EUR 1200×800, so `eq` = pallet count.

| Offer | eq | kg | share | premium | handling | `rate × km` | line haul = `rate × km × share × premium` | handling + line haul | Price € |
|---|---|---|---|---|---|---|---|---|---|
| A1 | 3 | 300 | 0.30 | 1.420 | 105 | 0.68 × 478.33 = 325.2644 | 325.2644 × 0.30 × 1.420 = 138.563 | 243.563 | **244** |
| A2 | 2 | 220 | 0.22 | 1.468 | 70 | 325.2644 | 325.2644 × 0.22 × 1.468 = 105.047 | 175.047 | **175** |
| A3 | 3 | 310 | 0.31 | 1.414 | 105 | 325.2644 | 325.2644 × 0.31 × 1.414 = 142.576 | 247.576 | **248** |
| A4 | 2 | 200 | 0.20 | 1.480 | 70 | 325.2644 | 325.2644 × 0.20 × 1.480 = 96.278 | 166.278 | **166** |
| R | 6 | 600 | 0.60 | 1.240 | 210 | 0.476 × 478.33 = 227.6851 | 227.6851 × 0.60 × 1.240 = 169.398 | 379.398 | **379** |
| C1 | 2 | 200 | 0.20 | 1.480 | 70 | 0.85 × 210.45 = 178.8825 | 178.8825 × 0.20 × 1.480 = 52.949 | 122.949 | **123** |
| C2 | 3 | 300 | 0.30 | 1.420 | 105 | 0.68 × 288.36 = 196.0848 | 196.0848 × 0.30 × 1.420 = 83.532 | 188.532 | **189** |
| C3 | 5 | 500 | 0.50 | 1.300 | 175 | 227.6851 | 227.6851 × 0.50 × 1.300 = 147.995 | 322.995 | **323** |

In A2 and A3 the mass decides the share (220 kg and 310 kg against 2 and 3 pallets).

### 2.6 Offers

| Offer | `source_offer_id` | Route | Pallets | kg | Price € | Pickup window (local) | Delivery window (local) | Service min |
|---|---|---|---|---|---|---|---|---|
| A1 | `GOLD-011-A1` | Katowice → Dresden | 3 | 300 | 244.00 | Mon 11-16 06:00–10:00 | Mon 11-16 12:00–20:00 | 30 + 30 |
| A2 | `GOLD-011-A2` | Katowice → Dresden | 2 | 220 | 175.00 | Mon 11-16 06:00–10:00 | Mon 11-16 12:00–20:00 | 30 + 30 |
| A3 | `GOLD-011-A3` | Katowice → Dresden | 3 | 310 | 248.00 | Mon 11-16 06:00–10:00 | Mon 11-16 12:00–20:00 | 30 + 30 |
| A4 | `GOLD-011-A4` | Katowice → Dresden | 2 | 200 | 166.00 | Mon 11-16 06:00–10:00 | Mon 11-16 12:00–20:00 | 30 + 30 |
| R | `GOLD-011-R` | Dresden → Katowice | 6 | 600 | 379.00 | Tue 11-17 06:00–10:00 | Tue 11-17 12:00–20:00 | 30 + 30 |
| C1 | `GOLD-011-C1` | Katowice → Wrocław | 2 | 200 | 123.00 | Mon 11-16 06:00–10:00 | Mon 11-16 08:00–16:00 | 30 + 30 |
| C2 | `GOLD-011-C2` | Wrocław → Dresden | 3 | 300 | 189.00 | Mon 11-16 09:00–14:00 | Mon 11-16 12:00–20:00 | 30 + 30 |
| C3 | `GOLD-011-C3` | Dresden → Katowice | 5 | 500 | 323.00 | Tue 11-17 06:00–10:00 | Tue 11-17 12:00–20:00 | 30 + 30 |

All offers: `vehicleProperties.type = ["VEHICLE_UP_TO_3_5_T"]`, body `CURTAIN_SIDER`, pallets `generated_mock`, service time `default` (flag `SERVICE_TIME_DEFAULTED`).

## 3. Expected outcome

### 3.1 The three best offer sets (objective `profit`)

| Rank | Offer set | Profile | Revenue € | Cost € | Net profit € | Finish | Fuel l |
|---|---|---|---|---|---|---|---|
| 1 | {A1, A2, A3, A4, R} | `eu561_van_international_v1` | 1 212.00 | 684.03 | **527.97** | Tue 15:42 | 122.445 |
| 2 | {A1, A2, A3, A4} | `eu561_van_international_v1` | 833.00 | 339.03 | 493.97 | Mon 18:42 | 63.163 |
| 3 | {A1, A2, A3, A4, C3} | `eu561_van_international_v1` | 1 156.00 | 682.39 | 473.61 | Tue 15:42 | 121.542 |

Why the chain cannot join set (a): with A1 … A4 on board the van carries 10 of 10 pallet places, so C1 and C2 do not fit on Monday. R and C3 are both loaded in Dresden on Tuesday morning and need 6 + 5 = 11 places together, so only one of them fits; R pays 56 € more for the same leg. The chain set {C1, C2, C3} has a revenue of 123 + 189 + 323 = 635.00 € and never more than one order on board; it is not among the three best sets.

Rank 2 arithmetic: fuel 63.163 l × 1.81 = 114.33; driver (477 + 240) min ÷ 60 × 14.00 = 167.30; vehicle 478.33 × 0.12 = 57.40; no rest away from base; cost 339.03; 833.00 − 339.03 = 493.97.

Rank 3 arithmetic: return leg with 500 kg: `L100 = (11 + 2 × 500 / 1085) × 1.023745 = 12.20474`, 478.33 km → 58.379 l; fuel 63.163 + 58.379 = 121.542 l × 1.81 = 219.99; driver 292.60; vehicle 114.80; accommodation 55.00; cost 682.39; 1 156.00 − 682.39 = 473.61.

### 3.2 Rank 1 plan — schedule, load and costs (profile `eu561_van_international_v1`)

| # | Action | Place | Leg km | Leg drive min | Inserted | Arrival | Wait min | Service start | Departure | Load after (EUR eq / kg) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | START | Katowice | — | — | — | — | 0 | Mon 06:00 | Mon 06:00 | 0.0 / 0 |
| 1 | PICKUP A1 | Katowice | 0.00 | 0 | — | Mon 06:00 | 0 | Mon 06:00 | Mon 06:30 | 3.0 / 300 |
| 2 | PICKUP A2 | Katowice | 0.00 | 0 | — | Mon 06:30 | 0 | Mon 06:30 | Mon 07:00 | 5.0 / 520 |
| 3 | PICKUP A3 | Katowice | 0.00 | 0 | — | Mon 07:00 | 0 | Mon 07:00 | Mon 07:30 | 8.0 / 830 |
| 4 | PICKUP A4 | Katowice | 0.00 | 0 | — | Mon 07:30 | 0 | Mon 07:30 | Mon 08:00 | 10.0 / 1 030 |
| 5 | DELIVERY A1 | Dresden | 478.33 | 477 | BREAK 45 min (Mon 12:00–12:45) | Mon 16:42 | 0 | Mon 16:42 | Mon 17:12 | 7.0 / 730 |
| 6 | DELIVERY A2 | Dresden | 0.00 | 0 | — | Mon 17:12 | 0 | Mon 17:12 | Mon 17:42 | 5.0 / 510 |
| 7 | DELIVERY A3 | Dresden | 0.00 | 0 | — | Mon 17:42 | 0 | Mon 17:42 | Mon 18:12 | 2.0 / 200 |
| 8 | DELIVERY A4 | Dresden | 0.00 | 0 | — | Mon 18:12 | 0 | Mon 18:12 | Mon 18:42 | 0.0 / 0 |
| 9 | PICKUP R | Dresden | 0.00 | 0 | DAILY_REST 678 min (Mon 18:42–Tue 06:00) | Mon 18:42 | 0 | Tue 06:00 | Tue 06:30 | 6.0 / 600 |
| 10 | DELIVERY R | Katowice | 478.33 | 477 | BREAK 45 min (Tue 11:00–11:45) | Tue 15:12 | 0 | Tue 15:12 | Tue 15:42 | 0.0 / 0 |

Counter trace (convention G5, G6, G7):
- Monday: after the four pickups at 08:00 the work since the last break is 120 min. After 240 min of driving (12:00) it reaches 360 min → `BREAK` 45 min. The remaining 237 min of driving end at 16:42 (driving today 477 min ≤ 540). The four deliveries end at 18:42.
- The pickup window of R opens on Tuesday at 06:00. The wait of 678 min (18:42 → 06:00) is ≥ 660 min and is taken as a daily rest of that length (G7), in Dresden, away from base.
- Tuesday: after the pickup (06:00–06:30) the driving since the last break reaches 270 min at 11:00 → `BREAK` 45 min. The remaining 207 min end at 15:12; the delivery ends at 15:42.

Fuel per leg (convention G10): `v = 478.33 × 60 / 477 = 60.1673 km/h`; `speed_curve(v) = 1.10 − 0.15 × (60.1673 − 50) / 20 = 1.023745`.

| Leg | km | drive min | curve(v) | load kg | `L100 = (11 + 2 × kg / 1085) × curve` | litres (3 dp) |
|---|---|---|---|---|---|---|
| Katowice → Dresden | 478.33 | 477 | 1.023745 | 1 030 | (11 + 1.898618) × 1.023745 = 13.20489 | 63.163 |
| Dresden → Katowice | 478.33 | 477 | 1.023745 | 600 | (11 + 1.105991) × 1.023745 = 12.39345 | 59.282 |
| **Total** | **956.66** | **954** | | | | **122.445** |

Legs inside one city are 0 km and burn no fuel (G3).

Totals and cost breakdown (EUR; minor units are cents):

| Item | Arithmetic | Value |
|---|---|---|
| Distance | 478.33 + 478.33 (empty km: 0) | 956.66 km |
| Driving | 477 + 477 | 954 min |
| Service | 10 stops × 30 min | 300 min |
| Waiting | the wait before `PICKUP R` is a daily rest (G7) | 0 min |
| Work (drive + service + wait) | 954 + 300 + 0 | 1 254 min |
| Breaks / daily rests inserted | 2 × 45 / 1 × 678 | 90 min / 678 min |
| Start → finish | Mon 06:00 → Tue 15:42 (2026-11-16T05:00Z → 2026-11-17T14:42Z) | 2 022 min |
| Revenue | 244 + 175 + 248 + 166 + 379 | 1 212.00 |
| Fuel cost | 122.445 l × 1.81 €/l = 221.625 | 221.63 |
| Toll cost | PL/DE ≤ 3.5 t: 0 €/km | 0.00 |
| Driver cost | 1 254 min ÷ 60 × 14.00 €/h | 292.60 |
| Per diem | international plan (stops in DE) → none (G9) | 0.00 |
| Accommodation | 1 daily rest away from base, sleeper cab: no | 55.00 |
| Vehicle cost | 956.66 km × 0.12 €/km = 114.799 | 114.80 |
| **Total cost** | 221.63 + 292.60 + 55.00 + 114.80 | **684.03** |
| **Net profit** | 1 212.00 − 684.03 | **527.97** (margin 43.56 %) |
| CO₂ | 122.445 l × 2.6 kg/l = 318.357 | 318.36 kg |

Load metrics (FEAT-010 FR-10):

| Metric | Arithmetic | Value |
|---|---|---|
| `load_factor_ep` | (10 × 478.33 + 6 × 478.33) ÷ (10 × 956.66) = 16 ÷ 20 | **0.8000** |
| `load_factor_kg` | (1 030 × 478.33 + 600 × 478.33) ÷ (1 085 × 956.66) = 1 630 ÷ 2 170 = 0.75115 | **0.7512** |
| `max_orders_on_board` | A1, A2, A3 and A4 between Katowice and Dresden | **4** |

## 4. Assertions a test must make

1. The rank 1 plan for objective `profit` contains exactly the offers {A1, A2, A3, A4, R} in the order `PICKUP A1 → PICKUP A2 → PICKUP A3 → PICKUP A4 → DELIVERY A1 → DELIVERY A2 → DELIVERY A3 → DELIVERY A4 → PICKUP R → DELIVERY R`.
2. No returned plan before rank 4 has the offer set {C1, C2, C3}; the rank 1 plan contains none of C1, C2, C3.
3. `max_orders_on_board = 4`, `load_factor_ep = 0.8000`, `load_factor_kg = 0.7512`.
4. `load_pallet_eq_after` per action stop = 3 → 5 → 8 → 10 → 7 → 5 → 2 → 0 → 6 → 0; `load_kg_after` = 300 → 520 → 830 → 1 030 → 730 → 510 → 200 → 0 → 600 → 0; both stay within the vehicle capacity (invariant 1).
5. `rules_profile = eu561_van_international_v1`.
6. Service start times: PA1 Mon 06:00, PA2 Mon 06:30, PA3 Mon 07:00, PA4 Mon 07:30, DA1 Mon 16:42, DA2 Mon 17:12, DA3 Mon 17:42, DA4 Mon 18:12, PR Tue 06:00, DR Tue 15:12; every one lies inside its window (invariant 4).
7. Totals: `distance_km = 956.66`, `empty_km = 0.00`, `drive_min = 954`, `work_min = 1254`, `wait_min = 0`, breaks 90 min, one daily rest of 678 min, `finish_at = 2026-11-17T14:42Z`.
8. `fuel_l = 122.445`, `co2_kg = 318.36` (invariant 17).
9. Cost breakdown in minor units: fuel 22163, toll 0, driver 29260, per diem 0, accommodation 5500, vehicle 11480; `cost_total_minor = 68403`; `revenue_minor = 121200`; `net_profit_minor = 52797` (invariant 7).
10. Rank 2 is {A1, A2, A3, A4} with `net_profit_minor = 49397`; rank 3 is {A1, A2, A3, A4, C3} with `net_profit_minor = 47361`.
11. `RouteValidator` accepts the plan; running the optimisation twice on the same snapshot gives an identical result (invariant 8).
12. The plan carries the warning flags `LOADING_ORDER_NOT_MODELLED` and `SERVICE_TIME_DEFAULTED`.

## 5. Open questions

- The return consignment adds only 34.00 € of profit over rank 2 (527.97 against 493.97): its revenue of 379 € barely covers a second day (driver 125.30, fuel 107.30, vehicle 57.40, accommodation 55.00). That is the honest result of the tariff and the cost profile; the case still fixes the consolidated set as the best plan.
- A scratch run of the engine on these inputs (not committed) returned the same values as the arithmetic above. The golden test itself is written only after the owner approves this file.

## 6. Changelog

- 2026-11-15: proposed (FEAT-010 FR-13). Not approved yet.
